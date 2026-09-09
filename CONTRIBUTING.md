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
git clone https://github.com/nijuna/Mdook.git
cd Mdook
uv sync --extra dev
```

---

## Running the Application & CLI

### 1. PySide6 Desktop GUI
Launch the graphical interface:
```bash
uv run mdook
# or: uv run python -m mdook
```

### 2. Headless CLI Converter
Run conversions directly in the terminal:
```bash
uv run mdook convert path/to/book.pdf -o ./vaults/
uv run mdook convert novel.epub -o ./vaults/ --profile literature
uv run mdook convert manuscript.docx -o ./vaults/ --profile technical
```

---

## Obsidian Desktop Plugin Development (`obsidian-plugin/`)

The official Obsidian plugin allows users to convert books directly inside their vault.

### Prerequisites
- **Node.js**: v18.0 or higher
- **npm**: v9.0 or higher

### Development Workflow
```bash
cd obsidian-plugin

# Install dependencies
npm install

# Run fast development build with watch mode
npm run dev

# Run production build (type checking + esbuild minification)
npm run build
```

### Testing in a Live Vault
To test changes directly inside an active Obsidian vault:
1. Create a symlink or copy `main.js`, `manifest.json`, and `styles.css` into your vault:
   ```bash
   mkdir -p "/path/to/vault/.obsidian/plugins/mdook"
   cp main.js manifest.json styles.css "/path/to/vault/.obsidian/plugins/mdook/"
   ```
2. In Obsidian: **Settings** $\rightarrow$ **Community Plugins** $\rightarrow$ Click **Reload plugins** $\rightarrow$ Enable **Mdook Book Importer**.
3. Use `Ctrl+R` (or `Cmd+R`) in Obsidian to quickly reload the app when updating `main.js`.

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
