# Mdook

**Convert PDF books into structured, readable Obsidian vaults.**

> **New AI assistant on this project? Read `Mdook-docs/HANDOFF.md` first.**
> It covers traps a fresh read of these docs is likely to fall into.

> **Status refreshed 2026-09-04** (see "Project Status" at the bottom —
> this file's Vision/Target Users/Success Metrics sections below are
> still the original pre-implementation plan and remain accurate as
> aspiration; only "Distribution Plan," "Build Phases," and "Project
> Status" described the wrong reality and have been corrected).

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

**This section is superseded by `Mdook-docs/ROADMAP.md`, which is the
current, actively-maintained phase tracker with real completion status.**
The original 4-phase sketch below is kept for historical context only —
don't treat it as current; `ROADMAP.md` has since grown to 6 phases plus a
completed 6-batch gap-filling program (Batches 14-19) that this sketch
never anticipated.

### Phase 1 — Literary Books with Text Layer *(done)*
### Phase 2 — Technical Profile *(done)*
### Phase 3 — OCR Fallback *(done, via Tesseract — see `STACK.md`)*
### Phase 4 — Polish & Edge Cases *(originally planned here; in `ROADMAP.md` this became Batches 14-19, now complete, plus a still-open Phase 5)*

---

## Success Metrics

- A converted book is readable *as a book* — you'd actually sit and read it in Obsidian, not just search it
- An AI given a chapter file can discuss its content without confusion from formatting artifacts
- The tool handles structural variety (chapters, modules, parts, named sections, unnumbered divisions) without hardcoded assumptions about what books "should" look like
- The GitHub repo earns genuine engagement (stars, issues, PRs) from the Obsidian/PKM community — not yet applicable, no repo exists yet

---

## Vision Discussion — What's Left (as of 2026-09-04)

Beyond `ROADMAP.md`'s Phase 5 (polish) and Phase 6 (distribution ideas),
active discussion is underway on:

- **Multi-format input** — EPUB3 first (already scoped as Phase 4 in
  `ROADMAP.md`, deliberately deferred until Phase 5 and a GitHub push are
  done), with the `DocumentTree` abstraction meant to make a second format
  a real test of whether it's genuinely format-agnostic.
- **AI/LLM integration, broadened to OpenAI-compatible APIs** — the
  original "AI structure review" idea (`ROADMAP.md` Phase 5) named Claude
  API or local Ollama specifically. Direction now under discussion:
  target the OpenAI-compatible chat-completions API shape generically
  (base URL + API key + model name, configurable) instead of a
  provider-specific client, since OpenAI itself, Ollama, LM Studio, vLLM,
  Groq, and most local inference servers all speak that same shape — one
  HTTP client covers all of them with no extra dependency per provider.
- **Long-term testing and improvement** — an ongoing practice, not a
  single feature: keep growing the real-book test library (`ROADMAP.md`'s
  "Testing Strategy" section) as new edge cases turn up, the same way
  every batch so far has been real-book-verified, not just unit-tested.
- **Website / hosted service support** — revisits the "Phase 3 — Web
  Service" idea above (upload a PDF, get a vault back). Not yet scoped in
  detail; worth a dedicated design pass before committing to it, since it
  implies real infrastructure (hosting, storage, possibly billing) that
  the rest of this project doesn't need.
- **Visual "presentation templates" for the rendered vault** — a newer
  idea, not yet designed: rendering a book into more visually distinctive
  Obsidian notes (via CSS snippets and/or richer use of Obsidian's own
  markdown extensions) rather than the current plain, uniformly-styled
  output, for both Obsidian and the user's own custom Obsidian-like
  application. This has a real tension with this project's founding
  principle — "efficient for AI models to reason about without wasting
  tokens on layout noise" — that needs to be resolved deliberately, not
  accidentally: the leaning discussed so far is to keep the plain,
  semantic markdown as the non-negotiable default output, and add any
  visual theming as a strictly optional, additive layer (e.g. a companion
  CSS snippet file shipped alongside the vault) rather than embedding
  heavy inline HTML/CSS into the content itself. Not yet started; revisit
  once the target application's actual rendering capabilities (does it
  support CSS snippets? custom markdown syntax? plain HTML embeds?) are
  known.

---

## Project Status

**As of 2026-09-04:** the full original implementation plan is complete —
Phases 1-3 (literary + technical PDF conversion, multi-column, tables,
footnotes/endnotes, and Tesseract-based OCR) plus a follow-on 6-batch
program (Batches 14-19) that closed real structural/content/robustness
gaps found by auditing `Mdook-docs/BOOK_ELEMENTS.md`'s ~333-element catalog
against the actual codebase: Parts/Books/Volumes divisions, callout/
sidebar boxes, citation-to-bibliography linking, image caption association
and vector-diagram rasterization, math/formal notation (Obsidian MathJax),
non-Latin script/RTL/vertical-text robustness, and encrypted/corrupt-PDF
handling. 200+ tests passing, `ruff` clean. The desktop GUI has also had a
full pass: a working light/dark theme, discoverable drag-and-drop, and a
real sequential multi-file conversion queue.

**Not started:** EPUB/multi-format input (Phase 4, deliberately deferred),
most of Phase 5's polish items (AI structure review, poetry/verse
handling, glossary/bibliography file structuring, profile auto-detection,
custom profile file support), and everything in Phase 6 (distribution).
**No git repository exists yet** for this project — version control and a
GitHub push are planned once Phase 5 is further along, not before.

See `Mdook-docs/ROADMAP.md` for the authoritative, continuously-updated
phase-by-phase task list and completion status, and `Mdook-docs/RULES.md`
for the full detection-rule catalog with real-book bug-fix history.
