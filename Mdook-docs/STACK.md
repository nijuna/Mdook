# Tech Stack

> **How to read this file:** written before implementation started, as a plan. Blockquote callouts like this one, placed next to the section they update, show what actually happened once real code and real books tested these choices — the original reasoning is left in place below/above each callout rather than deleted, so the "why we considered X, why we ended up with Y" history stays visible.

---

## Language: Python 3.11+

No contest here. Every serious PDF processing library is Python-native. The ecosystem for document AI, OCR, and text processing is overwhelmingly Python. The CLI tooling (argparse/click/typer) is mature. Packaging and distribution (pip, pipx) is straightforward.

---

## Core Libraries

### PyMuPDF (fitz)
**Role:** Primary text and image extraction engine.
**Why:** Fastest PDF library in Python. Gives you every text block with font name, font size, weight, position (x, y, width, height), and color. Also provides the PDF's embedded bookmark/outline tree (`doc.get_toc()`), which is the single best source for heading hierarchy when it exists. Handles image extraction (`page.get_images()`) and page rasterization for vector diagrams.

```
pip install PyMuPDF
```

### pdfplumber
**Role:** Table detection and extraction.
**Why:** Built specifically for extracting tabular data from PDFs. Uses line-detection heuristics to find table boundaries and cell structures. More reliable than PyMuPDF for tables. Returns structured data you can convert to markdown pipe tables or HTML.

```
pip install pdfplumber
```

### PyMuPDF4LLM
**Role:** Fast first-pass extraction for PDFs with a text layer.
**Why:** No ML, no GPU. Uses PyMuPDF's layout engine to detect headers, paragraphs, tables, and images structurally. Good as a baseline/fast-path for non-scanned PDFs. Output can be fed into our semantic analysis layer for refinement.

```
pip install pymupdf4llm
```

> **Update: never actually used.** It's still declared in `pyproject.toml`, but nothing in `mdook/` imports it — Stage 2/3 went straight to hand-built heuristic rules (`mdook/core/rules/*.py`) instead of using pymupdf4llm's structural pre-pass as a baseline. It's unused weight in the dependency tree at this point; worth removing unless a future use for it turns up.

### Typer (or Click)
**Role:** CLI framework.
**Why:** Clean, typed CLI interface with minimal boilerplate. Auto-generates help text. Supports subcommands for future expansion (e.g., `bookforge convert`, `bookforge validate`, `bookforge inspect`).

```
pip install typer
```

> **Update: never happened — the project became GUI-first instead.** From the very first implementation sprint, Mdook shipped as a PySide6 desktop app (`mdook/gui/`), not a CLI tool. Neither Typer nor Click was ever added as a dependency. `PySide6` itself belongs in this Core Libraries list and isn't mentioned here at all — that's a gap in this doc, not in the implementation.

### Pydantic
**Role:** Data models and configuration.
**Why:** Type-safe data structures for the book manifest, page data, block types, and configuration profiles. Validates config files (YAML/TOML) on load. Makes the pipeline's internal data contracts explicit and self-documenting.

```
pip install pydantic
```

### PyYAML or tomllib
**Role:** Configuration file parsing.
**Why:** Profile configs (literature vs. technical) and per-book overrides stored as human-readable config files. TOML is built into Python 3.11+ (`tomllib`), so zero extra dependency. YAML is more familiar to most people. Pick one — TOML is lighter.

> **Update: TOML was picked, and `literature.toml`/`technical.toml` exist (`mdook/profiles/`) — but most rules added after the first sprint don't actually read from them.** Font-size thresholds, indent ratios, column-gap ratios, OCR quality thresholds, and similar tuning constants added for lists, block quotes, code detection, multi-column reordering, and OCR live as hardcoded module-level constants in their respective `mdook/core/rules/*.py` files instead. Only a couple of things are genuinely profile-gated today (numbered-section detection is technical-only; the multi-column literature-profile shortcut). This is a real gap between the plan and what got built, not a deliberate redesign — worth reconciling if per-profile tuning of the newer rules ever matters in practice.

---

## OCR Engines (Fallback Path — Phase 3)

These are only invoked when a page has no usable text layer.

> **Update: implemented with Tesseract, not Marker.** Phase 3 was planned and built with the user directly (see the discussion preserved in the project's conversation history / `/home/azzy/.claude/plans/federated-napping-toast.md`) once the target machine turned out to be CPU-only, no GPU. Two things drove the choice away from this section's original recommendation:
> 1. **Hardware.** Marker's models (PyTorch, built on Surya) run noticeably slower on CPU than GPU — usable, but a real cost for a personal library with many scanned books.
> 2. **Schema fit.** Tesseract's plain word-plus-bounding-box output (via `pytesseract`) maps almost directly onto Mdook's own `TextBlock` model, so an OCR'd page becomes "a noisier native page" to the *existing* Stage 2/3 rule pipeline rather than a second structural format needing its own reconciliation logic. This directly contradicts this section's "What We're NOT Using" table further down, which argued *against* raw Tesseract for exactly the layout-understanding reasons that turned out to be a non-issue once the normalize-to-`TextBlock` design was chosen.
>
> Implemented in `mdook/core/rules/ocr.py` (Tesseract wrapper + `TextBlock` normalization) and `mdook/core/rules/text_quality.py` (the per-page quality score below, built as planned). Marker remains a reasonable *optional* engine for a future session with GPU access, and the "trust the OCR/layout tool's own structure" idea below is preserved as a deliberately deferred enhancement (see `Mdook-docs/ROADMAP.md`'s Phase 3 section) — not abandoned, just not built yet.

### Marker (Primary Recommendation)
**Role:** Deep-learning OCR with layout understanding.
**Why:** 18k+ GitHub stars, mature, well-maintained. Built on Surya OCR. Handles dense multi-column layouts. Has an optional LLM-correction flag that can point at a local model. Outputs markdown directly, which we can then feed into our semantic analysis layer.

```
pip install marker-pdf
```

### pdf-craft (Alternative)
**Role:** Book-specific OCR pipeline.
**Why:** Purpose-built for converting scanned *books* (not generic documents) to Markdown/EPUB. Auto-generates table of contents. Handles footnotes, formulas, tables. Runs entirely locally. Overlaps significantly with what Bookforge does, so it could serve as either an OCR backend or a comparison benchmark.

### RolmOCR (For Difficult Scans)
**Role:** Vision-language model OCR for ambiguous layouts.
**Why:** Fine-tuned Qwen2.5-VL model. Reads a rendered page image and outputs markdown. Lower memory footprint than full VLMs. Best reserved for pages where Marker/pdf-craft struggle — genuinely damaged scans, unusual layouts, handwritten annotations.

### PaddleOCR / Tesseract (Last Resort)
**Role:** Lightweight fallback when no GPU is available.
**Why:** Runs on CPU. Lower quality than ML-based options but functional. Tesseract is the classic workhorse. PaddleOCR is newer and generally better, especially for non-Latin scripts.

---

## AI / LLM Integration (Optional — Phase 4)

### Structure Review Pass
A lightweight LLM call that reviews the detected heading hierarchy for an entire book — not per-page, just the structural skeleton (~200–500 tokens). Can use:
- **Claude API** — best quality, requires API key and network
- **Local model via Ollama** — fully offline, lower quality but sufficient for structure validation
- **No LLM at all** — the rule-based system works standalone; AI is an enhancement, not a dependency

The LLM never sees full book content. It only sees a skeleton like:
```
[L1] PART ONE: THE EARLY YEARS
  [L2] Chapter 1 — Childhood
    [body first line] "I was born in a small village..."
```

### Prompt Templates
Stored as separate files in a `prompts/` directory. Versioned and testable independently of the pipeline code.

---

## Dev & Testing Tools

### pytest
Unit tests for each pipeline stage. Integration tests that run a known PDF through the full pipeline and diff the output against an expected vault.

> **Update: this is exactly what happened**, and it grew well past "unit tests for each stage" — 119 tests as of the last implementation session, including several regression tests written directly against real books from the user's own collection once a bug was found there (see `Mdook-docs/RULES.md`'s evolution notes for specific examples).

### Rich
Pretty CLI output — progress bars for multi-page processing, colored status messages, table-formatted validation reports.

```
pip install rich
```

> **Update: declared as a dependency, never imported anywhere.** Same situation as PyMuPDF4LLM above — a casualty of the CLI-to-GUI pivot. Progress reporting in the actual app goes through PySide6's own signal/slot mechanism (`mdook/gui/worker.py`'s `ConversionWorker`), not Rich. Worth removing unless a CLI entry point gets built later.

### pre-commit / ruff
Code formatting and linting. Ruff is fast and replaces flake8 + isort + black in one tool.

> **Update: ruff yes, pre-commit no.** Ruff is configured in `pyproject.toml` and run directly (`uv run ruff check .`) as part of the normal dev workflow. No `.pre-commit-config.yaml` exists — lint checks aren't automated as a git hook, just run manually/on-demand.

---

## What We're NOT Using (And Why)

| Tool | Why Not |
|------|---------|
| LangChain / LlamaIndex | Overkill. We're not building RAG or chat. We're building a deterministic pipeline with an optional LLM call. |
| Pandoc | Good for format conversion between structured documents, but PDFs aren't structured — Pandoc can't infer semantics from layout. |
| Adobe PDF Services API | Cloud-only, paid, and doesn't solve the semantic analysis problem. |
| ABBYY FineReader | Commercial, Windows-focused, overkill for our use case. |
| Nougat (Meta) | Designed for academic papers, not books. Struggles with literary content and non-standard layouts. |
| Raw Tesseract alone | No layout understanding. You'd have to rebuild all the column detection, reading order, and block classification that Marker/pdf-craft already do. |

> **Update: this row is exactly what got built, on purpose, and it worked.** See the "OCR Engines" update above. "You'd have to rebuild column detection, reading order, and block classification yourself" turned out to be a non-issue in practice — Mdook already builds and owns all of that (`mdook/core/rules/columns.py`, `headings.py`, etc.) for the native-PDF path, so reusing it for OCR'd `TextBlock`s cost nothing extra. The tradeoff this row worried about is real for a tool starting from scratch; it wasn't a real cost here.

---

## System Requirements

### Minimum (Phase 1 — no OCR)
- Python 3.11+
- ~500MB disk for dependencies
- Any modern CPU
- No GPU needed

### Recommended (Full pipeline with OCR)
- Python 3.11+
- 8GB+ RAM
- NVIDIA GPU with 6GB+ VRAM (for Marker/Surya OCR)
- ~5GB disk for dependencies + models

> **Update: not what Phase 3 actually needs.** With Tesseract as the implemented engine (see "OCR Engines" above), the real requirement is just the `tesseract` system package (e.g. `sudo dnf install tesseract` on Fedora) — no GPU, no multi-gigabyte model download. The GPU/VRAM line above only applies if Marker is added later as an optional engine.

### Fully Offline
The entire stack runs without network access once dependencies and models are installed. No API keys required for the core pipeline. The optional LLM structure review can use a local model via Ollama.
