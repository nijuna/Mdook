# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Structured Glossary Processing (Rule 9.6)**:
  - Added deterministic term-definition pair detection for back-matter glossary sections via `mdook/core/rules/glossary.py`.
  - Multi-signal detection supporting font-styling cues (bold terms), delimiter conventions (`Term: Definition`, `Term — Definition`, `Term – Definition`), and geometric hanging indents.
  - Formatted entries as clean markdown paragraphs (`**Term** — Definition`) within dedicated `Glossary.md` notes.
  - Alphabetical letter divider detection (`A`, `B`, `— C —`, `Section D`) generating structured markdown sub-headings (`## A`, `## B`).
  - Multi-line definition merging with hyphenated word rejoining (Rule 5.2).
  - Preservation of inline footnote and numeric citation sentinels within definitions, linking directly to `[[Notes.md]]` and `[[Bibliography.md]]`.
  - Automatic preservation of introductory prose and graceful fallback for unstructured narrative sections.
- **Back-Matter File Splitting (Dedicated Notes)**:
  - Decomposed back-matter content into dedicated Obsidian notes (`Glossary.md`, `Bibliography.md`, `Notes.md`, `Appendix.md`, etc.) rather than bundling everything into a single monolithic `99 - Back Matter.md`.
  - Automatic collision deduplication for multiple sections with identical titles (e.g. `Appendix.md`, `Appendix 2.md`).
  - Hierarchical sub-section preservation within dedicated back-matter divisions with root heading deduplication.
  - Direct cross-file wikilink routing for endnotes (`[[Notes#^note-N|N]]`) and numeric citations (`[[Bibliography#^ref-N|N]]`), with fallback to generic back-matter division.
  - Vault index file (`{title} - Index.md`) updated with a dedicated `## Back Matter` section linking each generated back-matter note.
- **Poetry and Verse Handling (Rule 9.2)**:
  - Exact line break preservation in verse stanzas and multi-stanza poems via markdown double trailing spaces (`  \n`).
  - Obsidian blockquote formatting (`> `) for indented and quoted poems.
  - Multi-stanza aggregation with blank-line stanza separators (`\n\n`) and vertical spacing clustering (1.7×–3.5× line height).
  - Trailing author attribution extraction (e.g. `— Robert Frost`, `-- Author`, `(by Author)`) rendered cleanly with standard em-dash format (`— Author`).
  - Domain safeguards against false positives: terminal punctuation discriminator against discrete prose sentences, dialogue quote & speech verb filters, and glossary term definition guards.
  - Direct splicing of inline superscript footnote markers in verse lines.

## [0.1.0] - 2026-09-05

### Added
- **5-Stage Conversion Pipeline**:
  - **Stage 1 (Intake)**: PDF validation, fast failure on encrypted or corrupt files, document metadata extraction (title, author, ISBN).
  - **Stage 2 (Extraction)**: Native text block extraction via PyMuPDF, font metrics (size, weight, family), table extraction via `pdfplumber`, embedded image extraction, vector diagram rasterization via bounding-box clustering, and image caption correlation.
  - **Stage 3 (Semantic Analysis)**: Deterministic font-clustering and bookmark heading detection, chapter segmentation, Part/Book/Volume grouping, front-matter and back-matter zone isolation, footnote and endnote correlation with bidirectional backlink sentinels, numeric citation-to-bibliography linking, Obsidian callout/sidebar box detection (`Note`, `Warning`, `Tip`), native MathJax equation rendering (`$$...$$`, `$...$`), and RTL-aware multi-column reading order (Hebrew/Arabic).
  - **Stage 4 (Rendering)**: Pure markdown and Obsidian vault generation, YAML frontmatter, table-of-contents Index note, relative image asset references, and block-level footnote anchors (`^note-N`, `^ref-N`).
  - **Stage 5 (Validation)**: Automated quality audit producing a `ValidationReport` with chapter counts, page stats, OCR page counts, footnote pairing integrity, and heuristic warnings.
- **Hybrid OCR Fallback**:
  - Text-layer quality scoring heuristic (`mdook/core/rules/text_quality.py`).
  - Automatic per-page routing to Tesseract OCR for scanned pages with no native text layer.
  - OCR line normalization into standard `TextBlock` format, fuzzy sequence matching (≥0.82) for header/footer deduplication, and case-less script support.
- **OpenAI-Compatible AI Structure Review**:
  - Zero-dependency HTTP client using standard library `urllib` targeting `/v1/chat/completions`.
  - Tested compatibility across OpenAI, Groq, local Ollama, LM Studio, vLLM, DeepSeek, and OpenRouter.
  - Token-efficient outline skeleton serialization (~200–500 tokens) with opening body snippets (no full chapter content sent).
  - Strictly constrained reviewer role returning structured JSON diffs (`demote_to_body`, `set_level`, `set_part`).
  - Deterministic guardrails discarding out-of-bounds IDs or whole-book demotions.
  - Seamless automatic fallback to deterministic heuristic rules if offline or errored.
  - Dynamic model discovery querying provider `/models` endpoints with live searchable substring filtering.
  - Non-blocking background connection testing with roundtrip latency feedback in milliseconds.
- **PySide6 Desktop GUI**:
  - Light and dark theme toggle with instant stylesheet swapping.
  - Full-window drag-and-drop zone with animated card highlight.
  - Multi-file sequential conversion queue with real-time status glyphs (`•`, `▶`, `✓`, `✗`).
  - Collapsible AI Structure Review panel with disclosure arrow indicators (`▾` / `▸`).
  - Non-blocking background worker threads (`ConversionWorker`, `ConnectionTestWorker`, `ModelFetchWorker`).
  - Conversion summary card with "Open Vault" direct file explorer integration.
- **Developer & CI Infrastructure**:
  - 238 unit and integration tests passing with headless Qt offscreen configuration.
  - Ruff linter configuration with strict import sorting.
  - GitHub Actions CI matrix testing Python 3.11 and 3.12 with system Tesseract and Qt dependencies.
