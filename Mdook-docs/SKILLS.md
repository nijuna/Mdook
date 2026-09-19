# Skills

What building Mdook requires and develops — framed for portfolio value and AI engineering career relevance.

---

## Core Technical Skills

### Document AI & NLP

- PDF internal structure (content streams, font tables, page trees, bookmarks, metadata dictionaries)
- Text extraction with positional and typographic metadata
- Heuristic classification: turning visual signals (font size, weight, position, spacing) into semantic labels (heading, footnote, caption, body)
- OCR pipeline design: routing decisions, quality thresholds, fallback chains
- Multi-modal document understanding (text + layout + images)

**Portfolio framing:** "Built a document intelligence pipeline that infers semantic structure from layout-only PDF data — the same class of problem commercial tools like Adobe Acrobat and ABBYY solve, but specifically optimized for book-length documents."

### Pipeline Architecture

- Multi-stage sequential pipeline with typed intermediate representations
- Stage isolation: each stage has a clear contract (input schema → output schema) and is independently testable
- Configuration-driven behavior: profiles, rule tuning, feature flags
- Graceful degradation: OCR fallback when text layer is missing, HTML fallback when markdown can't represent a table, AI fallback when heuristics are uncertain

**Portfolio framing:** "Designed a five-stage processing pipeline with typed data contracts between stages, configuration-driven heuristic tuning, and graceful degradation paths for edge cases."

### Heuristic Engineering

- Designing rules that work across hundreds of different books without being brittle
- Threshold tuning: finding the right font-size ratio, position percentage, word count cutoff
- Combining weak signals: no single heuristic is reliable alone, but 3 out of 5 passing is
- Knowing when to stop: accepting 90% accuracy from rules and using AI to patch the remaining 10%, rather than building an infinitely complex rule system
- Debugging heuristics: when the output is wrong, tracing back through rule decisions to find which rule misfired and why

**Portfolio framing:** "Engineered a heuristic system that combines typographic, positional, and structural signals to classify document elements with ~90% accuracy across diverse book formats, with an optional LLM verification pass for edge cases."

### AI/LLM Integration

- Using LLMs as reviewers, not generators: the AI doesn't create the structure, it validates what rules already produced
- Prompt engineering for structured validation tasks
- Token-efficient design: sending a 200-token skeleton, not a 50,000-token book
- Optional AI: the system works without it, AI makes it better — this is the right dependency relationship

**Portfolio framing:** "Integrated an optional LLM review pass that validates structural inference using a ~200-token document skeleton — demonstrating efficient AI-augmented pipelines where ML enhances deterministic logic rather than replacing it."

---

## Software Engineering Skills

### Packaging, GUI & CLI Design

- Clean project structure with `pyproject.toml`, proper package layout
- PySide6 GUI design: signal/slot wiring, background `QThread` workers so the UI never blocks, tokenized QSS theming across 3 theme families
- Rich terminal CLI & Interactive Wizard: animated progress bars, live stage indicators, interactive prompts via Questionary, and directory scanning
- Standalone PyInstaller compilation (`mdook.spec`) and Linux FreeDesktop integration (`packaging/linux/`)
- Dependency management: core vs. optional (OCR engine) vs. dev dependencies
- Entry point distribution: `pip install mdook` → `mdook` launches the app (GUI or CLI based on display context)

### Data Modeling

- Pydantic schemas for every intermediate representation
- Type safety across pipeline stages
- Serialization to JSON for debugging and test fixtures
- Schema evolution: adding fields without breaking existing saved data

### Testing Strategy

- Unit tests per rule (given this text block with this font at this position, does the heading detector fire?)
- Integration tests per stage (given this PageData, does semantic analysis produce the expected DocumentTree?)
- End-to-end tests (given this publication, does the output library or single document match the expected output?)
- Test fixtures: curated PDFs covering known edge cases (drop caps, multi-column, symbol footnotes)
- Regression testing: when a new rule is added, old books don't break

### Open Source Project Management

- README that shows the tool in action (before/after comparisons)
- Clear contribution guidelines
- Issue templates for bug reports (attach the PDF, show expected vs. actual output)
- Versioning and changelog discipline
- License choice and its implications for distribution

---

## Domain Knowledge

### Book Structure Conventions

- How real books are organized (front matter → body → back matter)
- The difference between footnotes, endnotes, and parenthetical citations
- Why different books use different hierarchies (Parts, Chapters, Modules, Sections, Units)
- Drop caps, epigraphs, colophons, running headers — what they are and why they exist
- How academic books differ from trade nonfiction from literary fiction in their structural conventions

### Markdown & Obsidian Ecosystem

- Markdown syntax and its limitations (no merged cells, no absolute positioning)
- Obsidian-specific extensions: callouts, footnotes, wikilinks, YAML frontmatter, embedded images
- How the Obsidian community thinks about knowledge management
- Plugin development patterns for Obsidian (Phase 2)

### Typography & PDF Internals

- How fonts are embedded and referenced in PDFs
- What font metadata is actually reliable (size, weight) vs. unreliable (semantic role)
- How scanned vs. native PDFs differ at the data level
- Why PDF "text" isn't really text — it's positioned glyphs without guaranteed reading order

---

## Career Relevance Map

| Mdook Skill                   | AI Engineering Role Relevance                        |
| ----------------------------- | ---------------------------------------------------- |
| Document structure inference  | Information extraction, knowledge graph construction |
| Heuristic + ML hybrid systems | Production AI systems where pure ML isn't enough     |
| Pipeline architecture         | MLOps, data engineering, ETL pipeline design         |
| OCR integration               | Computer vision pipelines, multi-modal AI            |
| LLM-as-reviewer pattern       | AI-augmented workflows, human-in-the-loop systems    |
| Configuration-driven behavior | Feature flag systems, A/B testing infrastructure     |
| Token-efficient AI usage      | Cost-optimized LLM deployment, prompt engineering    |
| Open source project           | Community building, technical writing, collaboration |

---

## Skills Gap & Learning Path

### Already Strong (Based on Background)

- Python programming
- AI/ML concepts
- Git and version control
- Problem decomposition

### Developed During This Project

- Multi-format ingestion pipelines (PyMuPDF, pdfplumber, ebooklib, beautifulsoup4, python-docx)
- Heuristic design, profile tuning, and per-page OCR fallback chains
- Desktop GUI (PySide6), headless CLI (Rich), and interactive terminal wizard (Questionary)
- Obsidian companion plugin engineering (TypeScript, Obsidian API, IPC child process)
- LaTeX math detection and MathJax rendering (`$...$` and `$$...$$`)
- Standalone packaging with PyInstaller and Linux desktop integration

### Future Stretch Goals

- Web service architecture (headless HTTP conversion queue)
- Multimodal Vision-Language Model (VLM) diagram captioning and alt-text generation
- Visual graph and reading canvas overviews
