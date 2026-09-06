# Profiles

Mdook uses processing profiles to tune its heuristics for different book types. A profile controls which rules are active, how aggressive each heuristic is, and what output conventions to follow.

> **Update 2026-09-04, two corrections:**
> 1. **There is no CLI.** The project became a PySide6 desktop GUI from the first implementation sprint (see `ARCHITECTURE.md`) — the `Mdook convert ...` command-line examples throughout this file (and the corrupted `bookMdookvert`/`bookMdookmmand` text below and in the old `SKILLS.md`, an artifact of an earlier project rename) never shipped. The GUI exposes profile selection as a dropdown (`mdook/gui/window.py`'s `PROFILE_CHOICES`: Literature, Technical) instead. Read the command examples below as illustrating the *concept*, not a real invocation.
> 2. **Most rules added after the first implementation sprint don't actually read from `literature.toml`/`technical.toml` at all.** Font-size thresholds, indent ratios, column-gap ratios, OCR quality thresholds, and similar tuning constants for lists, block quotes, code detection, callouts, citations, math, multi-column reordering, and OCR live as hardcoded module-level constants in their own `mdook/core/rules/*.py` files instead (see `STACK.md`'s matching evolution note). Only numbered-section detection (technical-profile-only) and the multi-column literature-profile shortcut actually check the profile today. The tuning-parameter TOML blocks in this file below describe the *original design intent*, not current behavior — treat them as a spec for work not yet done, not documentation of what exists.

---

## Selecting a Profile

### GUI Dropdown (Always Wins)

The Profile dropdown in the main window (Auto-Detect / Literature / Technical) sets
`BookManifest.profile` for the conversion. The headless CLI supports `-p/--profile {auto,literature,technical}`
(defaulting to `auto`).

### Auto-Detection (Default when no explicit choice is made)

Implemented via `mdook/core/rules/profiles.py`. When `profile="auto"`, `mdook.core.stages.intake.run_intake`
(and the EPUB/DOCX ingestion modules) evaluate structural signals across the document:

| Signal                                        | Literature | Technical |
| --------------------------------------------- | ---------- | --------- |
| Table density (tables per 100 pages)          | < 2        | ≥ 2       |
| Numbered section headings (1.1.2 pattern)     | Absent     | Present   |
| Figure/table captions ("Figure X", "Table X") | Rare       | Frequent  |
| Monospaced code blocks / syntax keywords      | Absent     | Present   |
| Math symbols / equations                      | Absent     | Present   |

If signals are mixed or inconclusive, Mdook defaults to `literature` — it is the safer, less aggressive profile.

---

## Literature Profile

**Designed for:** Novels, literary nonfiction, essays, philosophy, history, biography, poetry collections, annotated editions, translated works.

### Active Rules

- Zone detection (all)
- Heading detection via font-size clustering + positional confirmation
- Drop cap immunity
- Header/footer detection and literal preservation
- Page-bottom footnote detection and correlation
- Paragraph merging with hyphen rejoin and cross-page continuation
- Epigraph detection
- Poetry/verse detection
- Block quote detection
- Decorative element filtering (ornaments → horizontal rules)
- Printed TOC discard

### Inactive Rules

- Numbered section detection (1.1.2 pattern) — literary books don't use this
- Multi-column processing — assumed single-column unless auto-detected on > 10% of pages
- Complex table fallback — literary books rarely have tables; if one appears, try simple markdown only

### Tuning Parameters

```toml
[headings]
min_font_size_ratio = 1.3    # heading must be ≥ 1.3× body font size
max_heading_words = 15       # longer than 15 words → probably not a heading
require_page_top = true      # H1 candidates must be in top 30% of page
position_weight = 0.7        # positional signals weighted higher (literary books are predictable)

[footnotes]
prefer_style = "page_bottom" # assume page-bottom footnotes unless endnotes detected
symbol_markers = true        # allow †, ‡, § as footnote markers

[paragraphs]
merge_aggressiveness = "high" # literary text is almost always continuous prose
detect_dialog = true          # detect quoted dialog and preserve line breaks

[images]
extract = true               # still extract images when they exist
decorative_filter = "aggressive" # literary books have more ornamental images to filter
```

---

## Technical Profile

**Designed for:** Textbooks, technical manuals, programming books, scientific reference works, academic monographs with heavy structure.

### Active Rules

- All rules from Literature profile, PLUS:
- Numbered section detection (1.1.2 pattern)
- Multi-column reading order
- Table detection (both simple markdown and complex HTML fallback)
- Vector diagram rasterization
- Figure/table caption association
- Code block detection (monospaced font → fenced code block)

### Additional Rules

#### Code Block Detection

- **Condition:** Text block uses a monospaced font (Courier, Consolas, Source Code Pro, etc.) AND is indented or set apart from body text
- **Action:** Render as a fenced code block. Attempt language detection from context (if the chapter discusses Python, assume Python):
  
  ```python
  def example():
      return True
  ```

#### Math/Formula Handling (Future — Phase 4)

- **Condition:** Text contains mathematical symbols, superscripts/subscripts forming equations, or LaTeX-like notation
- **Action:** For now, preserve as-is in plain text. Future: convert to LaTeX notation wrapped in `$...$` for Obsidian's MathJax support.

### Tuning Parameters

```toml
[headings]
min_font_size_ratio = 1.15   # technical books have subtler heading differences
max_heading_words = 20       # section titles can be longer ("3.2.1 Implementation of the Observer Pattern")
require_page_top = false     # sections often start mid-page
position_weight = 0.3        # numbering pattern is a stronger signal than position
number_pattern_weight = 0.9  # trust 1.1.2 numbering heavily

[footnotes]
prefer_style = "endnote"     # technical books more often use endnotes
symbol_markers = false       # technical books almost always use numbers

[paragraphs]
merge_aggressiveness = "medium" # code blocks, tables, and figures interrupt paragraphs more
detect_dialog = false           # technical books rarely have dialog

[tables]
detection_sensitivity = "high"     # actively look for tables on every page
complex_fallback = true            # enable HTML table rendering for merged cells
max_simple_columns = 8             # tables wider than 8 columns → HTML

[images]
extract = true
decorative_filter = "conservative"  # technical books have fewer ornaments, more meaningful figures
caption_search_radius = 40          # look farther for captions (technical layouts are varied)
vector_rasterize = true             # rasterize vector diagrams

[columns]
detect = true                       # actively check for multi-column layout
min_column_gap = 20                 # minimum horizontal gap (points) to count as separate columns
```

---

## Custom Profiles

**Not implemented** (`ROADMAP.md` Phase 5's "Custom profile support"). Also
notice that "poem titles are short" or "prioritize verse formatting" tuning
wouldn't currently do anything even if a custom-profile loader existed —
per the update note at the top of this file, the rules that would need to
read these specific keys (`max_heading_words`, `merge_aggressiveness`,
`verse_detection`) don't consult profile config today. Kept below as the
original design intent.

Users can create their own `.toml` profile files for specialized book types:

```bash
Mdook convert book.pdf --profile ./my-custom-profile.toml
```

A custom profile inherits all defaults from `literature` and overrides only what's specified. Example for an annotated poetry anthology:

```toml
# poetry-anthology.toml
inherits = "literature"

[headings]
max_heading_words = 8    # poem titles are short

[paragraphs]
merge_aggressiveness = "low"  # don't merge lines — poetry needs line breaks preserved
detect_dialog = false

[footnotes]
prefer_style = "page_bottom"
symbol_markers = true

[special]
verse_detection = "aggressive"  # prioritize verse formatting
epigraph_detection = true
```

---

## Profile Override per Section

**Not implemented** — still a future idea, correctly labeled as such in
the original text below; nothing has changed here. Allow a book to switch
profiles mid-document. Example: a book with literary chapters but a
technical appendix. The zone detection could trigger a profile switch:

```toml
# In the book's override config
[zone_overrides]
back_matter_profile = "technical"  # use technical rules for appendices
```

This is a Phase 4 feature — not needed for initial release.
