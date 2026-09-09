# Mdook

**Convert PDF books into structured, readable Obsidian vaults.**

---

## Vision

PDFs are layout documents — they know where ink goes on a page, not what a "chapter heading" or "footnote" is. Every existing PDF-to-markdown tool treats this as a generic document conversion problem. Mdook treats it as a *book understanding* problem.

The goal is not pixel fidelity. It is semantic fidelity — preserving the structure, hierarchy, references, and reading flow of a book in a format that is pleasant for humans to read in Obsidian and efficient for AI models to reason about without wasting tokens on layout noise.

---

## What Mdook Does

- Takes a PDF book as input (literary, academic, or technical)
- Detects the book's internal structure: front matter, chapters, back matter, footnotes, figures, citations, math, callout boxes
- Converts each structural unit into clean, well-formatted Markdown
- Outputs a complete Obsidian vault with linked files, page references, and extracted images
- Preserves the book's own organizational conventions (chapters, modules, parts, named sections — whatever the book uses)
- Falls back to OCR (Tesseract) per page when a page has no usable text layer, without needing a second pipeline
- Runs entirely locally with no cloud dependencies

## What Mdook Does Not Do

- Pixel-perfect reproduction of page layouts (Markdown cannot do this; if you need it, use HTML)
- Real-time or streaming conversion (this is a batch tool)
- DRM removal or circumvention of any kind
- Replace reading the book — it makes the book *more* accessible, not summarized

---

## Target Users

1. **Obsidian power users** who read seriously and want their books inside their knowledge graph
2. **Academic researchers / PhD students** who need to annotate, cross-reference, and discuss books with AI
3. **Technical learners** who want reference books searchable and linkable in their vault
4. **Knowledge workers** building internal wikis or reference libraries from book-format material

---

## Distribution Plan

> **Update: the original three-phase plan below (CLI → Obsidian plugin →
> web service) was superseded almost immediately** — the project became a
> **PySide6 desktop GUI** (`mdook/gui/`) from the very first implementation
> sprint and never had a CLI at all. No public GitHub repo exists yet
> either. See "Project Status" below for what actually shipped, and
> `Mdook-docs/ROADMAP.md`'s Phase 5/6 for the current distribution-related
> open items (license, changelog, CI, and the Obsidian-plugin/web-service
> ideas below, still just ideas).

### Phase 1 — Open-Source CLI (Priority) *(superseded — became a desktop GUI instead)*

- ~~Python CLI tool: `Mdook convert book.pdf --profile literature --output ./vault/MyBook/`~~
- Published on GitHub with MIT or Apache 2.0 license — **not done yet**, no repo exists
- Good documentation, example outputs, before/after comparisons — partially done (see `README.md`)
- This is the portfolio piece and the foundation everything else builds on

### Phase 2 — Obsidian Community Plugin *(not started)*

- Wraps the CLI pipeline so users can trigger conversion from within Obsidian
- Free plugin, local processing by default
- Optional: call a hosted API for OCR-heavy or AI-assisted conversions

### Phase 3 — Web Service (If Demand Exists) *(not started; see the "vision discussion" note below)*

- Upload PDF → get back a zip of the Obsidian vault
- Freemium model: free tier with basic heuristics, paid tier with full pipeline + AI structure review
- Only worth building after the core engine is battle-tested and has real users

---

## Build Phases

Detailed task and milestone tracking is maintained in `Mdook-docs/ROADMAP.md`:

- **Phase 1 — Literary Books with Text Layer** *(Complete)*
- **Phase 2 — Technical Profile** *(Complete)*
- **Phase 3 — OCR Fallback (Tesseract CPU Engine)** *(Complete)*
- **Phase 4 — Multi-Format Input Support (EPUB3 & DOCX)** *(Complete)*
- **Phase 5 — Polish & Edge Cases (AI Review, Poetry, Glossaries, Dedicated Back-Matter)** *(Complete)*
- **Phase 6 — Distribution (Obsidian Plugin & Packaging)** *(Future)*

---

## Success Metrics

- A converted book is readable *as a book* — comfortable for human reading in Obsidian, not just searching.
- An AI given a chapter file can reason over its content without confusion from layout artifacts.
- The tool handles structural variety (chapters, modules, parts, named sections, unnumbered divisions) without hardcoded assumptions about what books "should" look like.
- Open-source health: clean tests, comprehensive documentation, and straightforward local installation.

---

## Future Extensions & Vision

- **Multimodal Diagram Captioning & Alt-Text**: Using local/cloud Vision-Language Models (VLMs) to inspect extracted diagrams and figures, generating descriptive alt-text and summaries to make visuals searchable in Obsidian and readable by LLMs.
- **Visual LaTeX Formula Recovery**: Processing vector-drawn equation regions through vision-based math extractors to recover clean MathJax formulas when PDFs lack extractable Unicode math.
- **Automatic Concept & Glossary Wikilinking**: Automatically cross-linking first mentions of glossary entries and core entities in chapters to their definition anchors (`[[Glossary#Term|term]]`), forming an Obsidian knowledge graph.
- **Obsidian Canvas Overview**: Generating native `.canvas` visual cards and reading roadmaps mapping book parts, chapters, and key figures.
- **Recursive Directory Batching**: CLI and GUI capabilities to recursively ingest entire folder trees of books.
- **Hosted / Web Conversion**: An optional headless web service endpoint for remote book conversion workflows.

---

## Project Status

**Release 0.2.0:** Multi-format book conversion engine:
- **Multi-Format Input Support**: Ingests PDF documents, EPUB3 / EPUB2 publications, and Word DOCX manuscripts into a unified `DocumentTree` contract.
- **Official Obsidian Desktop Plugin (`obsidian-plugin/`)**: Direct in-vault conversion of `.pdf`, `.epub`, and `.docx` books, folder batch processing, destination picker, context menus, and live status bar progress.
- **Profile Auto-Detection**: Heuristic signal classifier evaluating table density, numbered headings (`1.2.3`), code blocks, and math density.
- **Rich Book Typography & Semantics**: Footnotes and endnotes with block anchors, numeric citation-to-bibliography links, Obsidian callouts (`> [!note]`), MathJax equations (`$$...$$`), table extraction with merged-cell complexity classification, caption association, and RTL script reading order.
- **Hybrid OCR Fallback**: Automated per-page text-quality evaluation routing scanned pages to Tesseract OCR with fuzzy header deduplication.
- **OpenAI-Compatible AI Structure Review**: Zero-dependency outline review supporting local (Ollama, LM Studio, vLLM) and cloud providers (Groq, OpenAI, DeepSeek).
- **Poetry & Verse Preservation (Rule 9.2)**: Exact lineation preservation with markdown double trailing spaces, blockquote rendering, stanza spacing clustering, and author attributions.
- **Dedicated Back-Matter Files & Structured Glossaries (Rule 9.6)**: Split back-matter files (`Notes.md`, `Bibliography.md`, `Glossary.md`, `Appendix.md`) with term-definition parsing and alphabetical dividers (`## A`, `## B`).
- **Desktop GUI & Headless CLI**: PySide6 dark/light interface with drag-and-drop queue, paired with a standalone headless CLI (`mdook convert`) featuring Rich terminal progress bars and validation tables.
- **Quality & Testing**: 283 unit and integration tests passing, clean Ruff linting, active Git repository with continuous integration.

See `Mdook-docs/ROADMAP.md` for phase-by-phase task tracking, and `Mdook-docs/RULES.md` for the semantic detection rules catalog.
