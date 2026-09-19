# Architecture

Mdook is designed around a clean, typed contract architecture where pipeline stages
produce and consume strongly typed Pydantic models (`mdook/core/models.py`).
The system supports both deterministic PDF extraction through a 5-stage pipeline
and direct structured ingestion for EPUB3 and DOCX formats into `DocumentTree`.

---

## Pipeline Overview

Mdook processes documents through a format-aware pipeline:

- **PDF Documents**: Routed through the 5-stage sequential heuristic pipeline.
- **EPUB3 Publications**: Directly parsed via `mdook/core/formats/epub.py` into `DocumentTree`.
- **DOCX Manuscripts**: Directly parsed via `mdook/core/formats/docx.py` into `DocumentTree`.

Stages 4 (Rendering) and 5 (Validation) consume `DocumentTree` and `BookManifest`
identically across all input formats with zero format-specific branching.

```
Input File (.pdf / .epub / .docx)
   │
   ├── [PDF] ──► Stage 1 (Intake) ──► Stage 2 (Extraction) ──► Stage 3 (Semantics)
   │                                                                 │
   ├── [EPUB] ─► ebooklib / bs4 Direct Mapping to DocumentTree ──────┤
   │                                                                 │
   └── [DOCX] ─► python-docx / OpenXML Direct Mapping to DocumentTree ┤
                                                                     ▼
                                                         Stage 4 (Rendering & Output Generation)
                                                                     │
                                                                     ▼
                                                         Stage 5 (Validation Audit)
                                                                     │
                                                                     ▼
                                                         Structured Markdown Output (Modular Library or Single Document)
```

`mdook/core/pipeline.py`'s `convert()` orchestrates the pipeline and reports progress
via a plain `on_progress(percent, message) -> None` callback. Both the PySide6 GUI
(`mdook/gui/worker.py`'s `ConversionWorker`) and the headless CLI (`mdook/cli.py`)
consume this callback.

---

## Stage 1 — Intake (`mdook/core/stages/intake.py`)

**Input:** PDF file path + optional profile override (`auto`, `literature`, `technical`)
**Output:** `BookManifest`

- Opens the PDF with PyMuPDF. Fails fast with a clear, typed error
  (`mdook.core.errors.EncryptedPDFError` / `CorruptPDFError`) rather than
  producing garbage or an opaque traceback if the file is password-protected or corrupt.
- Samples pages to flag `needs_ocr` (a whole-book estimate; per-page OCR routing
  occurs in Stage 2).
- Extracts the PDF's own bookmark/outline tree (`doc.get_toc()`) — the preferred source
  for heading hierarchy when available (Rule 2.1).
- Detects zones (front matter / body / back matter) via `mdook.core.rules.zones`.
- **Profile Auto-Detection (`mdook/core/rules/profiles.py`)**: When profile is `auto` (default),
  evaluates structural signals across sampled pages (table density, numbered section headings
  `1.1`, monospaced code blocks, and math symbol density) to automatically classify the document
  as `technical` or `literature`.

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
(17 numbered rule sections). Summary of what happens, in
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

**Input:** `DocumentTree` + `BookManifest` + output directory + `output_mode`
**Output:** Files on disk (Modular Library or Single Document)

Mdook supports two distinct output architectures:

### Mode 1: Modular Library (Default)

Emits a multi-file structured knowledge library:

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

### Mode 2: Single Document (`-s` / `--single-file`)

Emits a complete, verbatim 1:1 continuous Markdown document (`Title.md`) with attachments:

```
MyBook/
├── MyBook.md                  # Complete continuous manuscript
└── attachments/
    ├── fig-2-1.png
    └── ...
```
- **Standard Image Links**: Uses universal markdown syntax (`![caption](attachments/fig.png)`).
- **Intra-Document Anchors**: Footnotes and citations link locally via `[[#^note-1|1]]` and `[[#^ref-1|1]]`.
- **Consolidated Footnotes**: Deduplicates marker collisions across chapters and collects all notes into a document-level `## Footnotes` section.

### Content-Type Rendering Details

- Page breaks → collapsed callouts: `> [!quote]- p. 142 · Book Title, Ch. 3`
- Footnotes → `[^n]`; endnotes and citations → wiki-links to a `^note-N` /
  `^ref-N` block anchor in the back-matter file (standard footnotes are
  file-scoped, so a cross-file reference needs a real link, not `[^n]`)
- `CalloutBlock` → `> [!type] Label` (standard callout syntax)
- `MathBlock` → `$$...$$` (display) or `$...$` (inline) — standard LaTeX math syntax
- Tables → markdown pipe tables (simple) or inline HTML (complex/merged
  cells)
- Images → `![[fig-3-2.png]]` (library mode) or `![caption](attachments/fig.png)` (single-doc mode)

---

## Stage 5 — Validation (`mdook/core/stages/validation.py`)

**Input:** The rendered output directory + `DocumentTree` + `list[PageData]`
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

## Interfaces: GUI, CLI & Wizard

Mdook offers a rich desktop graphical user interface, a headless command-line interface, and an interactive terminal wizard:

### Desktop GUI (`mdook/gui/`)
Launched via `mdook`, `mdook gui`, or `python -m mdook`:
- `window.py` — `MainWindow`: file inspection card, segmented output format toggle (`Modular Library` vs `Single Document`), sequential queue, 5-stage breadcrumbs, and "Open Output / Note" action.
- `settings_dialog.py` — `SettingsDialog`: modal settings interface for theme palette selection, conversion defaults, and live AI provider configuration.
- `theme.py` — 3 theme families (*The Library*, *Amethyst*, *Carbon*) across dark and light modes with tokenized stylesheet generation.
- `config.py` — `GUIConfig` model and JSON persistence (`~/.config/mdook/gui_config.json`).
- `worker.py` — `ConversionWorker`, `ConnectionTestWorker`, `ModelFetchWorker`: non-blocking `QThread` workers keeping the UI responsive.
- `queue_manager.py` — `QueueManager`/`QueueItem`: plain-Python queue state.

### Headless CLI (`mdook/cli.py`)
Terminal-first and headless server automation:
- `mdook convert <path...> -o <output/> [--single-file] [--profile literature|technical] [--ai]`:
  converts books with Rich spinners, progress bars, and formatted validation summary tables.
- `mdook scan [path] [-r] [-v]`: publication scanner identifying and inspecting supported documents (`.pdf`, `.epub`, `.docx`) across directories with metadata, page counts, and sizes.
- `mdook interactive` / `mdook -i`: rich interactive terminal wizard guiding directory scanning, document selection, format toggle (modular library or single document), destination folder, profile, and execution.
- `mdook gui`: explicitly launches the PySide6 desktop GUI.
- `mdook --version` / `mdook version`: displays version information.
- Display-aware dispatch: running `mdook` with no arguments automatically opens the
  desktop GUI on graphical environments, while displaying help in headless/remote environments.

### Interactive CLI Wizard (`mdook/cli_wizard.py`)
- Step-by-step interactive terminal wizard powered by Questionary and Rich.
- Guides users through directory scanning, multi-book selection, format mode toggle (`Modular Library` vs `Single Document`), destination folder configuration, profile selection, and AI structure review options.
- Dispatches directly into `mdook/core/pipeline.py` with live terminal progress reporting.

### Publication Scanner Engine (`mdook/core/scanner.py`)
- Traverses local filesystems recursively (`-r`) or shallowly to discover supported publications (`.pdf`, `.epub`, `.docx`).
- Extracts lightweight pre-flight metadata (title, author, page count, file size) without running the full extraction pipeline.
- Returns structured `DiscoveredBook` models for ingestion by the interactive wizard, batch CLI commands, or GUI queue.

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
│   ├── __main__.py             # Entry point dispatch (GUI or CLI)
│   ├── cli.py                  # Headless CLI entry point (convert, scan, interactive)
│   ├── cli_wizard.py           # Interactive terminal wizard
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── errors.py           # Typed error definitions (EncryptedPDFError, etc.)
│   │   ├── models.py           # Pydantic contracts across stages
│   │   ├── pipeline.py         # Pipeline orchestrator: convert(), Stage 1→5
│   │   ├── scanner.py          # Directory publication scanner engine
│   │   │
│   │   ├── formats/            # Non-PDF format direct ingestion
│   │   │   ├── epub.py         # EPUB3 container, TOC, XHTML & footnote mapping
│   │   │   └── docx.py         # Word OpenXML styles, runs, tables, & footnotes
│   │   │
│   │   ├── llm/                # OpenAI-compatible AI review client & prompts
│   │   │   ├── client.py       # Zero-dependency urllib HTTP client
│   │   │   └── prompts.py      # Outline review schema & prompt templates
│   │   │
│   │   ├── stages/             # 5 pipeline stage orchestrators
│   │   │   ├── intake.py       # Stage 1: metadata, bookmarks, zone detection
│   │   │   ├── extraction.py   # Stage 2: blocks, tables, images, Tesseract OCR
│   │   │   ├── semantic.py     # Stage 3: headings, notes, verse, glossaries
│   │   │   ├── rendering.py    # Stage 4: modular library or single-doc rendering
│   │   │   └── validation.py   # Stage 5: integrity audits & validation reports
│   │   │
│   │   └── rules/              # Pure semantic detection heuristics (no I/O)
│   │       ├── zones.py        # Front/body/back matter detection
│   │       ├── headings.py     # Heading detection & drop-cap immunity
│   │       ├── headers_footers.py # Running header/footer clustering
│   │       ├── footnotes.py    # Footnote/endnote detection & correlation
│   │       ├── paragraphs.py   # Paragraph merging & boundary detection
│   │       ├── tables.py       # Table classification & formatting
│   │       ├── images.py       # Caption association & diagram rasterization
│   │       ├── columns.py      # Multi-column reading order (RTL-aware)
│   │       ├── lists.py        # Bullet and numbered list detection
│   │       ├── code.py         # Monospace-font code block detection
│   │       ├── callouts.py     # Note/Warning/Tip sidebar box detection
│   │       ├── citations.py    # Numeric citation-to-bibliography linking
│   │       ├── math.py         # Equation & theorem-environment detection
│   │       ├── scripts.py      # RTL / case-less script detection
│   │       ├── text_quality.py # Per-page OCR-routing quality score
│   │       ├── ocr.py          # Tesseract wrapper & TextBlock normalization
│   │       ├── verse.py        # Poetry/verse line break & stanza preservation
│   │       ├── glossary.py     # Term-definition pair & divider extraction
│   │       └── profiles.py     # Heuristic auto-profile detection
│   │
│   └── gui/                    # PySide6 desktop GUI
│       ├── window.py           # MainWindow layout & widgets
│       ├── settings_dialog.py  # Modal SettingsDialog & AI test
│       ├── theme.py            # 3 theme families & stylesheet generation
│       ├── config.py           # GUIConfig JSON persistence
│       ├── queue_manager.py    # Sequential queue state
│       └── worker.py           # Background QThread workers
│
├── packaging/                  # Standalone distribution & OS integration
│   └── linux/
│       ├── install-desktop.sh  # Desktop entry & mime-type installer
│       ├── mdook.desktop       # FreeDesktop entry
│       └── mdook.svg           # Application vector icon
│
├── mdook.spec                  # PyInstaller standalone build specification
├── obsidian-plugin/            # Official Obsidian desktop companion plugin
│   ├── main.ts
│   ├── manifest.json
│   └── package.json
│
├── tests/                      # Pytest test suite (324 passing tests)
├── Mdook-docs/                 # Architectural specifications & rules catalog
├── pyproject.toml
├── uv.lock
└── README.md
```

---

## Multi-Format Ingestion Architecture

Non-PDF formats (`.epub`, `.docx`) bypass PDF-specific Stages 1–3 (intake heuristics,
PyMuPDF extraction, and font-size clustering). Instead, format-specific ingestion modules
in `mdook/core/formats/` parse the container markup and populate `BookManifest` and
`DocumentTree` directly:

- **EPUB3 (`mdook/core/formats/epub.py`)**: Uses `ebooklib` to read the container, OPF manifest,
  and spine. Parses navigation documents (`nav.xhtml`/`toc.ncx`) into chapter bookmarks,
  extracts embedded image assets, and maps XHTML tags (`h1-h6`, `p`, `blockquote`, `table`,
  `pre/code`, `aside`, `math`) directly to `DocumentTree` content types.
- **DOCX (`mdook/core/formats/docx.py`)**: Uses `python-docx` and OpenXML ZIP parsing to read
  document properties, styles (Headings 1–6, Quote, Lists, Code), inline runs (bold, italic,
  monospace code, hyperlinks), Word tables (with merged-cell complexity classification),
  embedded drawings/blips, and footnotes (`word/footnotes.xml`).

Both ingestion modules feed their output directly into **Stage 4 (Rendering)** and
**Stage 5 (Validation)**, verifying that `DocumentTree` serves as a true format-agnostic
contract for Markdown library generation.

---

## Data Flow Summary

```
PDF Document  ──► [Stage 1: Intake] ──► [Stage 2: Extraction] ──► [Stage 3: Semantics] ──┐
EPUB3 Book    ──► [formats/epub.py: Ingestion] ──────────────────────────────────────────┼──► DocumentTree + BookManifest
DOCX File     ──► [formats/docx.py: Ingestion] ──────────────────────────────────────────┘           │
                                                                                                     ▼
                                                                                       [Stage 4: Rendering & Output Generation]
                                                                                                     │
                                                                                                     ▼
                                                                                       [Stage 5: Validation Audit]
                                                                                                     │
                                                                                                     ▼
                                                                                       Structured Markdown Output (Modular Library or Single Document)
```

---

## Obsidian Desktop Companion Plugin Architecture

The official Obsidian companion plugin (`obsidian-plugin/`) runs directly within Obsidian's Electron desktop runtime, providing in-app book conversions without external application switching.

### 1. Execution Model & IPC Bridge
- **Zero Cloud Dependencies**: Operates 100% locally and privately. No network servers, external proxies, or subscriptions are required.
- **Asynchronous Child Process**: Spawns `mdook convert` via Node.js `child_process.spawn`. Runs completely in the background so Obsidian's UI, editing, and indexing remain fully responsive.
- **Dynamic Binary Resolver (`resolver.ts`)**: Discovers the local `mdook` CLI engine by probing:
  1. Explicit user path configured in plugin settings.
  2. System `$PATH` entries.
  3. Standard user installation locations (`~/.local/bin/mdook`, `~/.cargo/bin/mdook`, `/usr/local/bin/mdook`).
  4. Project virtual environments and `uv run mdook` wrappers.

### 2. Streaming Progress & Status Bar
- Listens to the spawned CLI's `stdout` and `stderr` streams in real time.
- Regex pattern matchers identify stage transitions (`Stage 1/5: Intake` through `Stage 5/5: Validation`) and calculate a continuous percentage score (0% to 100%).
- Displays live status in an interactive Obsidian status bar item (`Mdook: Dune.epub [60%]`) and modal progress bars.

### 3. Non-Destructive Ingestion
- **Preservation of Source Material**: The original `.pdf`, `.epub`, or `.docx` file is left untouched in its existing location.
- **Configurable Destination**: Output can be routed to a global default directory (e.g. `Books/`) or chosen on each conversion via the interactive modal.
- **Automatic Navigation**: On successful conversion, the plugin triggers an Obsidian filesystem refresh and automatically opens the newly generated book Index note (`Title - Index.md`) in a new editor tab.

---

## Standalone Packaging & Desktop Integration Architecture

Mdook provides a standalone binary packaging layer enabling distribution without requiring a pre-existing Python environment:

### 1. PyInstaller Standalone Build (`mdook.spec`)
- Freezes Python 3.12, PySide6 Qt binaries, PyMuPDF, and all dependencies into a standalone distribution directory (`dist/mdook/`).
- Includes application metadata, icons, and dynamic shared library bindings.

### 2. Linux Desktop Integration (`packaging/linux/`)
- **Desktop Entry (`mdook.desktop`)**: Registers Mdook in application launchers and desktop environments.
- **MIME Associations**: Associates Mdook with `.pdf` (`application/pdf`), `.epub` (`application/epub+zip`), and `.docx` (`application/vnd.openxmlformats-officedocument.wordprocessingml.document`).
- **Installer Script (`install-desktop.sh`)**: Deploys the desktop launcher and scalable SVG icon into user (`~/.local/share/applications`) or system (`/usr/share/applications`) paths.

