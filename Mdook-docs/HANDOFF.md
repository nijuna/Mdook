# Handoff Notes

**For an AI assistant picking up this project with no memory of prior
sessions.** Everything here was previously tracked only in Claude Code's
private, per-machine memory system — invisible to any other tool or model.
This file ports the useful, non-tool-specific parts of that into the repo
itself, written 2026-09-04 when the project moved from Claude to Gemini.

If anything in these docs is unclear, or contradicts what you find by
reading the actual code in `mdook/`, say so and ask rather than guessing
or silently picking one version — that's expected and welcome, not a sign
you missed something you should already know.

---

## Quick start — verify the environment before reading further

```bash
uv sync --extra dev      # installs runtime + dev deps (pytest, ruff)
uv run pytest -q         # should show 268 passed
uv run ruff check .      # should show "All checks passed!"
uv run python -m mdook   # launches the GUI (or: uv run mdook convert ...)
```

If any of these don't match, the environment differs from what this
handoff describes — figure out why before trusting the rest of this file.

### Quick facts

- **Both Desktop GUI and Headless CLI** — PySide6 GUI (`mdook`, `mdook gui`,
  `python -m mdook`) and Rich headless CLI (`mdook convert book.pdf -o ./vaults/`).
- **OCR engine is Tesseract** (a system package, not pip-installed —
  `sudo dnf install tesseract` / `sudo apt install tesseract-ocr`),
  routed per-page, not per-book.
- **AI Structure Review** — Implemented in Phase 5 via `mdook/core/llm/`
  with zero-dependency OpenAI-compatible client, `/models` discovery,
  and connection test latency measurement.
- **Poetry & Verse Handling** — Implemented in Phase 5 via `mdook/core/rules/verse.py`
  (Rule 9.2), preserving line breaks and stanza structure.
- **Back-Matter File Splitting** — Implemented in Phase 5 via `mdook/core/stages/rendering.py`,
  splitting back-matter into dedicated notes (`Notes.md`, `Bibliography.md`, `Glossary.md`,
  `Appendix.md`) with direct cross-file anchors (`^note-N`, `^ref-N`).
- **Structured Glossary Processing** — Implemented in Phase 5 via `mdook/core/rules/glossary.py`
  (Rule 9.6), structuring glossary entries into clean `**Term** — Definition` paragraphs,
  preserving letter dividers (`## A`, `## B`), and rejoining hyphenated multi-line definitions.
- **Headless CLI Command** — Implemented in Phase 5 via `mdook/cli.py`, supporting
  `mdook convert <pdf...> -o <vaults/>` with Rich progress bars and validation tables.
- **~2,800 lines across 9 docs in `Mdook-docs/`**, all current as of
  2026-09-06 — see the reading order below.
- **268 tests, `ruff` clean**, as of the same date.


---

## Read the docs in this order

1. **This file** — orientation and traps to avoid.
2. **`PROJECT.md`** — vision, what the tool does/doesn't do, current status,
   and the "Vision Discussion" section (open questions awaiting the user's
   input — read that before proposing new features).
3. **`ARCHITECTURE.md`** — the real five-stage pipeline, current data
   models, GUI structure, directory layout. Rewritten from the actual code
   on 2026-09-04; trust this over anything that contradicts it.
4. **`RULES.md`** — the full detection-rule catalog (17 sections). This is
   where almost all the real engineering judgment lives, including
   specific real-book bugs that shaped each rule. Read the section for
   whatever you're about to touch before changing it.
5. **`STACK.md`** — which libraries are actually used vs. planned-but-abandoned.
6. **`ROADMAP.md`** — phase-by-phase task list with real completion status.
7. **`PROFILES.md`, `SKILLS.md`, `BOOK_ELEMENTS.md`** — lower priority;
   read on demand.

---

## The single most important thing to know

**These docs were written *before* implementation, as a plan, and the
plan changed a lot.** Two conventions exist for showing that:

- `RULES.md` and `STACK.md` preserve the original planning text and add
  `> **Update:**` callouts next to whatever it got wrong, so the "why we
  ended up somewhere else" history stays visible. When you touch a rule
  covered by one of these, read the callout — it usually explains a real
  bug that a synthetic test didn't catch.
- `PROJECT.md` and `ARCHITECTURE.md` had drifted so far from reality
  (describing a CLI that was never built, an OCR engine that was never
  used) that annotating them stopped making sense — they were rewritten
  from the real code instead. Treat them as current-state references, not
  historical narrative.

**Practical consequence: don't trust a doc's description of "what Mdook
does" over the actual code in `mdook/`.** If they disagree, the code is
right and the doc needs fixing — that's true even of this file eventually.

---

## Specific traps a fresh read is likely to fall into

- **There is no CLI.** The project became a PySide6 desktop GUI
  (`mdook/gui/`) in the very first implementation sprint and stayed that
  way. Several docs still show `Mdook convert book.pdf --profile ...`
  command examples — those never shipped and never will unless someone
  deliberately adds a CLI entry point later.
- **OCR is Tesseract, not Marker/pdf-craft.** The original plan's OCR
  section recommended Marker; the actual target machine was CPU-only, and
  Tesseract's plain word+bbox output maps directly onto the existing
  `TextBlock` schema, so it was chosen instead. See `STACK.md`'s "OCR
  Engines" evolution note for the full reasoning — it's a real design
  decision, not a shortcut.
- **Most rules don't read the `.toml` profile files.** `mdook/profiles/
  literature.toml` and `technical.toml` exist, but font-size thresholds,
  indent ratios, and similar tuning constants for most rules added after
  the first sprint are hardcoded in their own `mdook/core/rules/*.py`
  files instead. Only numbered-section detection and the multi-column
  literature shortcut actually check the profile today.
- **`BOOK_ELEMENTS.md`'s status column is stale and shouldn't be trusted
  blindly.** It was audited once (2026-09-03) against the real codebase
  and found to under-report what was actually built (e.g. it listed
  "Lists (bulleted)" as `[new]` when they'd been implemented for a while).
  If you need to know whether something is really implemented, grep the
  code or check `RULES.md`/`ROADMAP.md`, not this file's status column.
- **Git repository initialized and hosted on GitHub.** The repository is
  version-controlled at `origin` (`https://github.com/nijuna/Mdook`), on
  branch `main`. Releases and CI workflows are active via GitHub Actions.

---

## How this codebase was actually developed (useful working method, not just history)

- **Real books over synthetic fixtures, always as a follow-up check.**
  Every batch of work in `ROADMAP.md`'s history was unit-tested with
  synthetic fixtures *and then* spot-checked against real PDFs from the
  user's own collection before being called done. Several real,
  non-obvious bugs were found this way that no synthetic test had caught
  (see `RULES.md`'s evolution notes for specific examples — OCR font-size
  jitter promoting garbage text to chapter titles, a header/footer
  detector that never fired on OCR'd text because Tesseract misreads a
  few characters differently every page, a union-find clustering bug that
  only showed up on an ordinary two-box flowchart, and others). If you
  implement something new, do the same: unit tests for the logic, then at
  least one real-book (or realistic synthetic) check before considering
  it done. A passing unit test on invented data is not the same claim as
  "this works."
- **Batches, not files.** Work was scoped into small, independently
  testable batches (see `ROADMAP.md`'s "Batches 14-19" section for the
  clearest example) — each one lands with its own tests, its own
  real-book verification, and its own doc updates, rather than large
  unreviewed changes.
- **Docs get updated in the same batch as the code**, not after the fact
  in bulk. If you build something, update the relevant `RULES.md` section
  (or add a new numbered section, following the existing pattern) and
  `ROADMAP.md`'s checklist in the same piece of work.

---

## Open questions the user still needs to answer (don't assume)

From `PROJECT.md`'s "Vision Discussion" section, as of 2026-09-04:

1. **Visual presentation templates** — the user wants to explore making
   converted books render more visually distinctively (CSS/HTML-based
   "themes") for Obsidian and their own custom Obsidian-like app. This is
   explicitly *not yet designed*, and has a real, acknowledged tension
   with the project's founding principle of staying maximally AI-readable
   (heavy inline HTML/CSS makes markdown noisier for a model to parse).
   The recommended direction so far — keep plain semantic markdown as the
   default, add theming as an optional companion layer (e.g. a separate
   CSS snippet file) rather than embedding it in content — is a
   *recommendation*, not a decision. **Genuinely blocking question:** what
   does the user's custom Obsidian-like app actually support rendering-
   wise (CSS snippets? its own markdown extensions? raw HTML embeds?).
   Ask before designing anything here.
2. **Website/hosted service support** — revisits `PROJECT.md`'s original
   "Phase 3 — Web Service" idea. The user said "maybe" and wanted to
   discuss it further; it hasn't been decided whether this is still
   wanted or just legacy content from the pre-implementation plan.
3. **OpenAI-compatible LLM API** — this one *is* a settled direction (not
   open): generalize the "AI structure review" idea beyond Claude/Ollama
   to any OpenAI-compatible chat-completions endpoint (configurable base
   URL + API key + model name), so one HTTP client covers OpenAI, Ollama,
   LM Studio, vLLM, Groq, etc. Not implemented yet, but the shape is
   agreed — just needs building.
