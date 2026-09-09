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

> **Implementation Decision: Tesseract (CPU-first).** Mdook implements OCR using Tesseract via `pytesseract` (`mdook/core/rules/ocr.py`) rather than heavy deep-learning layout models. Two primary reasons drove this architecture:
> 1. **Hardware portability:** Runs efficiently on standard CPUs without requiring GPU dependencies or PyTorch runtimes.
> 2. **Schema fit:** Tesseract's word-level bounding box output maps directly into Mdook's `TextBlock` model, allowing Stage 3's semantic rules (headings, footnotes, tables, columns) to run unchanged on OCR-processed pages.
>
> Implemented in `mdook/core/rules/ocr.py` (Tesseract wrapper + `TextBlock` normalization) and `mdook/core/rules/text_quality.py` (per-page text quality assessment).

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
Terminal UI for the headless CLI (`mdook convert`) — provides animated progress bars across conversion stages, colored status indicators, and formatted summary/validation tables.

```bash
pip install rich
```

### Multi-Format Ingestion Libraries
- **`ebooklib`**: Ingests EPUB2/EPUB3 archives, providing access to Dublin Core metadata, OPF manifests, spine reading orders, and navigation documents (`nav.xhtml` / `toc.ncx`).
- **`beautifulsoup4`**: Walks XHTML spine DOMs, mapping semantic tags (`<h1>`-`<h6>`, `<p>`, `<blockquote>`, `<table>`, `<pre>/<code>`, `<aside>`, `<math>`) into `DocumentTree` blocks.
- **`python-docx`**: Parses Microsoft Word `.docx` documents and OpenXML styles, mapping Heading 1–6 hierarchies, inline runs (bold, italic, code, hyperlinks), tables, and footnotes.

---

## Obsidian Desktop Plugin Stack (`obsidian-plugin/`)

The official Obsidian companion plugin is built using a lightweight TypeScript toolchain:

| Component | Technology | Role |
| :--- | :--- | :--- |
| **Language** | TypeScript 5.4+ (strict mode) | Type safety across Obsidian API contracts and CLI integration |
| **Bundler** | `esbuild` 0.21+ | Fast packaging producing a single, self-contained `main.js` (< 25 KB) |
| **API** | `obsidian` npm package | Direct integration with Obsidian's workspace, file explorer, ribbon, and modals |
| **Runtime** | Node.js (Electron Desktop) | Non-blocking `child_process.spawn` executing the local `mdook` CLI engine |
| **Dependencies** | Zero runtime npm packages | Externalizes Node built-ins and Obsidian APIs; zero external bundle bloat |

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
