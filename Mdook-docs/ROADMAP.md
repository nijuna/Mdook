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
- [x] **GUI progress granularity** — `mdook/core/stages/extraction.py`'s `run_extraction` now takes an `on_page_extracted(done, total)` callback, fired after each page; `mdook/core/pipeline.py` maps it into the 25-50% band so a multi-minute OCR pass reports real per-page progress instead of sitting at a flat 25% until the whole stage finishes.
- [ ] **Signal-fusion enhancement (future, deliberately deferred)** — Cross-reference an OCR/layout tool's own structure detection (e.g. Marker/Surya's layout model) as an *additional confidence signal* feeding into Mdook's existing heuristics, rather than replacing them — an ensemble-style refinement once real OCR'd-book test data shows which signals are actually worth fusing. Requires the normalize-to-`TextBlock` step above as a prerequisite either way.
- [ ] **Known limitation (not fixed):** `_pick_chapter_tier` in `mdook/core/stages/semantic.py` requires a font-size tier to recur across multiple headings before it's trusted as "chapter level," falling back to tier 1 otherwise. A very short scanned document with only one real heading (e.g. a single-chapter pamphlet/letter) can fail that bar and render as one `Untitled` chapter with the real title demoted to a sub-heading — a correct improvement over the garbage-title bug above (better to lose a title than corrupt one), but still imperfect. Low priority: real multi-chapter books have enough headings to satisfy the existing threshold normally.

---

## Batches 14-19 — Remaining Structural, Content & Robustness Gaps (Complete)

**Goal:** Mdook is a general-purpose converter for *any* book, not tuned to one library — these batches close real gaps found by auditing `Mdook-docs/BOOK_ELEMENTS.md`'s full catalog against the actual codebase after Batch 13. Full plan: `/home/azzy/.claude/plans/federated-napping-toast.md`.

**Per the user's explicit sequencing decision, Phase 4 (EPUB3/multi-format support) is deferred after this** — next up is Phase 5 (Polish, Edge Cases & Design) below, followed by a GitHub push.

- [x] **Batch 14 — Parts/Books/Volumes + callout/sidebar boxes** (Tier A). A Part/Book/Volume division above the chapter tier is recorded on `Chapter.part_title` and grouped in the Index/MOC file under a `## {part_title}` heading (font-clustering path only; bookmark-based books are a known gap — see `Mdook-docs/RULES.md` Rule 13.1). Discovered and fixed a real ambiguity in `_pick_chapter_tier` along the way: pure tier-occurrence counts can't distinguish "2 Parts, 4 Chapters" from "4 Chapters, 40 Subheadings," so tier selection now also checks whether a tier's own heading text reads as a Part/Book/Volume label (`PART_LABEL_RE`). Callout/sidebar boxes ("Note:", "Warning.", ...) are extracted as `CalloutBlock` and rendered as Obsidian callouts (`mdook/core/rules/callouts.py`, Rule 13.2) — label-text signal only, vector box-border detection deferred. Real-book spot-check (a 32-page native-text pamphlet) confirmed no false positives and no regressions.
- [x] **Batch 15 — Citation-to-bibliography linking** (Tier A). Numeric citations (`[1]`, `[1, 3]`, `[1-4]`) link to their matching Bibliography/References entry via the same sentinel-then-Stage-4-resolves-the-link mechanism proven for endnotes (`mdook/core/rules/citations.py`), including `^ref-N` block anchors on the bibliography's own numbered entries. Author-date style (`(Smith, 2020)`) remains a documented stretch goal, not built. A bracket with any unmatched number degrades to plain text rather than a broken link. Real-book regression check (a 32-page native-text pamphlet) confirmed no crashes/regressions — this particular collection's 18th/19th-century pamphlets predate the numeric-citation convention, so a genuine positive match wasn't available to test against; the unit/integration test suite covers the actual linking behavior instead.
- [x] **Batch 16 — Image/figure completion** (Rules 7.2-7.3). Caption association (`mdook/core/rules/images.py`'s `find_caption`) checks both above and below an image for a Figure/Fig./Diagram/Illustration/Plate-labeled text block, populating the long-unused `ImageBlock.caption` field and deriving a figure-numbered attachment filename when available. Vector diagram rasterization clusters `page.get_drawings()`'s per-path rects (union-find, so a connecting line between two boxes correctly merges an ordinary flowchart into one region — an initial single-pass clustering approach failed exactly that case) and excludes any region overlapping an existing image or table bbox. Real-book spot-checked (2 books, no crashes/regressions; one recovered 2 images with the new logic active).
- [x] **Batch 17 — Math & formal notation** (full). Display/inline equations render through Obsidian's native MathJax (`$$...$$`/`$...$`), detected via Unicode symbol-density scoring (`mdook/core/rules/math.py`); theorem-like environments (Theorem/Lemma/.../Proof, with QED-marker-aware proof grouping) reuse Batch 14's `CalloutBlock` rendering. Two real bugs found writing the tests: (1) ¹²³ use legacy Latin-1 codepoints, not the Superscripts Unicode block, so "E = mc²" scored zero math density until added as an explicit exception; (2) a flat density threshold also missed short equations like that one, since most of their characters are ordinary-looking letters/digits — fixed with a two-tier check (any symbol suffices for a short paragraph, real density required for a longer one). Explicit, stated-upfront limitation: this only handles the *text-layer* math case — a PDF built from real LaTeX usually draws equations as vector paths/Type3 glyphs with no extractable Unicode at all, which is out of scope (Rule 7.2's rasterization is the honest fallback there, not semantic math recovery). Real-book regression-checked; a pre-existing literal "$" character in one 1837 pamphlet's raw text (an unrelated font-encoding quirk) was confirmed untouched by the new code, not a false positive.
- [x] **Batch 18 — Non-Latin script & RTL/bidi robustness** (generic — not Latin-biased shortcuts). New `mdook/core/rules/scripts.py` (`is_rtl_text`, `is_caseless_text`, `page_is_rtl`). Three fixes to existing rules: (1) multi-column reading order (`columns.py`) now reads the rightmost column first on a page whose dominant script is Hebrew/Arabic; (2) Batch 13's OCR-page heading confirmation, which made uppercase mandatory, is exempted for case-less scripts (CJK/Arabic/Hebrew/Devanagari/Thai) — `str.isupper()` is always False for those characters, so the guard would otherwise reject every heading candidate on such a page, not just the noisy ones; (3) a page whose lines report vertical writing mode (PyMuPDF's per-line `wmode`, new `PageData.is_vertical_text`) skips column reordering entirely rather than having it scramble traditional vertical CJK typesetting — explicit, stated-upfront scope limit: full vertical-layout reading order is not implemented, this is detect-and-don't-corrupt only. Verified with real Arabic/Hebrew/Chinese Unicode text in synthetic fixtures (no matching real book in this collection, which is entirely Latin-script); real-book regression-checked for no impact on ordinary Latin-script books.
- [x] **Batch 19 — Pathological PDF robustness** (encrypted/corrupt PDFs, CID-font garbage, blank pages, duplicate text layers, large-file awareness). New `mdook/core/errors.py` (`EncryptedPDFError`, `CorruptPDFError`) — `run_intake` now fails fast with a clear message instead of an opaque downstream traceback. CID-font/mojibake handling was investigated and found already correctly scoped (verified, no code change — see `Mdook-docs/RULES.md` Rule 17.3 for why the "valid-but-wrong-glyph" variant is undetectable from character validity alone by construction). New `PageData.is_blank`/`is_vertical_text`-style detection: a page with no text *and* no images is recorded as intentionally blank and skips OCR entirely, rather than logging what looks like an OCR failure (a page with an image but no text is correctly left alone — that's a real "OCR found nothing" case, not a false one). Duplicate overlapping text layers (a scan with both a faint original layer and a separately-applied OCR layer already baked in) are deduplicated by matching text + bbox overlap. `headers_footers.py`/`columns.py` spot-checked for quadratic behavior — neither is, both stay linear in total blocks regardless of book length. Real-book regression-checked; confirmed a page that looked like it should be "blank" was actually correctly left alone since it had 2 real embedded images with no text.

---

## Phase 4 — Multi-Format Input Support

> **Sequencing decision (2026-09-03):** deferred. After Batches 14-19 finish, the plan is to go straight to Phase 5 (Polish, Edge Cases & Design) and then a GitHub push, skipping this phase for now rather than starting EPUB support next. Revisit once Phase 5 and the GitHub push are done.

**Goal:** Handle EPUB3 (and lay groundwork for future formats) by parsing already-structured markup directly into `DocumentTree`, instead of running it through the PDF-specific heuristic pipeline. EPUB's own tags (`<h1>`, `<p>`, `<blockquote>`, a real nav/TOC document) already carry the structure Stages 2-3 spend most of their effort *guessing* at for PDFs — font-size clustering, gap-based paragraph merging, list-marker regexes, indent-based block-quote detection none of it applies here, because the answer is already in the markup. Stage 4 (Rendering) and Stage 5 (Validation) consume `DocumentTree` regardless of source and need no format-specific changes at all — this phase is the first real test that the `DocumentTree` abstraction actually holds up as a format-agnostic contract.

- [ ] **Format detection & pipeline branch** — `mdook.core.pipeline.convert()` detects input format by extension/content-sniffing and routes to the right intake path. PDF path unchanged; EPUB path is new and bypasses Stages 2-3 entirely.
- [ ] **EPUB container parsing** — Use `ebooklib` to open the `.epub` (a zip archive), read the OPF manifest/spine (reading order) and metadata (title, author, ISBN, publisher — often richer than what PDF metadata provides).
- [ ] **Navigation/TOC parsing** — Parse `nav.xhtml` (EPUB3) or `toc.ncx` (EPUB2 fallback) directly into the chapter hierarchy. No font-clustering or bookmark fuzzy-matching needed — the EPUB's own TOC already has exact titles and structure.
- [ ] **XHTML content mapping** — Walk each spine document's DOM (`BeautifulSoup`/`lxml`) and map tags directly to `DocumentTree` content types: `<h1>`-`<h6>` → `Section` hierarchy, `<p>` → `Paragraph`, `<blockquote>` → `BlockQuote`, `<ul>`/`<ol>` → `ListData`, `<table>` → `TableData`, `<pre>`/`<code>` → `CodeBlock`, `<img>` → `ImageRef` (extracted from the EPUB's own embedded assets).
- [ ] **Footnote/endnote mapping** — EPUB3's semantic footnote convention (`epub:type="footnote"`/`"noteref"`) or the common `<a href="#fnN">` + `id="fnN"` pattern maps directly to `Footnote` objects — again, no positional/font-size guessing required.
- [ ] **Front/back matter mapping** — Where an EPUB marks matter type via the structural semantics vocabulary (`epub:type="preface"`, `"bibliography"`, `"glossary"`, etc.), map it directly; otherwise fall back to the existing keyword-label matching (`FRONT_MATTER_LABELS`/`BACK_MATTER_LABELS`, already built for PDF's back-matter zone processing).
- [ ] **CSS class signal (optional, lower priority)** — An EPUB's own CSS occasionally distinguishes things plain tags don't (a "verse" or "epigraph" class) — a nice-to-have refinement once the tag-based mapping is solid.
- [ ] **End-to-end test** — Convert 3-5 real EPUB3 books (fiction, non-fiction, one with real footnotes/endnotes) through the new path; vault quality should match or exceed the PDF path's output for equivalent content.

### Phase 4 Exit Criteria

- [ ] EPUB3 books convert to the same vault structure/quality as PDF books
- [ ] Stage 4/5 required zero format-specific changes (confirms `DocumentTree` actually is a format-agnostic contract)
- [ ] Architecture documented for adding a third format later (MOBI/AZW3, DOCX, plain HTML) following the same pattern

---

## Phase 5 — Polish & Edge Cases

**Goal:** Harden the pipeline, add optional AI review, handle remaining edge cases.

> **Status check 2026-09-04:** several items below were already done as a side effect of Batches 1-19 and just never got checked off here — corrected below so this list stays trustworthy for whoever picks it up next.

- [x] **AI structure review** — Implemented in Phase 5 via `mdook/core/llm/`. Uses a zero-dependency standard library client (`urllib.request`) targeting the universal OpenAI-compatible chat-completions endpoint (`/v1/chat/completions`) compatible with OpenAI, Ollama, LM Studio, vLLM, Groq, OpenRouter, and DeepSeek. Serializes detected heading candidates into a compact, token-efficient text skeleton (~200–500 tokens) with opening body snippets. The LLM acts strictly as a reviewer returning a JSON diff of validated corrections (`demote_to_body`, `set_level`, `set_part`). Guardrails reject out-of-bounds IDs, invalid levels, or 100% book demotions. Degrades gracefully to deterministic heuristic rules if offline, timed out, or errored. Integrated into Stage 3 before chapter segmentation, tracked in `ValidationReport` and `ConversionResult`, and configurable via environment variables and desktop GUI controls (including non-blocking background connection testing with millisecond latency feedback, dynamic `/models` discovery with live searchable substring filtering, and a collapsible disclosure arrow indicator `▾` / `▸`).
- [x] **Poetry/verse handling** — Implemented Rule 9.2 in Phase 5 via `mdook/core/rules/verse.py`. Detects verse stanzas and multi-stanza poems before paragraph merging, preserving exact line breaks via markdown double trailing spaces (`  \n`) and rendering indented/quoted poems in Obsidian blockquotes (`> `). Features stanza-gap clustering, font styling continuity, dialogue and glossary guards, and a terminal punctuation discriminator to avoid false positives on short prose sentences. Supports inline footnote markers and trailing author attributions (`— Robert Frost`). Integrated into `mdook/core/stages/semantic.py` and `mdook/core/stages/rendering.py`.
- [x] **Block quote handling** — Implemented in Batch 3, well beyond just Rule 9.3's epigraphs: general indent-based block quotes too (`mdook/core/rules/*` via `semantic.py`'s `_looks_like_block_quote`).
- [x] **Glossary processing** — Implemented Rule 9.6 in Phase 5 via `mdook/core/rules/glossary.py`. Detects term-definition pairs via font-styling (bold terms), delimiter patterns (colon, em-dash, en-dash), and hanging indent geometry. Formats entries as clean `**Term** — Definition` paragraphs in dedicated `Glossary.md` notes. Preserves alphabetical letter dividers (A, B, C...) as level-2 markdown sub-headings (`## A`), supports multi-line definition merging with hyphenation rejoining, splices inline footnote and citation sentinels within definitions, preserves introductory text as standard paragraphs, and provides a graceful fallback for unstructured narrative sections.
- [x] **Bibliography processing & back-matter file splitting** — Completed in Phase 5. Back matter is split into dedicated markdown notes per section (`Bibliography.md`, `Notes.md`, `Glossary.md`, `Appendix.md`, etc.) instead of a shared single file. Spliced numeric citations link directly to `[[Bibliography#^ref-N|N]]` and endnotes link to `[[Notes#^note-N|N]]`. The index note groups and links each dedicated back-matter file under a `## Back Matter` section. Includes automatic collision deduplication (e.g. `Appendix 2.md`) and hierarchical preservation of sub-sections under their parent note.
- [x] **Symbol footnote handling** — Already implemented from the first sprint: `mdook/core/rules/footnotes.py`'s `DEFINITION_MARKER_RE` has always matched `*`, `†`, `‡`, `§`, `¶` alongside numeric markers.
- [ ] **Profile auto-detection** — Implement the signal-based profile classifier (table density, numbered headings, figure captions). Still not implemented — `run_intake` uses the caller-supplied profile as-is.
- [ ] **Custom profile support** — Allow users to pass a `.toml` override file. Still not implemented, and see `PROFILES.md`'s evolution note: most rules added after the first sprint don't read profile config at all yet, so this would need that gap closed first to be meaningful.
- [ ] **Rich CLI output** — Progress bars, colored status messages, validation report table. **Reconsider before building:** there is no CLI at all (the project became a GUI, see `ARCHITECTURE.md`) — progress reporting already exists natively via the GUI's Qt signals (`mdook/gui/worker.py`). This item may not apply anymore unless a CLI entry point is added for its own sake.
- [x] **Documentation** — Comprehensive README with installation, usage examples, visual GUI guide, configuration table, architecture overview, and `CONTRIBUTING.md` guidelines.
- [x] **GitHub release preparation** — MIT `LICENSE`, `CHANGELOG.md` (Keep a Changelog standard), enriched `pyproject.toml` metadata, expanded `.gitignore`, and GitHub Actions CI workflow (`.github/workflows/ci.yml`).


---

## Phase 6 (Future) — Distribution

- [ ] **Obsidian plugin** — TypeScript wrapper that triggers Mdook from within Obsidian
- [ ] **Web service** — Upload endpoint, conversion queue, vault download. See `PROJECT.md`'s "Vision Discussion" section — not yet scoped in detail.
- [x] **Math/formula support** — Done in Batch 17, well ahead of this phase: Unicode-symbol-density-detected equations rendered via Obsidian's native MathJax (`mdook/core/rules/math.py`). Real LaTeX-drawn vector-path equations (no extractable Unicode) remain out of scope, by design — see `RULES.md` section 15.
- [~] **Batch processing** — The GUI's queue (see `ARCHITECTURE.md`) already converts several dropped/queued PDFs sequentially in one run. What's *not* done: pointing at a whole folder/library and converting everything in it automatically — today each file still needs to be added individually (via drag-drop or the file picker).
- [ ] **Per-section profile switching** — Literary chapters + technical appendix in the same book
- [ ] **Additional format backends** — MOBI/AZW3, DOCX, plain HTML, following the Phase 4 pattern

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
