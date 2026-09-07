# Roadmap

Concrete task breakdown by phase. Each task is scoped to a single coding session (1–4 hours). Tasks within a phase are ordered by dependency — do them in sequence.

---

## Phase 1 — Literary Books with Text Layer

**Goal:** Convert a literary PDF with embedded text into a readable Obsidian vault. No OCR, no tables, no multi-column.

### Sprint 1: Foundation

- [ ] **Project scaffold** — Set up `pyproject.toml`, package structure, Typer CLI skeleton, pytest config. Running `Mdook --help` should work.
- [ ] **Data models** — Define Pydantic schemas: `BookManifest`, `PageData`, `TextBlock`, `ImageBlock`, `DocumentTree`, `Chapter`, `Section`, `Paragraph`, `Footnote`. These are the contracts between stages.
- [ ] **Stage 1: Intake** — Open PDF with PyMuPDF. Extract metadata (title, author). Read bookmark tree. Check text layer on sample pages. Detect zones (front/body/back) using keyword scanning. Output a `BookManifest`.

### Sprint 2: Extraction & Basic Semantics

- [ ] **Stage 2: Extraction** — For each page, extract all text blocks with font info and positions. Group spans into `TextBlock` objects. Extract embedded images. Output `list[PageData]`.
- [ ] **Header/footer detection** — Implement Rule 3.1 (repeating band detection) and Rule 3.2 (page number extraction). Strip headers/footers from content blocks.
- [ ] **Heading detection (bookmark path)** — Implement Rule 2.1. When bookmarks exist, map them directly to heading levels. Test on a PDF that has bookmarks.
- [ ] **Heading detection (font path)** — Implement Rules 2.2 and 2.3. Font-size clustering + positional confirmation. Test on a PDF without bookmarks.

### Sprint 3: Content Processing

- [ ] **Paragraph merging** — Implement Rules 5.1–5.4. Same-font continuation, hyphen rejoin, cross-page continuation, paragraph boundary detection.
- [ ] **Footnote detection** — Implement Rules 4.1–4.2. Page-bottom footnotes with superscript marker correlation.
- [ ] **Drop cap handling** — Implement Rule 2.5. Single oversized character merged back into first paragraph.
- [ ] **Special content** — Implement Rules 9.1 (epigraphs), 9.4 (printed TOC discard), 9.5 (decorative element filtering).

### Sprint 4: Rendering & Validation

- [ ] **Stage 4: Rendering** — Walk the `DocumentTree` and emit markdown files. Index/MOC file with YAML frontmatter. Chapter files with heading hierarchy. Page markers as collapsed callouts. Footnotes as `[^n]` syntax. Image references.
- [ ] **Stage 5: Validation** — Footnote integrity check, image integrity check, heading hierarchy sanity, page continuity, file size warnings.
- [ ] **End-to-end test** — Pick 3 literary PDFs. Run the full pipeline. Read the output in Obsidian. Fix bugs until the vaults are genuinely pleasant to read.

### Phase 1 Exit Criteria

- [ ] 5 different literary books converted successfully
- [ ] Output is readable cover-to-cover in Obsidian without jarring formatting artifacts
- [ ] An AI (Claude) given a chapter file can discuss its content coherently
- [ ] CLI works: `Mdook convert book.pdf --output ./vault/`

---

## Phase 2 — Technical Profile

**Goal:** Handle textbooks and technical books with tables, figures, multi-column layouts, and numbered section headings.

- [ ] **Technical profile config** — Create `technical.toml` with profile-specific tuning parameters
- [ ] **Numbered section detection** — Implement Rule 2.4. Regex matching for `1.1.2` style headings.
- [ ] **Table extraction** — Integrate pdfplumber. Implement Rules 6.1–6.4. Simple markdown tables + complex HTML fallback + caption association.
- [ ] **Image/figure handling** — Implement Rules 7.1–7.5. Embedded image extraction, vector diagram rasterization, caption association, decorative filtering, meaningful filenames.
- [ ] **Multi-column support** — Implement Rules 8.1–8.3. Column detection, per-column sorting, column-spanning elements.
- [ ] **Code block detection** — Monospaced font detection → fenced code blocks.
- [ ] **Endnote path** — Implement Rules 4.3–4.4. Back-of-book endnotes with chapter-scoped numbering and block reference links.
- [ ] **End-to-end test** — 3 technical PDFs. Tables render correctly. Figures extracted with captions. Code blocks formatted.

---

## Phase 3 — OCR Fallback

**Goal:** Handle scanned books where no text layer exists.

**Engine decision (superseding the original plan below): Tesseract, not Marker.** Chosen for a CPU-only environment — Tesseract's plain word+bbox output maps directly onto Mdook's existing `TextBlock` shape, so OCR'd pages become "a noisier native page" to the existing Stage 2/3 pipeline rather than a second structural format needing reconciliation. Marker (PyTorch, full layout/table model) remains a possible future *optional* engine for anyone with a GPU, not the default.

- [x] **Text layer quality check** — Per-page quality score (character count, Unicode validity, word-likeness heuristic) in `mdook/core/rules/text_quality.py`. Below threshold → route to OCR.
- [x] **Tesseract integration** — `mdook/core/rules/ocr.py` wraps `pytesseract`, rasterizing a page and grouping its word-level output into lines.
- [x] **OCR output normalization** — Tesseract's output maps directly into Mdook's own `TextBlock` schema (font size approximated from box height; bold/italic/superscript unavailable, default False) — every existing Stage 3 rule (headings, footnotes/endnotes, lists, tables, columns) runs unchanged on OCR'd pages.
- [x] **Hybrid routing** — Per-page decision in `mdook/core/stages/extraction.py`: native PyMuPDF text is scored first; only a page that scores below threshold gets re-extracted via OCR. `PageData.was_ocrd` records which path each page took; `ValidationReport.ocr_pages` reports a real per-page count.
- [x] **End-to-end test** — A real 5-page, fully scanned pamphlet (0 native characters/page) from the user's collection converted successfully through the actual pipeline (not just unit tests). This surfaced two genuine Stage 3 degradations that no synthetic fixture had caught:
  - **Chapter-title corruption**: OCR font size is approximated from each line's own bbox height (`mdook/core/rules/ocr.py`), which jitters several points from ordinary ascender/descender variation. An unlucky tall body line at the top of a page routinely tier-matched as a "heading" and got promoted to a chapter title — mid-sentence garbage like `# jecting me to denunciations in speeches and resolutions`. Fixed in `mdook/core/rules/headings.py`'s `_confirm_heading`: for an OCR'd page, the uppercase signal is now mandatory rather than one-of-several, since it's the only Rule 2.3 signal OCR doesn't degrade (`is_bold` is always False for OCR text).
  - **Running headers leaking into every page's body**: `mdook/core/rules/headers_footers.py` grouped repeated headers by exact normalized-text match, which never fires for OCR'd text — Tesseract misreads a few characters differently on every page (`"THURLOW WEED ON..."` vs `"THURLOW WEED GN..."` vs `"...WHED ON..."`). Fixed by clustering candidates with `difflib.SequenceMatcher` similarity (≥0.82) instead of exact equality. Separately, the header/footer band ratio (`TOP_BAND_RATIO`/`BOTTOM_BAND_RATIO`) was widened from 0.08 to 0.15 — a scanned page's canvas routinely has a wider blank border than a tightly-cropped native PDF, and the real book's header measured 9-13% down from the top, just outside the old band.
  - Both fixes are covered by new regression tests (`tests/test_headings.py`, `tests/test_headers_footers.py`, the latter previously untested at all).
- [x] **End-to-end test** — A real 5-page, fully scanned pamphlet (0 native characters/page) from the user's collection converted successfully through the actual pipeline. 
- [x] **GUI progress granularity** — `mdook/core/stages/extraction.py`'s `run_extraction` now takes an `on_page_extracted(done, total)` callback, fired after each page; `mdook/core/pipeline.py` maps it into the 25-50% band so a multi-minute OCR pass reports real per-page progress.

---

### Advanced Structural & Robustness Hardening (Complete)

**Goal:** Provide general-purpose book conversion handling complex structural divisions, citations, vector graphics, mathematical notation, and non-Latin scripts.

- [x] **Parts/Books/Volumes + callout/sidebar boxes** — Divisions above the chapter tier are recorded on `Chapter.part_title` and grouped in the Index/MOC file under a `## {part_title}` heading. Callout and sidebar boxes ("Note:", "Warning.", ...) are extracted as `CalloutBlock` and rendered as Obsidian callouts (`mdook/core/rules/callouts.py`, Rule 13.2).
- [x] **Citation-to-bibliography linking** — Numeric citations (`[1]`, `[1, 3]`, `[1-4]`) link to their matching Bibliography/References entry via sentinels resolved during Stage 4 rendering (`mdook/core/rules/citations.py`), including `^ref-N` block anchors on the bibliography's numbered entries.
- [x] **Image & figure completion** — Caption association (`mdook/core/rules/images.py`'s `find_caption`) checks both above and below an image for labeled text blocks, populating `ImageBlock.caption` and deriving figure-numbered attachment filenames. Vector diagram rasterization clusters `page.get_drawings()` rects via union-find algorithms.
- [x] **Math & formal notation** — Display and inline equations render through Obsidian's native MathJax (`$$...$$`/`$...$`), detected via Unicode symbol-density scoring (`mdook/core/rules/math.py`); theorem environments reuse `CalloutBlock` rendering.
- [x] **Non-Latin script & RTL/bidi robustness** — Script detection (`mdook/core/rules/scripts.py`) reorders multi-column reading order right-to-left when the page's dominant script is RTL (Hebrew/Arabic), and exempts caseless scripts from uppercase heading constraints.
- [x] **Pathological PDF robustness** — Fast-fail error handling for encrypted or corrupt PDFs (`EncryptedPDFError`, `CorruptPDFError`). Intentionally blank pages skip OCR, and duplicate overlapping text layers are deduplicated.

---

## Phase 4 — Multi-Format Input Support (Complete)

**Goal:** Handle EPUB3 and DOCX manuscripts by parsing structured markup directly into `DocumentTree`, bypassing the PDF-specific heuristic pipeline. Stage 4 (Rendering) and Stage 5 (Validation) consume `DocumentTree` regardless of source with zero format-specific changes.

- [x] **Format detection & pipeline branch** — `mdook.core.pipeline.convert()` detects input format by extension (`.pdf`, `.epub`, `.docx`) and routes to the right intake path.
- [x] **EPUB container parsing** — Uses `ebooklib` to open `.epub` archives, reading the OPF manifest/spine and Dublin Core metadata (title, author, ISBN, publisher, date).
- [x] **Navigation/TOC parsing** — Parses `nav.xhtml` (EPUB3) and `toc.ncx` (EPUB2) directly into chapter bookmarks hierarchy.
- [x] **XHTML content mapping** — Walks each spine document's DOM (`BeautifulSoup`) and maps tags directly to `DocumentTree` content types: `<h1>`–`<h6>` (chapter/section hierarchy), `<p>` (paragraphs with bold, italic, code, links), `<blockquote>` (with attributions), `<ul>`/`<ol>` (lists with items), `<table>` (tables with merged-cell complexity detection), `<pre>`/`<code>` (code blocks), `<img>` (image references), `<aside>` (callouts), and `<math>` (formal notation).
- [x] **Footnote/endnote mapping** — EPUB3's semantic footnote convention (`epub:type="footnote"`/`"noteref"` and `<a href="#fnN">`) maps directly into `Footnote` objects and inline sentinels.
- [x] **Front/back matter mapping** — Where an EPUB marks matter type via structural semantics vocabulary (`epub:type="frontmatter"`, `"backmatter"`), maps it directly; falls back to keyword matching (`FRONT_MATTER_LABELS`/`BACK_MATTER_LABELS`).
- [x] **DOCX manuscript support** — Implemented in `mdook/core/formats/docx.py`. Maps Word styles (Heading 1–6, Quote, Lists, Code), inline runs (bold, italic, strikethrough, monospace, hyperlinks), Word tables (with merged cell complexity), embedded drawings/blips, and footnotes (`word/footnotes.xml`).
- [x] **End-to-end multi-format tests** — Tested end-to-end with unit and integration tests across PDF, EPUB, and DOCX.

### Phase 4 Exit Criteria

- [x] EPUB3 books convert to the same vault structure/quality as PDF books
- [x] Stage 4/5 required zero format-specific changes (confirms `DocumentTree` is a true format-agnostic contract)
- [x] Architecture documented and extended for DOCX manuscript support

---

## Phase 5 — Polish & Edge Cases

**Goal:** Harden the pipeline, add optional AI review, handle remaining edge cases.

- [x] **AI structure review** — Implemented in Phase 5 via `mdook/core/llm/`. Uses a zero-dependency standard library client (`urllib.request`) targeting the universal OpenAI-compatible chat-completions endpoint (`/v1/chat/completions`) compatible with OpenAI, Ollama, LM Studio, vLLM, Groq, OpenRouter, and DeepSeek. Serializes detected heading candidates into a compact, token-efficient text skeleton (~200–500 tokens) with opening body snippets. The LLM acts strictly as a reviewer returning a JSON diff of validated corrections (`demote_to_body`, `set_level`, `set_part`). Guardrails reject out-of-bounds IDs, invalid levels, or 100% book demotions. Degrades gracefully to deterministic heuristic rules if offline, timed out, or errored. Integrated into Stage 3 before chapter segmentation, tracked in `ValidationReport` and `ConversionResult`, and configurable via environment variables and desktop GUI controls (including non-blocking background connection testing with millisecond latency feedback, dynamic `/models` discovery with live searchable substring filtering, and a collapsible disclosure arrow indicator `▾` / `▸`).
- [x] **Poetry/verse handling** — Implemented Rule 9.2 in Phase 5 via `mdook/core/rules/verse.py`. Detects verse stanzas and multi-stanza poems before paragraph merging, preserving exact line breaks via markdown double trailing spaces (`  \n`) and rendering indented/quoted poems in Obsidian blockquotes (`> `). Features stanza-gap clustering, font styling continuity, dialogue and glossary guards, and a terminal punctuation discriminator to avoid false positives on short prose sentences. Supports inline footnote markers and trailing author attributions (`— Robert Frost`). Integrated into `mdook/core/stages/semantic.py` and `mdook/core/stages/rendering.py`.
- [x] **Block quote handling** — Implemented in `mdook/core/rules/*` via `semantic.py`'s `_looks_like_block_quote` for epigraphs and indent-based quotations.
- [x] **Glossary processing** — Implemented Rule 9.6 in Phase 5 via `mdook/core/rules/glossary.py`. Detects term-definition pairs via font-styling (bold terms), delimiter patterns (colon, em-dash, en-dash), and hanging indent geometry. Formats entries as clean `**Term** — Definition` paragraphs in dedicated `Glossary.md` notes. Preserves alphabetical letter dividers (A, B, C...) as level-2 markdown sub-headings (`## A`), supports multi-line definition merging with hyphenation rejoining, splices inline footnote and citation sentinels within definitions, preserves introductory text as standard paragraphs, and provides a graceful fallback for unstructured narrative sections.
- [x] **Bibliography processing & back-matter file splitting** — Completed in Phase 5. Back matter is split into dedicated markdown notes per section (`Bibliography.md`, `Notes.md`, `Glossary.md`, `Appendix.md`, etc.) instead of a shared single file. Spliced numeric citations link directly to `[[Bibliography#^ref-N|N]]` and endnotes link to `[[Notes#^note-N|N]]`. The index note groups and links each dedicated back-matter file under a `## Back Matter` section. Includes automatic collision deduplication (e.g. `Appendix 2.md`) and hierarchical preservation of sub-sections under their parent note.
- [x] **Symbol footnote handling** — Implemented in `mdook/core/rules/footnotes.py`: `DEFINITION_MARKER_RE` matches `*`, `†`, `‡`, `§`, `¶` alongside numeric markers.
- [x] **Profile auto-detection** — Implemented heuristic profile classifier (`mdook/core/rules/profiles.py`) evaluating table density, numbered section headings (`1.1`, `1.2.3`), code blocks, and math density. Integrated into Stage 1 / Intake, Headless CLI (`-p auto`), and Desktop GUI ("Auto-Detect" dropdown default).
- [ ] **Custom profile support** — Allow users to pass a `.toml` override file.
- [x] **Rich CLI output & headless converter** — Implemented via `mdook/cli.py`. Supports `mdook convert <pdf...> -o <output_dir>` with Rich progress bars, colored status messages, and formatted summary/validation tables. Automatically launches the Desktop GUI when run without arguments on graphical displays, while gracefully providing CLI help in headless environments. Also provides `mdook version` and `mdook gui`.
- [x] **Documentation** — Comprehensive README with installation, usage examples, visual GUI guide, configuration table, architecture overview, and `CONTRIBUTING.md` guidelines.
- [x] **GitHub release preparation** — MIT `LICENSE`, `CHANGELOG.md` (Keep a Changelog standard), enriched `pyproject.toml` metadata, expanded `.gitignore`, and GitHub Actions CI workflow (`.github/workflows/ci.yml`).

---

## Phase 6 (Future) — Distribution

- [x] **Obsidian plugin** — Official desktop plugin in `obsidian-plugin/` enabling in-vault book conversions (.pdf, .epub, .docx), folder batching, destination picker, context menus, and status bar progress.
- [ ] **Web service** — Upload endpoint, conversion queue, vault download.
- [x] **Math/formula support** — Unicode-symbol-density-detected equations rendered via Obsidian's native MathJax (`mdook/core/rules/math.py`). Real LaTeX-drawn vector-path equations (no extractable Unicode) remain out of scope by design (see `RULES.md` section 15).
- [~] **Batch processing** — The GUI queue converts several dropped/queued books sequentially in one run. Future extension: pointing at an entire directory tree and converting everything in it recursively.
- [ ] **Per-section profile switching** — Literary chapters + technical appendix in the same book
- [ ] **Additional format backends** — MOBI/AZW3, plain HTML, following the Phase 4 pattern

---

## Testing Strategy Across Phases

### Test Library

Build a curated collection of PDFs (and, from Phase 4 on, EPUBs) covering known edge cases:

| Book Type                       | Tests                                                    |
| ------------------------------- | -------------------------------------------------------- |
| Novel (simple, with bookmarks)  | Heading detection via bookmarks, basic paragraph flow    |
| Novel (no bookmarks, drop caps) | Font-based heading detection, drop cap immunity          |
| Annotated literary edition      | Heavy footnotes, translator's notes, editorial apparatus |
| History/biography               | Endnotes, bibliography, index, image plates              |
| Textbook (numbered sections)    | 1.1.2 headings, tables, figures, code blocks             |
| Academic monograph              | Multi-column, dense citations, complex tables            |
| Poetry anthology                | Verse formatting, short headings, epigraphs              |
| Scanned novel (OCR test)        | Text layer quality detection, OCR fallback               |
| Scanned textbook (OCR test)     | OCR + table/figure handling together                     |
| EPUB3 novel                     | Tag-based mapping vs. the PDF heuristic path, nav.xhtml TOC |
| EPUB3 with footnotes/endnotes   | `epub:type="footnote"`/`"noteref"` mapping                |

### Regression Rule

Every bug fix includes a test case. Every new PDF that exposed a problem gets added to the test library. The test suite must pass before any release.
