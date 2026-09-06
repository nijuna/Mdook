<div align="center">

# Mdook

**Convert PDF books into structured, readable Obsidian vaults.**

[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![PySide6](https://img.shields.io/badge/GUI-PySide6-41cd52.svg)](https://pypi.org/project/PySide6/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Tests](https://img.shields.io/badge/tests-238%20passed-brightgreen.svg)]()

</div>

---

## Overview

Most PDF-to-Markdown tools produce a single, messy text dump with broken paragraphs, leaked running headers, lost footnotes, and fractured tables.

**Mdook** is a desktop application designed specifically for **books**. It extracts text, diagrams, and metadata from PDF files, analyzes typography and reading order through deterministic heuristics, and generates a structured, multi-file **Obsidian vault** ready for reading and personal knowledge management.

```text
Input: Book.pdf 
   │
   ▼
[Stage 1: Intake]       ── Validation, metadata extraction, fail-fast corruption checks
   │
   ▼
[Stage 2: Extraction]   ── Text blocks, font metrics, pdfplumber tables, image & vector drawings
   │
   ▼
[Stage 3: Semantics]    ── Heading clustering, chapter splitting, footnotes, callouts, MathJax
   │                       └─ Optional: OpenAI-compatible AI Structure Review (~200 tokens)
   ▼
[Stage 4: Rendering]    ── Multi-file Obsidian vault, YAML frontmatter, Index/MOC, backlinks
   │
   ▼
[Stage 5: Validation]   ── Automated structural audit (ValidationReport)
   │
   ▼
Output: /My-Book-Vault/
        ├── 00 - Index.md
        ├── 01 - Chapter 1.md
        ├── 02 - Chapter 2.md
        ├── 99 - Back Matter.md
        └── attachments/
```

---

## Key Features

###  Deterministic Layout & Semantic Engine
- **Font-Clustering Heading Hierarchy**: Reconstructs book structure even when the PDF lacks bookmarks or a table of contents.
- **Part / Book / Volume Segmentation**: Recognizes multi-tier books and groups chapters under Part divisions in the vault Index.
- **Front & Back Matter Isolation**: Automatically isolates Preface, Introduction, Notes, Bibliography, and Appendices into dedicated sections.
- **Multi-Column & Bidirectional Reading Order**: Column detection with right-to-left (RTL) reading order for Hebrew and Arabic scripts.

###  Scanned Book OCR Fallback (Tesseract)
- Evaluates text-layer quality per page.
- Automatically routes scanned or damaged pages to **Tesseract OCR** while keeping native vector pages fast.
- Fuzzy sequence matching prevents noisy OCR headers from leaking into chapter prose.

###  Rich Book Elements
- **Footnotes & Endnotes**: Bidirectional links between body text and notes using Obsidian block references (`[[#^note-1|1]]` and `^note-1`).
- **Citation-to-Bibliography Linking**: Correlates in-text numeric citations (`[1]`, `[1-3]`) directly to matching bibliography entries.
- **Obsidian Callouts**: Detects Note, Warning, Tip, and Caution sidebars and renders native `> [!note]` callouts.
- **Math & Formal Notation**: Detects Unicode math symbols and renders inline and display equations via native Obsidian MathJax (`$$...$$`).
- **Tables & Figures**: Extracts tables using `pdfplumber`, extracts embedded illustrations, rasterizes vector schematics, and correlates captions.

###  OpenAI-Compatible AI Structure Review (Optional)
- **Token Efficient**: Sends only an ultra-compact outline skeleton (~200–500 tokens), never generating or rewriting book contents.
- **Broad Provider Reach**: Works with **Groq**, **OpenAI**, **local Ollama**, **LM Studio**, **vLLM**, **DeepSeek**, and **OpenRouter**.
- **Model Discovery**: Dynamically queries the provider's `/models` endpoint to populate an editable, searchable dropdown.
- **Latency & Reachability Testing**: Non-blocking connection test measuring roundtrip latency in milliseconds.
- **Fail-Safe Fallback**: Guardrails discard invalid suggestions; network failures gracefully fall back to deterministic heuristics.

###  Modern Desktop GUI (PySide6)
- Dark and Light theme toggle with instant stylesheet switching.
- Drag-and-drop PDF ingestion.
- Sequential multi-file conversion queue with real-time status indicators (`•`, `▶`, `✓`, `✗`).
- Direct "Open Vault" file manager integration upon conversion completion.

---

## Installation & Quickstart

Mdook requires **Python 3.11+** and uses [Astral `uv`](https://docs.astral.sh/uv/) for dependency management.

### 1. Prerequisites

For scanned PDF OCR support, install the Tesseract system binary:

- **Fedora / RHEL**:
  ```bash
  sudo dnf install tesseract tesseract-langpack-eng
  ```
- **Ubuntu / Debian**:
  ```bash
  sudo apt install tesseract-ocr tesseract-ocr-eng
  ```
- **macOS** (Homebrew):
  ```bash
  brew install tesseract
  ```
- **Arch Linux**:
  ```bash
  sudo pacman -S tesseract tesseract-data-eng
  ```

### 2. Install Mdook

Clone the repository and sync dependencies:

```bash
git clone https://github.com/your-org/mdook.git
cd mdook
uv sync --extra dev
```

### 3. Launch the Application

```bash
uv run python -m mdook
```

---

## Configuration

Settings can be configured directly inside the desktop GUI or set via environment variables:

| Environment Variable | Default | Description |
| -------------------- | ------- | ----------- |
| `MDOOK_LLM_ENABLED` | `false` | Enable AI Structure Review (`true` / `false`) |
| `MDOOK_LLM_BASE_URL` | `https://api.openai.com/v1` | OpenAI-compatible endpoint URL |
| `MDOOK_LLM_API_KEY` | *(empty)* | API key (optional for local Ollama / LM Studio) |
| `MDOOK_LLM_MODEL` | `gpt-4o-mini` | Model name (e.g. `llama-3.3-70b-versatile`, `llama3.2`) |
| `MDOOK_LLM_TIMEOUT` | `30.0` | Network timeout in seconds |

---

## Development & Testing

Mdook is thoroughly tested with 238 unit and integration tests configured to run headless offscreen:

```bash
# Run the test suite
uv run pytest -q

# Run Ruff linter and import sorter
uv run ruff check .

# Automatically apply safe fixes
uv run ruff check --fix .
```

---

## Documentation

Full architectural documentation and design logs are maintained in [`Mdook-docs/`](Mdook-docs/):

- [`Mdook-docs/PROJECT.md`](Mdook-docs/PROJECT.md): Project vision and scope.
- [`Mdook-docs/ARCHITECTURE.md`](Mdook-docs/ARCHITECTURE.md): Data models, 5-stage pipeline, and GUI structure.
- [`Mdook-docs/RULES.md`](Mdook-docs/RULES.md): Catalog of all 18 semantic detection rules and edge cases.
- [`Mdook-docs/ROADMAP.md`](Mdook-docs/ROADMAP.md): Milestone tracking across development phases.
- [`Mdook-docs/HANDOFF.md`](Mdook-docs/HANDOFF.md): Engineering orientation and design trade-offs.

---

## License

This project is licensed under the [MIT License](LICENSE).
