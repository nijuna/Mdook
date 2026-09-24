# Mdook

**Convert books into structured Markdown libraries and single documents.**

---

## Vision

Books are structured knowledge, not raw layout artifacts. PDFs know where ink goes on a page, EPUBs structure reflowable markup, and DOCX manuscripts capture styled runs. Every generic conversion tool flattens these into disconnected text. Mdook treats document conversion as a *book understanding* problem.

The goal is not pixel fidelity. It is semantic fidelity — preserving the structure, hierarchy, references, and reading flow of a book in clean Markdown that is pleasant for humans to read across Markdown editors and knowledge bases, and optimal for AI models to reason about without wasting tokens on layout noise.

---

## What Mdook Does

- Ingests PDF documents, EPUB3 publications, and Word DOCX manuscripts
- Detects the book's internal structure: front matter, chapters, back matter, footnotes, figures, citations, math, callout boxes
- Hardened against real-world layout anomalies: line-level structural zone scanning, drop-shadow duplicate span deduplication, outer side margin watermark suppression, and sub-pixel printer dingbat filtering
- Sanitizes publication metadata, stripping desktop publishing layout document filenames (.qxd, .indd, .pmd) and downloader promotional watermarks
- Converts each structural unit into clean, well-formatted Markdown
- Emits dual output formats: **Modular Library** (chapter-split files with Part grouping and Index) or **Single Document** (continuous reading copy with consolidated notes)
- Preserves the book's own organizational conventions (chapters, modules, parts, named sections — whatever the book uses)
- Falls back to OCR (Tesseract) per page when a PDF page has no usable text layer, without needing a second pipeline
- Runs entirely locally with no cloud dependencies

## What Mdook Does Not Do

- Pixel-perfect reproduction of page layouts (Markdown cannot do this; if you need it, use HTML)
- Real-time or streaming conversion (this is a batch tool)
- DRM removal or circumvention of any kind
- Replace reading the book — it makes the book *more* accessible, not summarized

---

## Target Users

1. **Markdown knowledge base users** who read seriously and want their books inside interconnected libraries
2. **Academic researchers / PhD students** who need to annotate, cross-reference, and discuss books with AI
3. **Technical learners** who want reference books searchable, organized, and linkable
4. **Knowledge workers** building internal wikis or reference libraries from book-format material

---

## Distribution & Interfaces

Mdook is distributed with multiple interfaces and is hosted on GitHub at [nijuna/Mdook](https://github.com/nijuna/Mdook) under the MIT License:

### 1. Desktop GUI (PySide6)
- Modern two-tier desktop interface (`mdook/gui/`) featuring file inspection cards, 5-stage stepper, and sequential queue.
- 3 Theme Families (*The Library*, *Amethyst*, *Carbon*) in dark/light modes.
- Strictly typography-first design with zero emojis.
- Dedicated `SettingsDialog` with dynamic LLM provider discovery and latency testing.

### 2. Headless CLI & Interactive Wizard (`mdook/cli.py`, `mdook/cli_wizard.py`)
- Full terminal and headless server automation (`mdook convert book.pdf -o ./output/`).
- Recursive publication scanner (`mdook scan`) discovering and summarizing supported publications across directories.
- Step-by-step interactive terminal wizard (`mdook interactive` / `mdook -i`) for batch selection, format toggle, and conversion.
- Supports modular library or single document formats, profile selection, and AI structure review flags.
- Rich terminal progress indicators and validation summary tables.
- Display-aware entrypoint: launches GUI on desktop displays, prints help on headless servers.

### 3. Obsidian Desktop Plugin (`obsidian-plugin/`)
- Official companion plugin enabling in-app conversion of `.pdf`, `.epub`, and `.docx` books directly inside Obsidian.
- Context menu integration, folder batch conversions, and interactive conversion modal.
- Configurable output modes (modular library or single document) and real-time status bar widget.

### 4. Standalone Packaging & OS Integration (`packaging/`, `mdook.spec`)
- Standalone PyInstaller binary builds requiring no host Python environment.
- Linux desktop launcher (`mdook.desktop`), scalable vector application icon, and system MIME associations for PDF, EPUB, and DOCX files.

---

## Build Phases

Detailed task and milestone tracking is maintained in `Mdook-docs/ROADMAP.md`:

- **Phase 1 — Literary Books with Text Layer** *(Complete)*
- **Phase 2 — Technical Profile** *(Complete)*
- **Phase 3 — OCR Fallback (Tesseract CPU Engine)** *(Complete)*
- **Phase 4 — Multi-Format Input Support (EPUB3 & DOCX)** *(Complete)*
- **Phase 5 — Polish & Edge Cases (AI Review, Poetry, Glossaries, Dedicated Back-Matter)** *(Complete)*
- **Phase 6 — Distribution (Obsidian Plugin, Wizard, & Standalone Packaging)** *(Complete)*
- **Sprint 2.0.1 — Real-World PDF Evaluation & Layout Heuristics Hardening** *(Complete — verified against 11 diverse test books, 2,479 total pages, with 0 crashes)*

---

## Success Metrics

- A converted book is readable *as a book* — comfortable for human reading across Markdown readers, not just searching.
- An AI given a chapter file can reason over its content without confusion from layout artifacts.
- The tool handles structural variety (chapters, modules, parts, named sections, unnumbered divisions) without hardcoded assumptions about what books "should" look like.
- Open-source health: clean tests, comprehensive documentation, and straightforward local installation.

---

## Future Extensions & Vision

- **Multimodal Diagram Captioning & Alt-Text**: Using local/cloud Vision-Language Models (VLMs) to inspect extracted diagrams and figures, generating descriptive alt-text and summaries to make visuals searchable in Obsidian and readable by LLMs.
- **Visual LaTeX Formula Recovery**: Processing vector-drawn equation regions through vision-based math extractors to recover clean MathJax formulas when PDFs lack extractable Unicode math.
- **Automatic Concept & Glossary Wikilinking**: Automatically cross-linking first mentions of glossary entries and core entities in chapters to their definition anchors (`[[Glossary#Term|term]]`), forming an interconnected knowledge graph.
- **Visual Graph & Canvas Overviews**: Generating visual cards and reading roadmaps mapping book parts, chapters, and key figures.
- **Hosted / Web Conversion**: An optional headless web service endpoint for remote book conversion workflows.

---

## Project Status

**Release 0.2.0:** Multi-format book conversion engine:
- **Multi-Format Input Support**: Ingests PDF documents, EPUB3 / EPUB2 publications, and Word DOCX manuscripts into a unified `DocumentTree` contract.
- **Dual Output Formats**: Supports chapter-split **Modular Libraries** (with Part hierarchies, attachments, and navigation indexes) and **Single Continuous Documents** (1:1 reading copy with standard image links and consolidated notes).
- **Directory Publication Scanner**: `mdook scan` inspects directories for supported documents with pre-flight metadata extraction.
- **Interactive Terminal Wizard**: `mdook interactive` (`mdook -i`) provides a terminal-based guided conversion experience.
- **Official Obsidian Desktop Plugin (`obsidian-plugin/`)**: Direct in-vault conversion of `.pdf`, `.epub`, and `.docx` books, folder batch processing, destination picker, context menus, and live status bar progress.
- **Standalone Packaging**: PyInstaller build specification (`mdook.spec`) and Linux desktop integration script (`packaging/linux/install-desktop.sh`).
- **Profile Auto-Detection**: Heuristic signal classifier evaluating table density, numbered headings (`1.2.3`), code blocks, and math density.
- **Rich Book Typography & Semantics**: Footnotes and endnotes with block anchors, numeric citation-to-bibliography links, callouts (`> [!note]`), MathJax equations (`$$...$$`), table extraction with merged-cell complexity classification, caption association, and RTL script reading order.
- **Hybrid OCR Fallback**: Automated per-page text-quality evaluation routing scanned pages to Tesseract OCR with fuzzy header deduplication.
- **OpenAI-Compatible AI Structure Review**: Zero-dependency outline review supporting local (Ollama, LM Studio, vLLM) and cloud providers (Groq, OpenAI, DeepSeek).
- **Poetry & Verse Preservation (Rule 9.2)**: Exact lineation preservation with markdown double trailing spaces, blockquote rendering, stanza spacing clustering, and author attributions.
- **Dedicated Back-Matter Files & Structured Glossaries (Rule 9.6)**: Split back-matter files (`Notes.md`, `Bibliography.md`, `Glossary.md`, `Appendix.md`) with term-definition parsing and alphabetical dividers (`## A`, `## B`).
- **Desktop GUI & Headless CLI**: PySide6 dark/light interface with drag-and-drop queue, paired with a standalone headless CLI (`mdook convert`) featuring Rich terminal progress bars and validation tables.
- **Quality & Testing**: 324 unit and integration tests passing, clean Ruff linting, active Git repository with continuous integration.

See `Mdook-docs/ROADMAP.md` for phase-by-phase task tracking, and `Mdook-docs/RULES.md` for the semantic detection rules catalog.
