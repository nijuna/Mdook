# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
