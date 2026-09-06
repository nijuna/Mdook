# Architecture

> **Rewritten 2026-09-04.** The original version of this file described the
> project as planned before implementation started: a Typer CLI, a
> Marker/pdf-craft OCR path, and a much smaller data model. None of that
> matches what was actually built — the project became GUI-first
> (`mdook/gui/`, PySide6) very early, the OCR engine ended up being
> Tesseract (see `STACK.md`'s evolution note for why), and the data model
> grew substantially across 19 implementation batches. Rather than layer
> another dozen "**Update:**" callouts on a description that was wrong
> in its bones, this file was rewritten from the real code — this is what
> actually exists today. `RULES.md` and `STACK.md` still use the
> preserve-and-annotate convention for their rule-by-rule/tool-by-tool
> detail; read those for the "how did we get here" history. This file is
> the current-state reference.

---

## Pipeline Overview

Mdook processes a PDF through five sequential stages, each with a clear
input/output contract (Pydantic models, `mdook/core/models.py`). No stage
reaches back to modify an earlier stage's output.

```
PDF File
   │
   ▼
┌──────────────────────────┐
│  Stage 1: INTAKE         │  mdook/core/stages/intake.py
│                          │  → BookManifest (metadata + zone map + profile)
└──────────────────────────┘
   │
   ▼
┌──────────────────────────┐
│  Stage 2: EXTRACTION     │  mdook/core/stages/extraction.py
│                          │  → list[PageData] (text/image/table blocks,
│                          │    OCR-routed per page where needed)
└──────────────────────────┘
   │
   ▼
┌──────────────────────────┐
│  Stage 3: SEMANTIC       │  mdook/core/stages/semantic.py
│          ANALYSIS        │  → DocumentTree (chapters → sections → content)
└──────────────────────────┘
   │
   ▼
┌──────────────────────────┐
│  Stage 4: RENDERING      │  mdook/core/stages/rendering.py
│                          │  → Markdown files + attachments (the vault)
└──────────────────────────┘
   │
   ▼
┌──────────────────────────┐
│  Stage 5: VALIDATION     │  mdook/core/stages/validation.py
│                          │  → ValidationReport (warnings, errors, stats)
└──────────────────────────┘
   │
   ▼
Obsidian Vault (output directory)
```

`mdook/core/pipeline.py`'s `convert()` orchestrates all five stages and
reports progress via a plain `on_progress(percent, message) -> None`
callback — the GUI (`mdook/gui/worker.py`'s `ConversionWorker`, a `QThread`)
is the only thing that turns that into Qt signals. The core pipeline has no
Qt dependency at all.

Almost all of the actual *detection logic* — is this a heading, is this a
citation, is this text right-to-left — lives in `mdook/core/rules/*.py`,
one pure module per concern, with no I/O. The `stages/*.py` files are thin
orchestrators that call into `rules/*.py` in the right order. See
`RULES.md` for the full rule-by-rule catalog; this file only summarizes.

---

## Stage 1 — Intake (`mdook/core/stages/intake.py`)

**Input:** PDF file path + optional profile override
**Output:** `BookManifest`

- Opens the PDF with PyMuPDF. Fails fast with a clear, typed error
  (`mdook.core.errors.EncryptedPDFError` / `CorruptPDFError`) rather than
  producing garbage or an opaque traceback if the file is password-
  protected or too damaged to read.
- Samples pages to flag `needs_ocr` (a cheap whole-book estimate; the real
  per-page OCR decision happens in Stage 2 — see Rule 4.1-style routing
  below).
- Extracts the PDF's own bookmark/outline tree (`doc.get_toc()`) — the
  preferred source for heading hierarchy when it exists (`Mdook-docs/RULES.md`
  Rule 2.1).
- Detects zones (front matter / body / back matter) via
  `mdook.core.rules.zones`.
- Logs an informational note for very large books (1000+ pages) — not a
  hard limit.

```
BookManifest:
  file_path: str
  title: str
  author: str
  total_pages: int
  needs_ocr: bool
  profile: "literature" | "technical"
  zone_map: list[ZoneEntry]
  bookmarks: list[Bookmark] | None
  metadata: dict[str, Any]        # ISBN, publisher, edition, etc.
```

**Not implemented:** signal-based profile auto-detection (the table above
in the original plan) — the caller-supplied profile is used as-is,
defaulting to `literature`. See `Mdook-docs/ROADMAP.md` Phase 5.

---

## Stage 2 — Extraction (`mdook/core/stages/extraction.py`)

**Input:** `BookManifest`
**Output:** `list[PageData]`

For each page:

1. PyMuPDF extracts every text span (font, size, bold/italic/superscript,
   bbox), grouped into `TextBlock`s by style continuity (Rule 5.1's
   font-name-independent matching — see `RULES.md`).
2. pdfplumber runs table detection (`mdook.core.rules.tables`) — PyMuPDF
   has no equivalent.
3. **Per-page text-quality scoring** (`mdook.core.rules.text_quality`)
   decides whether this specific page's native text is usable. A page
   that scores below threshold is re-extracted via **Tesseract**
   (`mdook.core.rules.ocr`, via `pytesseract` — not Marker/pdf-craft, see
   `STACK.md`'s evolution note for why), whose word+bbox output is
   normalized directly into the same `TextBlock` shape so every
   downstream rule runs unchanged regardless of source. A page with no
   text *and* no images is recorded as intentionally blank and skips OCR
   entirely rather than logging a false "OCR failed" warning.
4. Embedded raster images are extracted (`get_images()`); vector-drawn
   diagrams with no embedded raster (flowcharts, charts drawn as PDF
   paths) are detected via `page.get_drawings()` and rasterized
   (`mdook.core.rules.images`). Nearby caption text is associated and
   removed from the ordinary text flow.
5. A page whose lines report vertical writing mode (traditional CJK
   typesetting) is flagged (`is_vertical_text`) so later stages know not
   to apply horizontal-reading-order assumptions to it.
6. Duplicate overlapping text layers (a scan carrying both a faint
   original layer and a separately-baked-in OCR layer) are deduplicated.
7. Multi-column reading order (`mdook.core.rules.columns`) is
   reconstructed as a final whole-book pass, once every page's blocks
   exist — right-to-left column order when the page's dominant script is
   RTL (`mdook.core.rules.scripts`).

```
TextBlock:
  text: str
  font_name: str
  font_size: float
  is_bold: bool
  is_italic: bool
  is_superscript: bool
  bbox: (x0, y0, x1, y1)
  page_number: int

ImageBlock:
  image_path: str          # temp file; Stage 4 copies into attachments/
  bbox: (x0, y0, x1, y1)
  caption: str | None
  page_number: int

TableBlock:
  cells: list[list[str]]
  bbox: (x0, y0, x1, y1)
  page_number: int

PageData:
  page_number: int
  width: float
  height: float
  blocks: list[TextBlock | ImageBlock | TableBlock]
  header_text: str | None       # populated in Stage 2 (header/footer detection)
  footer_text: str | None
  was_ocrd: bool                # True if this page's blocks came from Tesseract
  is_vertical_text: bool        # traditional vertical CJK typesetting
  is_blank: bool                # no text and no images at all
```

---

## Stage 3 — Semantic Analysis (`mdook/core/stages/semantic.py`)

**Input:** `BookManifest` + `list[PageData]`
**Output:** `DocumentTree`

This is the brain of the pipeline — see `RULES.md` for the full ruleset
(17 numbered rule sections as of Batch 19). Summary of what happens, in
order:

1. Drop-cap immunity, then heading detection — bookmark-based (trusted
   completely when ≥3 bookmarks exist) or font-size clustering with
   positional confirmation otherwise. A Part/Book/Volume tier above the
   chapter tier, if the heading text itself reads as such a label, is
   recorded separately (`Chapter.part_title`) rather than treated as a
   chapter.
2. Footnote/endnote detection and inline-marker correlation.
3. Citation-to-bibliography linking (numeric `[1]`/`[1,3]`/`[1-4]` style)
   against a detected Bibliography/References back-matter section.
4. Chapter segmentation, with the printed TOC discarded (Rule 9.4) and
   decorative elements filtered (Rule 9.5).
5. Per chapter, per text run: lists, monospace-font code blocks, callout/
   sidebar boxes ("Note:", "Warning.", theorem-like environments), display/
   inline math (Unicode symbol-density scoring, rendered via Obsidian's
   native MathJax), block quotes, and ordinary paragraphs — in that
   priority order.
6. Front/back matter sections named by keyword-label matching.

```
DocumentTree:
  metadata: BookMetadata
  front_matter: list[Section]
  chapters: list[Chapter]
  back_matter: list[Section]

Chapter:
  number: int
  title: str
  level: int                    # always 1 today; see part_title below
  part_title: str | None        # Part/Book/Volume division, if any
  sections: list[Section]
  footnotes: list[Footnote]
  page_spans: list[(start_page, end_page)]

Section:
  title: str | None
  level: int
  content: list[SectionContent]

SectionContent = Paragraph | ImageRef | TableData | BlockQuote
                | ListData | CodeBlock | CalloutBlock | MathBlock
                | VerseBlock | GlossaryBlock

Paragraph:      text: str; page_number: int
ImageRef:       source_path: str; caption: str | None; figure_id: str | None
TableData:      cells: list[list[str]]; is_complex: bool; page_number: int
BlockQuote:     lines: list[str]; attribution: str | None; page_number: int; italic: bool
ListItem:       text: str; level: int; ordered: bool; marker: str | None
ListData:       items: list[ListItem]; page_number: int
CodeBlock:      lines: list[str]; page_number: int
CalloutBlock:   label: str; paragraphs: list[str]; page_number: int
MathBlock:      latex_or_text: str; display: bool; numbering: str | None; page_number: int
VerseBlock:     lines: list[str]; attribution: str | None; is_quoted: bool; page_number: int
GlossaryBlock:  items: list[GlossaryItem]; page_number: int
GlossaryItem:   term: str; definition: str; page_number: int
Footnote:       marker: str; text: str; page_number: int; style: "page_bottom" | "endnote"
```

**Known, deliberately-unfixed limitations** (see `RULES.md`/`ROADMAP.md`
for the full reasoning on each):
- Part/Book/Volume detection only works on the font-clustering heading
  path, not the bookmark-based one.
- A very short document with only one real heading can render as a single
  `Untitled` chapter with the title demoted to a sub-heading.
- Math detection only recovers the *text-layer* case (Unicode symbols
  already present) — a PDF built from real LaTeX usually draws equations
  as vector paths with no extractable Unicode at all.
- Vertical CJK text is detect-and-don't-corrupt only; there is no real
  vertical-layout reading order.

---

## Stage 4 — Rendering (`mdook/core/stages/rendering.py`)

**Input:** `DocumentTree` + `BookManifest` + output directory
**Output:** Files on disk (the Obsidian vault)

```
MyBook/
├── MyBook - Index.md          # YAML frontmatter + linked chapter list,
│                               #   grouped under "## {part_title}" headings
│                               #   when the book has Parts
├── 00 - Front Matter.md       # only written if front matter exists
├── 01 - Chapter One.md
├── 02 - Chapter Two.md
├── ...
├── Notes.md                  # dedicated back-matter notes (if present)
├── Bibliography.md           # dedicated bibliography/references (if present)
├── Glossary.md               # dedicated glossary (if present)
├── Appendix.md               # dedicated appendices (if present)
└── attachments/
    ├── fig-2-1.png
    └── ...
```

Content-type rendering, briefly:
- Page breaks → collapsed callouts: `> [!quote]- p. 142 · Book Title, Ch. 3`
- Footnotes → `[^n]`; endnotes and citations → wiki-links to a `^note-N` /
  `^ref-N` block anchor in the back-matter file (Obsidian footnotes are
  file-scoped, so a cross-file reference needs a real link, not `[^n]`)
- `CalloutBlock` → `> [!type] Label` (Obsidian renders any type name with a
  generic bordered style, even ones it doesn't specifically recognize —
  this is how "Note", "Warning", and theorem-environment labels like
  "Theorem 3.2" all render without inventing multiple box mechanisms)
- `MathBlock` → `$$...$$` (display) or `$...$` (inline) — Obsidian's native
  MathJax, not a custom fenced block
- Tables → markdown pipe tables (simple) or inline HTML (complex/merged
  cells)
- Images → `![[fig-3-2.png]]` with the caption (if any) on the next line

---

## Stage 5 — Validation (`mdook/core/stages/validation.py`)

**Input:** The rendered vault + `DocumentTree` + `list[PageData]`
**Output:** `ValidationReport`

```
ValidationReport:
  errors: list[str]
  warnings: list[str]
  total_pages: int
  total_chapters: int
  total_footnotes: int
  total_images: int
  ocr_pages: int                # real per-page count, from PageData.was_ocrd
  processing_time_seconds: float
```

Checks: footnote integrity (every marker has a definition and vice versa),
image integrity (every reference resolves to a file that exists), heading
hierarchy sanity, page continuity (front/back zone pages count as
covered), file size sanity.

---

## Interfaces: GUI & CLI

Mdook offers both a rich desktop graphical user interface and a headless command-line interface:

### Desktop GUI (`mdook/gui/`)
Launched via `mdook`, `mdook gui`, or `python -m mdook`:
- `window.py` — `MainWindow`: file pickers, drag-and-drop (multiple PDFs
  at once), a light/dark theme toggle, a real sequential queue (drop
  or queue several books; they convert one after another automatically),
  collapsible AI Structure Review settings panel, and a summary card
  that displays `ConversionResult` statistics and enables the "Open Vault" button.
- `worker.py` — `ConversionWorker`, `ConnectionTestWorker`, `ModelFetchWorker`:
  non-blocking `QThread` workers keeping the UI responsive.
- `queue_manager.py` — `QueueManager`/`QueueItem`: plain-Python queue state.
- `styles.py` — `DARK_STYLE`/`LIGHT_STYLE` QSS stylesheets.

### Headless CLI (`mdook/cli.py`)
Terminal-first and headless server automation:
- `mdook convert <pdf...> -o <vaults/> [--profile literature|technical] [--ai]`:
  converts books with Rich spinners, progress bars, and formatted validation summary tables.
- `mdook gui`: explicitly launches the PySide6 desktop GUI.
- `mdook --version` / `mdook version`: displays version information.
- Display-aware dispatch: running `mdook` with no arguments automatically opens the
  desktop GUI on graphical environments, while displaying help in headless/remote environments.

`ConversionResult` (returned by `convert()`, consumed by the GUI's
`conversion_finished` signal):

```
ConversionResult:
  success: bool
  output_dir: Path
  manifest: BookManifest | None
  validation_report: ValidationReport | None
  error_message: str | None
  pages: int; chapters: int; footnotes: int; images: int
```

---

## Project Source Structure

```
Mdook/
├── mdook/
│   ├── __init__.py
│   ├── __main__.py             # `python -m mdook` — launches the GUI
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── errors.py           # EncryptedPDFError, CorruptPDFError
│   │   ├── models.py           # every Pydantic schema in this file
│   │   ├── pipeline.py         # orchestrator — convert(), Stage 1→5
│   │   │
│   │   ├── stages/
│   │   │   ├── intake.py       # Stage 1
│   │   │   ├── extraction.py   # Stage 2
│   │   │   ├── semantic.py     # Stage 3
│   │   │   ├── rendering.py    # Stage 4
│   │   │   └── validation.py   # Stage 5
│   │   │
│   │   └── rules/              # pure detection logic, no I/O
│   │       ├── zones.py            # front/body/back matter detection
│   │       ├── headings.py         # heading detection & drop-cap immunity
│   │       ├── headers_footers.py  # running header/footer detection
│   │       ├── footnotes.py        # footnote/endnote detection & correlation
│   │       ├── paragraphs.py       # paragraph merging & boundary detection
│   │       ├── tables.py           # table classification & formatting
│   │       ├── images.py           # caption association & vector-diagram rasterization
│   │       ├── columns.py          # multi-column reading order (RTL-aware)
│   │       ├── lists.py            # bullet/numbered list detection
│   │       ├── code.py             # monospace-font code block detection
│   │       ├── callouts.py         # Note/Warning/etc. sidebar box detection
│   │       ├── citations.py        # numeric citation-to-bibliography linking
│   │       ├── math.py             # equation & theorem-environment detection
│   │       ├── scripts.py          # RTL / case-less script detection
│   │       ├── text_quality.py     # per-page OCR-routing quality score
│   │       └── ocr.py              # Tesseract wrapper & TextBlock normalization
│   │
│   ├── gui/
│   │   ├── window.py            # MainWindow
│   │   ├── worker.py            # ConversionWorker (QThread)
│   │   ├── queue_manager.py     # QueueManager / QueueItem
│   │   └── styles.py            # DARK_STYLE / LIGHT_STYLE
│   │
│   └── profiles/
│       ├── literature.toml
│       └── technical.toml       # see PROFILES.md's evolution note — most
│                                 #   newer rules don't actually read these yet
│
├── tests/                       # one test file per rule/stage module,
│                                 #   plus test_gui_window.py
│
├── Mdook-docs/                  # this folder
├── pyproject.toml
├── uv.lock
└── README.md
```

There is no `cli.py`, no `config.py`, no `ocr/` subpackage, and no `ai/`
subpackage — those were part of the original pre-implementation plan and
were superseded by the structure above.

---

## Data Flow Summary

```
PDF → [Intake] → BookManifest
                      │
                      ▼
PDF + Manifest → [Extraction] → list[PageData]
                                     │
                                     ▼
Manifest + Pages → [Semantic] → DocumentTree
                                     │
                                     ▼
DocumentTree → [Rendering] → Vault files on disk
                                     │
                                     ▼
Vault + Tree + Pages → [Validation] → ValidationReport
```

Each stage is independently testable — and is: `tests/` has dedicated
files per stage and per rule module (200+ tests as of Batch 19).
