# Contributing to Mdook

Thank you for your interest in contributing to Mdook!

Mdook is a desktop application that converts PDF books into structured, readable Obsidian vaults using deterministic layout heuristics, robust OCR fallback, and an optional token-efficient AI structure reviewer.

---

## Architectural Principles

Before contributing code, please keep these core design principles in mind:

1. **Deterministic Rules First**: The core extraction and structure pipeline is built on reproducible geometric and typographic heuristics (`mdook/core/rules/`). Always prefer clean rule-based algorithms over nondeterministic models for layout parsing.
2. **LLMs are Reviewers, Not Generators**: The AI component only reviews an ultra-compact heading skeleton (~200–500 tokens) to catch edge-case OCR noise and running headers. It never rewrites, rephrases, or generates book prose.
3. **Zero Heavy SDK Bloat**: We avoid bulky third-party SDKs (such as official cloud vendor SDKs) when standard library features (such as `urllib.request`) suffice.
4. **Non-Blocking GUI**: The user interface must never freeze. Any network calls or pipeline conversions must run in dedicated background `QThread` workers (`mdook/gui/worker.py`).
5. **Preserve Documentation Integrity**: All architectural decisions, rule justifications, and known limitations are cataloged in `Mdook-docs/` (particularly `RULES.md` and `ROADMAP.md`). When adding or altering rules, update the corresponding documentation.

---

## Development Setup

Mdook uses [Astral `uv`](https://docs.astral.sh/uv/) for Python dependency management.

### Prerequisites

- **Python**: 3.11 or higher
- **Tesseract OCR**: Required for scanned PDF fallback
  - **Fedora / RHEL**: `sudo dnf install tesseract tesseract-langpack-eng`
  - **Ubuntu / Debian**: `sudo apt install tesseract-ocr tesseract-ocr-eng`
  - **macOS**: `brew install tesseract`
  - **Arch Linux**: `sudo pacman -S tesseract tesseract-data-eng`

### Environment Installation

Clone the repository and install all runtime and development dependencies:

```bash
git clone https://github.com/your-org/mdook.git
cd mdook
uv sync --extra dev
```

---

## Running the Application

Launch the PySide6 desktop GUI:

```bash
uv run python -m mdook
```

---

## Testing & Quality Assurance

All pull requests must pass the test suite and linter:

```bash
# Run the test suite (configured for headless offscreen Qt)
uv run pytest -q

# Run Ruff linting and import checks
uv run ruff check .
```

### Writing Tests

- Unit tests live in `tests/`.
- Tests run headless in CI using Qt's `offscreen` platform plugin (`QT_QPA_PLATFORM=offscreen`).
- When asserting visibility on widgets in tests, use `not widget.isHidden()` rather than `widget.isVisible()` (since unshown parent windows report `isVisible() == False` in offscreen mode).

---

## Pull Request Guidelines

1. **Branch Naming**: Use descriptive branch names (e.g. `feat/verse-detection`, `fix/ocr-bounding-box`).
2. **Commit Messages**: Keep commit messages clear, concise, and written in the imperative mood (e.g. `Add model discovery for OpenAI-compatible providers`).
3. **Documentation**: Update `Mdook-docs/RULES.md` if your change affects semantic heuristics, or `Mdook-docs/ROADMAP.md` if implementing a roadmap milestone.
4. **Code Style**: Format imports and ensure lines do not exceed 100 characters (`uv run ruff check --fix .`).
