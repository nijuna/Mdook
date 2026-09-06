# Rules

The semantic analysis ruleset — every heuristic Mdook uses to turn raw extracted blocks into a meaningful document structure.

Rules are organized by the problem they solve. Each rule has a condition (when it fires), an action (what it does), and known failure modes (when it gets it wrong).

> **How to read this file:** written before implementation started, as a plan. Blockquote callouts like this one, placed next to the rule they update, show what actually happened once real code and real books tested these ideas — most rules below were built close to as written, but several needed real calibration real books forced (bad heading detection, false-positive block quotes, a TOC-discard heuristic that ate whole chapters), a few were deliberately simplified, and some genuinely new rules (Lists, Code Blocks) had no home in the original 1-10 numbering at all and are appended at the end. Nothing below is deleted or silently rewritten — these docs were always meant as a starting point to deviate from based on real-world testing, not a binding spec.

---

## 1. Zone Detection

**Goal:** Classify every page as `front_matter`, `body`, or `back_matter` before any content analysis begins.

### Rule 1.1 — Page Number Style Boundary

- **Condition:** Pages transition from roman numerals (i, ii, iii, iv) to arabic numbers (1, 2, 3)
- **Action:** Everything before the transition is `front_matter`, the transition page starts `body`
- **Failure mode:** Some books use no page numbers in front matter at all. Fall back to Rule 1.2.

### Rule 1.2 — Keyword Scanning (Front)

- **Condition:** Pages in the first 15% of the document contain keywords: "Table of Contents", "Contents", "Preface", "Foreword", "Dedication", "Acknowledgments", "Copyright", "Published by", "ISBN", "All rights reserved"
- **Action:** Mark those pages as `front_matter`. The first page after the last front-matter keyword page that has normal body text formatting starts `body`.
- **Notes:** Match case-insensitively. "CONTENTS" and "Contents" are the same signal.

### Rule 1.3 — Keyword Scanning (Back)

- **Condition:** Pages in the last 20% of the document contain keywords: "Bibliography", "References", "Works Cited", "Glossary", "Index", "Notes", "Endnotes", "Appendix", "About the Author", "Acknowledgments" (when at the back)
- **Action:** Mark from the first back-matter keyword page onward as `back_matter`.
- **Failure mode:** "Notes" is ambiguous — could be a chapter title. Require it to be followed by numbered note entries, not prose.

### Rule 1.4 — Title Page Detection

- **Condition:** One of the first 5 pages contains: text significantly larger than body font, centered horizontally, with very little other text on the page
- **Action:** Mark as `front_matter`, extract text as candidate book title and author.
- **Not implemented.** Title comes from PDF metadata instead (see Rule 1.4's own note being superseded in practice — `mdook/core/stages/intake.py`'s `_clean_metadata_title`), with a fallback to the filename when the metadata title is garbage (found via a real book whose title was a URL-encoded file path).

> **Update: this whole zone map was computed at intake (Stage 1) but never actually consulted anywhere downstream, for the entire first several implementation batches.** Rules 1.1-1.3 as described here were built essentially as written (`mdook/core/rules/zones.py`), but `BookManifest.zone_map` just sat there unused until a real book (a 500+ page occult text with a decorative cover page) exposed why that mattered: a giant cover-page font was dominating the whole-book font-size histogram used for heading detection (Rule 2.2), starving real chapter headings of a tier slot. Fixing it required wiring `zone_map` into Stage 3 so font clustering scopes to the `body` zone specifically — see Rule 2.2's update below. The same fix also let genuinely orphaned front/back-matter pages (a page with no chapter heading of its own) get preserved as named sections instead of silently vanishing from the vault, which nothing in this original section anticipated needing.

---

## 2. Heading Detection

**Goal:** Identify chapter titles, section headings, and sub-headings. Map them to a consistent hierarchy (H1, H2, H3).

### Rule 2.1 — Bookmark-Based Hierarchy (Preferred)

- **Condition:** `BookManifest.bookmarks` is not None and has ≥ 3 entries
- **Action:** Trust bookmarks completely. Map bookmark depth 1 → H1, depth 2 → H2, depth 3 → H3. For each bookmark, find the nearest text block on the target page that matches the bookmark title (fuzzy match — bookmarks sometimes abbreviate). Tag that block as a heading at the corresponding level.
- **Skip:** All font-based heading heuristics (Rules 2.2–2.5). Bookmarks are authoritative.

### Rule 2.2 — Font-Size Clustering

- **Condition:** No usable bookmarks. Collect all text blocks in the `body` zone.
- **Action:**
  
  1. Build a frequency histogram of font sizes across all body-zone text blocks.
  
  2. The most frequent font size is `body_font_size`.
  
  3. Identify font sizes that appear significantly less frequently and are *larger* than `body_font_size`. These are heading candidates.
  
  4. Cluster heading candidates into tiers by size:
     - Tier 1 (largest, least frequent) → H1 candidate
     - Tier 2 → H2 candidate
     - Tier 3 → H3 candidate
  
  5. Require at least a 1.5pt difference between tiers to count as distinct. Tiers within 1pt are merged.

> **Implementation details:**
> 1. **Body-zone scoping.** Text blocks are analyzed specifically within the `body` zone for the font-clustering path; bookmark-based heading detection (Rule 2.1) operates whole-book.
> 2. **Chapter-tier selection.** Rather than assuming the single largest font tier is always the chapter heading, Mdook picks the smallest tier with at least 2 occurrences as the chapter tier, falling back to tier 1 only if nothing qualifies (`mdook/core/stages/semantic.py`'s `_pick_chapter_tier`).
> 3. **Sub-heading nesting.** Tiers not chosen as the chapter tier nest as sub-sections (`H2`/`H3`).
> 4. **Part/Book tier gating:** A tier is only skipped as "Parts, not chapters" if its headings match Part/Book/Volume patterns (`PART_LABEL_RE` / `_looks_like_part_tier`), ensuring true multi-part divisions are preserved above chapters.

### Rule 2.3 — Positional Confirmation

- **Condition:** A text block is a heading candidate from Rule 2.2
- **Action:** Promote to confirmed heading only if it passes at least 2 of:
  - Appears within the top 30% of the page vertically
  - Is preceded by a page break or significant vertical whitespace (> 2× normal line spacing)
  - Is short (≤ 15 words)
  - Is followed by body-sized text within normal paragraph spacing
  - Is bold, uppercase, small-caps, or uses a different font family than body text
- **Failure mode:** Chapter titles that appear mid-page (some literary books don't start chapters on new pages). Lower the positional requirement for H2/H3 — only H1 should strongly prefer page-top.

> **OCR & Script Considerations:**
> - On OCR-processed pages (`PageData.was_ocrd`), font height variation from ascenders/descenders can produce false heading candidates. In `_confirm_heading`, uppercase is mandatory when `was_ocrd` is true.
> - For caseless scripts (CJK, Arabic, Hebrew, Devanagari, Thai) where `str.isupper()` does not apply (`mdook/core/rules/scripts.py`'s `is_caseless_text`), this guard is exempted, falling back to signal-count scoring.

### Rule 2.4 — Numbered Section Detection (Technical Profile)

- **Condition:** Profile is `technical`. Text block matches pattern: `^\d+(\.\d+)*\s+\S`
- **Action:** The number of dot-separated segments determines the level:
  - `1` or `1.` → H1
  - `1.1` → H2
  - `1.1.1` → H3
  - `1.1.1.1` → H4 (rare, but exists in some textbooks)
- **Notes:** This overrides font-size clustering for numbered headings. A "Chapter 1" heading without the dot-numbering pattern uses font-size rules instead.

### Rule 2.5 — Drop Cap Immunity

- **Condition:** A single character block with font size ≥ 2× `body_font_size`, positioned at the top-left of a paragraph
- **Action:** Do NOT classify as a heading. Merge into the first paragraph's text as the initial character.
- **Key signal:** It's a single character (length = 1), and the text block immediately to its right or below starts with a lowercase letter continuing a word.

### Rule 2.6 — Heading Text Preservation

- **Condition:** Any confirmed heading
- **Action:** Preserve the book's exact heading text. Do not normalize, rename, or re-number. If the book says "MODULE THREE", the markdown heading is `# MODULE THREE`. If it says "3", the heading is `# 3`. If it says "The Sound and the Fury", the heading is `# The Sound and the Fury`.
- **Rationale:** The tool mirrors the book's structure; it does not impose one.

> **Update: one deliberate, narrow exception to "preserve exact text," added after this rule caused a real bug.** Some books typeset the chapter number as its own oversized element with the real title set separately underneath (e.g. a huge "9" with "Creative Problem Solving" in smaller bold text below it) — font clustering only sees the number as the size outlier, so three chapters in a real book ended up titled just "9", "11", "12" with the actual title silently dropped. Fixed by detecting a bare number/roman-numeral/"Chapter N" heading and absorbing the very next text block as the real title *only if it looks like a title* (bigger than body text or bold) rather than body prose — otherwise a genuinely bare-numeral chapter ("Chapter IX", no separate title at all) would swallow the opening words of its own first paragraph. `mdook/core/stages/semantic.py`'s `_merge_chapter_number_titles`. This is a case of *recovering* the book's own text that extraction had accidentally split apart, not imposing new text — consistent with this rule's rationale, just not something the original wording anticipated.

---

## 3. Header & Footer Detection

**Goal:** Identify running headers (book title, chapter title, author name) and page numbers that repeat across pages. Remove from content flow, preserve as page markers.

### Rule 3.1 — Repeating Band Detection

- **Condition:** Text appearing in the top 8% or bottom 8% of the page, with the same or very similar content on ≥ 5 consecutive pages
- **Action:** Classify as header (top band) or footer (bottom band). Strip from content blocks.
- **Notes:** "Very similar" accounts for alternating headers (odd pages show chapter title, even pages show book title). Compare within odd-page and even-page groups separately.

> **Update: "very similar" was never actually implemented until Phase 3 (OCR) forced the issue.** `mdook/core/rules/headers_footers.py` originally grouped candidates by exact normalized-text equality (digit-masked, whitespace-collapsed) — fine for native PDFs, where a running header repeats byte-for-byte, but Tesseract misreads a handful of characters differently on *every* page of a scanned book (`"THURLOW WEED ON..."`, `"...OM THE MORGAN ABDEUOTION."`, `"...WHED ON..."`), so exact matching never reached the 5-page threshold and the header leaked into the body of every single page. Fixed with `difflib.SequenceMatcher`-based clustering (similarity ≥ 0.82) instead of exact equality — this is what the "very similar" language above was already describing for the alternating-header case, just not built that way originally. Separately, the 8%/8% band itself was widened to 15%/15%: a scanned page's canvas has a wider blank border around the actual printed area than a tightly-cropped native PDF, and a real book's header measured 9-13% down from the page top. The wider band is safe for native PDFs too since a candidate still only strips if it *also* repeats — an ordinary paragraph's first line never does.

### Rule 3.2 — Page Number Extraction

- **Condition:** A short text block (1–4 characters) in the header/footer band that matches a sequential number pattern across pages
- **Action:** Extract as `page_number`. Attach to `PageData`.
- **Notes:** Some books use roman numerals in front matter. Handle both.

### Rule 3.3 — Page Marker Rendering

- **Condition:** A page boundary occurs between content blocks
- **Action:** Insert a collapsed Obsidian callout:
  
  ```
  > [!quote]- p. 142 · Book Title, Ch. 3
  ```
  
  The callout contains the original header/footer text exactly as printed. Collapsed by default so it doesn't disrupt reading.

---

## 4. Footnote & Endnote Detection

**Goal:** Identify footnotes, correlate them with their in-text markers, and format them appropriately.

### Rule 4.1 — Page-Bottom Footnote Detection

- **Condition:** Text block(s) meeting ALL of:
  - Font size smaller than `body_font_size` (typically 1–3pt smaller)
  - Positioned in the bottom 25% of the page
  - Preceded by a horizontal rule or significant vertical gap
  - Begins with a number, asterisk, or symbol (†, ‡, §, ¶)
- **Action:** Extract as `Footnote` with `style: page_bottom`. Associate the leading number/symbol as the `marker`.

### Rule 4.2 — Superscript Marker Detection

- **Condition:** A text span with `is_superscript: true` and content matching a number or symbol
- **Action:** Record as a footnote reference. Match to the `Footnote` with the same `marker` on the same page.
- **Failure mode:** OCR often fails to detect superscript. Fallback: look for a bare number immediately following a word with no space, where that number matches a footnote marker on the same page.

### Rule 4.3 — Endnote Detection

- **Condition:** A `back_matter` section titled "Notes" or "Endnotes" containing numbered entries grouped by chapter
- **Action:** Extract each entry as `Footnote` with `style: endnote`. Chapter-scope the numbering (note "14" in Chapter 3 is different from note "14" in Chapter 5). Create block references for linking:
  
  ```
  ...the treaty was signed.[[Notes#^c3-14|¹⁴]]
  ```

> **Update: implemented with book-wide numbering, not chapter-scoped — a deliberate simplification, decided in discussion rather than found as a bug.** Chapter-scoping would require sub-dividing the Notes section by chapter headers and tracking which chapter each inline marker occurs in; most non-academic books use one continuous endnote sequence for the whole book, where the collision this rule worries about never arises. Detection lives in `mdook/core/rules/footnotes.py`'s `detect_endnote_markers`. The link format also differs from the example above: `[[99 - Back Matter#^note-14|14]]` (a fixed back-matter filename and a simple `^note-N` anchor) rather than a per-chapter `Notes.md#^c3-14` — same idea, simpler scheme. Chapter-scoped numbering remains a known, accepted gap if a book that actually restarts numbering per chapter ever turns up.

### Rule 4.4 — Footnote Placement in Markdown

- **Condition:** `style: page_bottom`

- **Action:** Use Obsidian's native footnote syntax. Place the `[^n]` marker inline in the text. Place the definition (`[^n]: text`) at the bottom of the page's content block (after the page marker callout for that page, before the next page marker).

- **Condition:** `style: endnote`

- **Action:** Keep the in-text marker as a link to `Notes.md` with a block reference. Render the notes section as a separate file organized by chapter.

> **Update: rendered into dedicated files per back-matter section** (e.g. `Notes.md`, `Bibliography.md`, `Glossary.md`), not a shared monolithic back-matter file. In-text endnote markers link directly to `[[Notes#^note-N|N]]` (or whatever the notes file's actual title stem is), and bibliography citations link to `[[Bibliography#^ref-N|N]]`. If a book only has untitled generic back matter, it falls back to `Back Matter.md`. `mdook/core/stages/rendering.py`.

### Rule 4.5 — Symbol Footnote Normalization

- **Condition:** Footnote markers use symbols (†, ‡, §) instead of numbers
- **Action:** Preserve the original symbols in both the marker and the definition. Do not convert to numbers — fidelity to the book matters here.

---

## 5. Paragraph Merging

**Goal:** Combine fragmented text blocks into coherent paragraphs. Raw extraction often splits a single paragraph across multiple blocks.

### Rule 5.1 — Same-Font Continuation

- **Condition:** Two consecutive text blocks share the same `font_name`, `font_size`, and `is_bold`/`is_italic` flags. No heading, image, table, or footnote block between them.
- **Action:** Merge into a single paragraph. Join with a space.

### Rule 5.2 — Hyphenated Line Rejoin

- **Condition:** A text block ends with a hyphen (`-`) and the next block starts with a lowercase letter
- **Action:** Remove the hyphen and join the two words: `"extraordi-" + "nary"` → `"extraordinary"`
- **Exception:** Do not rejoin if the hyphen is part of a compound word that legitimately uses a hyphen (e.g., "well-known"). Heuristic: if the joined word exists in a dictionary and the hyphenated form does not appear elsewhere in the book as a compound, rejoin.

### Rule 5.3 — Cross-Page Paragraph Continuation

- **Condition:** The last text block on page N ends without terminal punctuation (no `.`, `!`, `?`, `:`) AND does not fill the full line width (text doesn't reach within 90% of the right margin)
- **Actually, reverse that:** If the last block DOES reach the right margin and lacks terminal punctuation, the paragraph continues on the next page. If it ends short of the right margin WITH terminal punctuation, the paragraph ends.
- **Action:** Merge the last block of page N with the first block of page N+1 (assuming same font).
- **Failure mode:** Poetry, block quotes, and dialog can end lines without punctuation mid-page. Combine with font/style check.

### Rule 5.4 — Paragraph Boundary Detection

- **Condition:** The next text block starts with a first-line indent (x-position shifted right by ~1em compared to subsequent lines) OR extra vertical spacing (> 1.5× normal line spacing) separates two blocks
- **Action:** Start a new paragraph. Do not merge.

---

## 6. Table Processing

**Goal:** Extract tables, classify their complexity, and render them in the best available markdown format.

### Rule 6.1 — Table Detection

- **Condition:** pdfplumber finds a region bounded by lines forming a grid pattern
- **Action:** Extract cell contents into a 2D array.

### Rule 6.2 — Simple Table Rendering

- **Condition:** No merged cells. No cell contains more than ~80 characters. Column count ≤ 8.
- **Action:** Render as a standard markdown pipe table:
  
  ```
  | Col A | Col B | Col C |
  |-------|-------|-------|
  | data  | data  | data  |
  ```

### Rule 6.3 — Complex Table Fallback

- **Condition:** Table has merged cells, multi-line cells, nested structure, or > 8 columns
- **Action:** Render as an inline HTML `<table>` block in the markdown file. Obsidian renders HTML natively. This preserves data integrity over formatting elegance.

### Rule 6.4 — Table Caption Association

- **Condition:** A text block immediately above or below a table matches pattern: "Table \d+" or "TABLE \d+" or starts with a label-like prefix
- **Action:** Include as a caption line above the rendered table.

> **Update: no dedicated code for this — and testing suggests none was needed.** A caption text block already sits immediately adjacent to its table in reading order once Stage 3 slots the table into the content stream by position (same mechanism Rule 8.2's column-spanning elements use). That already reads correctly without any pattern-matching or special-casing. Revisit only if real books turn up cases where this natural adjacency isn't enough (e.g. a caption genuinely far from its table).

---

## 7. Image & Figure Handling

**Goal:** Extract images, associate captions, filter decorative junk, save with meaningful filenames.

### Rule 7.1 — Embedded Image Extraction

- **Condition:** PyMuPDF `get_images()` returns image references on a page
- **Action:** Extract and save to temp directory. Record bounding box.

### Rule 7.2 — Vector Diagram Rasterization

- **Condition:** A page region contains PDF drawing operators (paths, fills) but no extracted image covers that region. The region is larger than 50×50 points.
- **Action:** Rasterize just that region of the page at 300 DPI. Save as PNG.

> **Implementation details:** `page.get_drawings()` returns one rect *per individual path* (a flowchart's two boxes and connecting line are three separate rects, not one), so diagrams have their pieces clustered into a single region using union-find clustering over all pairwise-close rects (`mdook/core/rules/images.py`'s `cluster_drawing_regions`). A resulting region is excluded if it overlaps an already-extracted raster image *or* a detected table's bbox, preventing vector gridlines from rasterizing duplicate tables.

### Rule 7.3 — Caption Association

- **Condition:** A text block within 30pt vertically of an image's bounding box matches patterns: "Figure \d+", "Fig. \d+", "Diagram \d+", "Illustration", or is italic/smaller text directly below the image
- **Action:** Associate as the image's caption. Use figure number for filename: `fig-3-2.png`

> **Implementation details:** `mdook/core/rules/images.py`'s `find_caption` checks both below *and* above an image (accommodating plate captions set above), matching a fixed label set (Figure/Fig./Diagram/Illustration/Plate). The matched caption `TextBlock` is removed from the page's ordinary text flow to prevent duplicate paragraphs. The figure-number-based filename (`extract_figure_number`) is used when available, falling back to chapter/index-based schemes (`mdook/core/stages/semantic.py`'s `_figure_id`).

### Rule 7.4 — Decorative Image Filtering

- **Condition:** Image is smaller than 80×80 pixels, OR appears on > 3 pages at the same position (likely a publisher logo or ornament), OR is positioned in the header/footer band
- **Action:** Discard. Do not save to attachments folder.

> **Update: one more condition added, and it turned out to matter more than anything in the original list.** Two real scanned books (a 75-image and a 168-image count before the fix) revealed that a scanned book's underlying page-photo is embedded as one full-page image on *every single page* — extracting those bloats the vault's attachments folder with a duplicate of the entire book and multiplies conversion time for no benefit. Added: an image covering ≥90% of the page area is treated as a scan background and discarded, same as this rule's other conditions. `mdook/core/stages/extraction.py`'s `FULL_PAGE_IMAGE_AREA_RATIO`. After the fix, those two books' image counts dropped to 3 and 4 respectively.

### Rule 7.5 — Image Reference in Markdown

- **Action:** Insert `![[fig-3-2.png]]` in the chapter file at the position where the image appeared. If a caption exists, include it on the line below:
  
  ```
  ![[fig-3-2.png]]
  *Figure 3.2: Cross-section of the engine assembly*
  ```

---

## 8. Multi-Column Reading Order

**Goal:** Reconstruct correct reading order when text is laid out in multiple columns.

### Rule 8.1 — Column Detection

- **Condition:** On a given page, text blocks cluster into 2+ distinct x-position ranges with a vertical gap between them
- **Action:** Group blocks by column (by x-range). Sort within each column by y-position. Concatenate columns left-to-right.
- **Do NOT:** Sort all blocks by y-position globally — this interleaves columns into nonsense.

### Rule 8.2 — Column Span Detection

- **Condition:** A text block spans the full page width (its x-range covers > 80% of the page)
- **Action:** Treat as a column-spanning element (typically a heading or figure). Process it at the y-position where it appears, before continuing with the columns below it.
- **Extended in practice:** images and tables are treated as spanning anchors too, purely by vertical position — Rule 8.1/8.2's text doesn't classify them by column membership at all, so they always interrupt the reading order rather than risk being folded into the wrong column. Implemented and confirmed against a real 2-column dictionary in the user's collection: reordered output read as one coherent alphabetical sequence end to end.

> **RTL script handling:** Rule 8.1's "concatenate columns left-to-right" applies to Latin and LTR scripts. When a page's dominant script is RTL (`mdook/core/rules/scripts.py`'s `page_is_rtl`), `reorder_columns` reverses the reading order to right-to-left while preserving internal column top-to-bottom order. Vertical writing mode pages skip column reordering.

### Rule 8.3 — Literature Profile Shortcut

- **Condition:** Profile is `literature`
- **Action:** Assume single-column layout. Skip column detection entirely. Only trigger Rule 8.1 if automated detection finds > 10% of pages with multi-column signals.

---

## 9. Special Content Handling

### Rule 9.1 — Epigraph Detection

- **Condition:** A short italic or indented text block at the start of a chapter, before the first body paragraph. Often includes an attribution line (em dash + author name).
- **Action:** Render as a blockquote:
  
  ```
  > *The world breaks everyone, and afterward, many are strong at the broken places.*
  > — Ernest Hemingway
  ```

### Rule 9.2 — Poetry / Verse Detection

- **Condition:** Multiple short lines (< 68 chars, average < 52 chars) with irregular right margins (not reaching body right margin), consistent left margin alignment, and high ratio of capitalized initial characters. May be indented relative to body text.
- **Action:** Preserve line breaks exactly. Do not merge into paragraphs. Render with two trailing spaces per line (`  \n`) for hard line breaks in markdown. If indented relative to the body text left margin, render enclosed in Obsidian blockquotes (`> `). Blank lines between stanzas are preserved as blank lines (`\n\n`).
- **Implemented in Phase 5** (`mdook/core/rules/verse.py`, models in `mdook/core/models.py`, integrated into `mdook/core/stages/semantic.py` and `mdook/core/stages/rendering.py`).

> **Update: implemented with five domain-specific guards against false positives.**
> Detecting verse before paragraph merging without corrupting standard prose required several critical safeguards:
> 1. **Terminal Punctuation Discriminator**: In synthetic test fixtures and certain short-sentence prose passages, individual lines are short (< 40 chars) but represent full discrete sentences ending in periods, exclamation points, or question marks. In authentic verse, enjambment causes sentences to span multiple lines, with lines terminating in commas, semicolons, dashes, or unpunctuated words. If > 50% of lines in a ≥ 3-line block end in terminal punctuation (`.`, `?`, `!`), the block is classified as prose, preventing synthetic tests and staccato dialogue from being misidentified as poetry.
> 2. **Dialogue & Speech Verb Guard**: Lines with opening/closing dialogue quotes followed by speech attribution verbs (`said`, `whispered`, `asked`, etc.) are explicitly rejected from verse clustering.
> 3. **Glossary / Definition Guard**: Two or more lines following the dictionary/glossary pattern `^[^:]{1,30}:\s+\S` are rejected to prevent term glossaries from converting into verse stanzas.
> 4. **Multi-Stanza Continuity & Attribution**: Vertical gaps between 1.7× and 3.5× line height are treated as stanza breaks. Successive stanzas are aggregated into a single `VerseBlock` with blank line separators. Trailing attribution lines (e.g. `— Robert Frost`, `-- Author`, `(by Author)`) are recognized, extracted to `VerseBlock.attribution`, and rendered cleanly as `— Attribution` at the end of the poem.
> 5. **Inline Footnote Splicing**: Superscript footnote markers positioned at the ends of poetic lines are spliced directly into the line text via sentinels (`FOOTNOTE_MARKER_SENTINEL`), ensuring footnote links like `[^1]` are preserved accurately in rendered verse.

### Rule 9.3 — Block Quote Detection

- **Condition:** Text with increased left margin (indented > 1.5× normal) spanning multiple lines, typically in body font but sometimes slightly smaller
- **Action:** Render as markdown blockquote (`>`).

> **Update: implemented, generalized beyond epigraphs, and needed two extra guards real testing forced.** A first version using just the 1.5×-indent threshold above produced **496 false positives on one real book** — investigation found two distinct causes neither anticipated here: (1) short marker/digit debris (page numbers, stray footnote-adjacent fragments) getting swept up as "quotes," and (2) more interestingly, right-hand sidebar/pull-quote content landing at an x-position hundreds of points into the page — a symptom of multi-column layout (Rule 8) not being handled on that specific page, not a real block quote at all. Fixed with two additional conditions this rule doesn't mention: a minimum word count (a 1-3 word "paragraph" this indented is debris, not a quotation) and a *maximum* indent ratio (past roughly 6× body font size, it's a column-layout artifact, not a deliberately-indented quote). `mdook/core/stages/semantic.py`'s `_looks_like_block_quote`. After the fix, the same book had 43 genuine quotes (real first-person excerpts), which checked out on inspection.

### Rule 9.4 — Printed TOC Discard

- **Condition:** A front-matter page contains a structured list of chapter titles paired with page numbers, matching the pattern "Title...###" or "Title    ###"
- **Action:** Discard entirely. The vault generates its own MOC/Index file. Keeping the printed TOC duplicates structure and confuses AI context.

> **Update: this rule's own "confuses AI context" worry turned out to apply to *itself*, not just the printed TOC.** Beyond the dot-leader pattern above, the implementation added a second signal for ebook-derived TOCs with no page numbers at all: cross-referencing a page's text against the book's own already-detected chapter titles (≥3 matches ⇒ it's a TOC page). That second signal became a real bug on a book whose heading detection had degenerated to garbage (three chapters all titled bare "H", a font-encoding corruption issue, not a TOC problem) — a single-character "title" trivially substring-matches almost *any* page's text, so nearly every page in that book got wrongly discarded as "the printed TOC," silently dropping all of its content, not just tables. Fixed by requiring a title to have at least 4 normalized characters before it can be used as a cross-reference signal at all (`mdook/core/stages/semantic.py`'s `MIN_TOC_TITLE_MATCH_LENGTH`). The underlying garbled-heading-detection problem itself remains unsolved — this fix only stops it from cascading into content loss.

### Rule 9.5 — Decorative Element Filtering

- **Condition:** Small centered text or symbol between sections (§, *, ❧, ◆, or ornamental dingbats). Often used as section breaks in literary books.
- **Action:** Replace with a horizontal rule (`---`) in markdown. Do not preserve the specific ornament character.

### Rule 9.6 — Structured Glossary Processing

- **Condition:** A back-matter section titled "Glossary", "Definitions", "Vocabulary", or similar keyword containing term-definition pairs.
- **Signals:**
  1. **Font-Styling Signal**: Bold terms (`is_bold=True`) at line start followed by normal-weight definitions.
  2. **Syntactic Delimiter Signal**: Lines formatted as `Term: Definition`, `Term — Definition`, or `Term – Definition`.
  3. **Geometric Hanging Indent Signal**: Flush terms at baseline column margin ($x_0$) followed by indented definition lines ($x_0 + \Delta$).
  4. **Alphabetical Letter Dividers**: Standalone single-letter headings (`A`, `B`, `— C —`, `[D]`) preserved as level-2 markdown sub-headings (`## A`, `## B`).
- **Action:** Pull entries into `GlossaryBlock` and `GlossaryItem` models. Render as clean `**Term** — Definition` paragraphs in dedicated `Glossary.md` notes. Multi-line definitions rejoin hyphenated line breaks. Inline footnote and citation sentinels are preserved within definitions, linking directly to `[[Notes.md]]` and `[[Bibliography.md]]`.
- **Safeguards:** Unstructured or narrative text under a Glossary heading cleanly degrades to standard markdown paragraphs with zero loss of content.

`mdook/core/rules/glossary.py`.

---

## 10. Profile-Specific Rule Activation

### Literature Profile

Active: Zones, Headings (font-based), Headers/Footers, Footnotes (page-bottom priority), Paragraph Merging, Epigraphs, ~~Poetry~~, Block Quotes, Decorative Filtering, Drop Cap Immunity
Inactive: Numbered Section Detection, Multi-Column (unless auto-detected), Complex Table handling
Tuning: Stricter positional confirmation for headings (literary books have simpler structure)

### Technical Profile

Active: All rules
Extra: Numbered Section Detection, Multi-Column, Table extraction (both simple + complex), ~~Vector Diagram Rasterization~~, ~~Figure/Table caption association~~
Tuning: More lenient heading detection (technical books vary more in layout), table detection sensitivity increased

> **Update: "Poetry" and the two struck-through Rule 7 items are listed as active/available above but aren't implemented at all yet** (see their own rule sections' updates). More significantly: **most rules added after the first implementation sprint aren't profile-gated the way this table implies everything is.** Lists, block quotes, code-block detection, multi-column reordering, and OCR text-quality scoring all use fixed thresholds in their own rule modules rather than reading from `literature.toml`/`technical.toml`. Only numbered-section detection (technical-only) and the multi-column literature shortcut (Rule 8.3) actually check the profile today. This table describes the original intent more than current reality — see `Mdook-docs/STACK.md`'s TOML config update for the same gap from the tooling side.

---

## 11. List Detection *(new — not in the original plan)*

**Goal:** Preserve bulleted and numbered lists as real markdown lists instead of letting Rule 5.1 flatten them into one merged paragraph — every item in a list typically shares font, size, and left margin with its siblings, which is exactly Rule 5.1's condition for merging them together.

### Rule 11.1 — Bullet/Numbered Marker Detection

- **Condition:** A text block's stripped text starts with a bullet glyph (•, ◦, ▪, ‣, ∙, ○, ■, □, ◆, ♦, *, -) followed by whitespace, or a digit followed by `.` or `)` and whitespace (`"1. "`, `"2) "`).
- **Action:** Pull consecutive marker-prefixed blocks out of the ordinary paragraph-merge flow into a `ListData` before `merge_text_blocks` ever sees them.
- **Deliberately excluded:** lettered (`"a. "`) and roman-numeral (`"i. "`) markers. A single letter followed by a period is indistinguishable from a personal initial at the start of a sentence ("A. Einstein once said...") without much deeper context — this only recognizes unambiguous signals.
- **Simplification:** an item must be a single extracted line; one that wraps across two source lines only captures its first line.

### Rule 11.2 — Nesting Level by Indent

- **Condition:** Multiple consecutive list items with different left-edge x-positions.
- **Action:** Cluster distinct x0 values (within ~3pt tolerance) and assign each item a nesting level by which cluster its indent falls into.

### Rule 11.3 — Numbered Item Marker Preservation

- **Condition:** An ordered list item.
- **Action:** Render using the item's *own printed number* verbatim, not a synthesized running counter.
- **Failure mode found in testing:** narrative prose routinely interrupts a numbered sequence ("1. Relax completely. *[a paragraph of explanation]* 2. Observe the visual images."), splitting it into several separate single-item lists. A synthesized counter would print "1." for every one of them; using the book's own printed number avoids this entirely, regardless of how fragmented the detection ends up being.

`mdook/core/rules/lists.py`.

---

## 12. Code Block Detection *(new — not in the original plan; `Mdook-docs/ROADMAP.md`'s Phase 2 names the idea with no rule numbers assigned)*

**Goal:** Preserve source code's line breaks and indentation, which Rule 5.1's same-style continuation would otherwise destroy by joining code lines into a flowing sentence.

### Rule 12.1 — Monospace Font Detection

- **Condition:** A text block's font name contains a recognizable monospace-font keyword (Courier, Consolas, Menlo, Monaco, "mono", SourceCodePro, FiraCode, Inconsolata, DejaVuSansMono, and similar).
- **Action:** Pull consecutive monospace blocks out of the paragraph-merge flow into a `CodeBlock`, preserving each source line exactly. Render as a fenced ` ``` ` block with no language tag (nothing in the PDF reliably identifies one).
- **Simplification:** this is font-*name* keyword matching, not per-glyph advance-width measurement (Stage 2's `TextBlock` doesn't carry per-character positions) — the same class of heuristic most PDF-to-markdown tools use. A monospace font renamed to something unrecognizable by an HTML-to-PDF export (the same failure mode Rule 5.1's font-name-independent style matching already works around) simply won't be detected as code — a false negative, never a false positive, so ordinary prose is never miscategorized as code by this gap.

`mdook/core/rules/code.py`.

---

## 13. Structural Divisions & Callout Boxes

### Rule 13.1 — Part/Book/Volume Division

- **Condition:** Font-clustering path only (Rule 2.2). A heading tier above the chosen chapter tier has at least 2 occurrences whose text reads as a Part/Book/Volume label (`^(part|book|volume)\b`, case-insensitive).
- **Action:** Record the most recent such heading (by page number) as each chapter's `part_title`. `Chapter` stays a flat list (`DocumentTree.chapters`) rather than a nested container — Stage 4 groups the Index/MOC file's chapter links under a `## {part_title}` heading per part; individual chapter files are unaffected.
- **Known gap:** bookmark-based hierarchy (Rule 2.1) always numbers its top level "1" for whatever the PDF's own bookmarks call it, so there is no "level above 1" to check — a bookmark-based book with real Parts doesn't get this treatment yet.
- **Simplification:** the label-keyword gate is English-only, consistent with `CHAPTER_LABEL_ONLY_RE` elsewhere in this file. A book naming its parts something else entirely (or in another language) degrades to no Part grouping — chapters still segment and render correctly, just without the extra `## Part` heading.

`mdook/core/stages/semantic.py`'s `_pick_part_tier`/`_looks_like_part_tier`/`_part_title_for_page`.

### Rule 13.2 — Callout / Sidebar Box Detection

- **Condition:** A merged paragraph's own text opens with a recognized label followed immediately by `:` or `.` — Note, Warning, Tip, Caution, Important, Key Point, Remember (case-insensitive).
- **Action:** Extract as a `CalloutBlock` instead of an ordinary `Paragraph`. Render as an Obsidian callout (`> [!warning] Warning`, etc.), mapping the label to one of Obsidian's built-in callout types with an `info` fallback for anything unmapped.
- **False-positive guard:** requiring punctuation directly after the label word is what keeps ordinary prose ("Note that the results varied...") from being misread as a callout.
- **Not implemented:** vector-drawn box borders around a callout (`page.get_drawings()`) — the label-text signal alone covers the common case; box-border detection would add real noise on scanned pages and was deferred rather than gating the whole feature on it.

`mdook/core/rules/callouts.py`.

---

## 14. Citation-to-Bibliography Linking

### Rule 14.1 — Numeric Citation Detection & Linking

- **Condition:** A back-matter section labeled Bibliography/References/Works Cited (reusing the same label-matching approach as Rule 4.3's Notes/Endnotes detection) contains numbered entries (`1. Smith...` or `[1] Smith...`). An in-text bracketed number or number list/range (`[1]`, `[1, 3]`, `[1-4]`) appears in body text.
- **Action:** Link the in-text citation to its matching bibliography entry via an Obsidian wiki-link block reference (`[[99 - Back Matter#^ref-3|3]]`), reusing the same sentinel-then-Stage-4-resolves-the-link mechanism already built for endnotes (Rule 4.3/4.4) — a new sentinel character rather than a new architecture. The bibliography's own numbered-list entries get `^ref-N` block-ID anchors the same way the Notes section gets `^note-N` ones.
- **Key difference from footnote/endnote markers:** a numeric citation is ordinary inline text sitting inside a normal sentence, not a discrete superscript `TextBlock` — so detection works directly on already-merged paragraph text via regex (`mdook/core/rules/citations.py`'s `splice_citation_links`), with no `TextBlock`-level correlation step needed at all.
- **Degrade-gracefully behavior:** if any number inside a bracket doesn't match a known bibliography entry (a malformed/incomplete back matter, or a bracketed number that was never a citation to begin with), the *entire* bracket is left as plain text rather than producing a partially-broken or wrong link.
- **Not implemented (stretch goal, not built):** author-date style citations (`(Smith, 2020)`) — these need fuzzy author-surname/year matching against bibliography entry text rather than an exact number match, a meaningfully less reliable signal than the numeric case.

`mdook/core/rules/citations.py`.

---

## 15. Mathematics & Formal Notation

**Goal, and its explicit limit:** handle the *text-layer* math case — Unicode math symbols already present in extracted text (Word-equation-editor exports, OCR'd math via Tesseract's Latin+symbol recognition, older typeset technical books). A PDF built from real LaTeX frequently draws equations as vector paths or Type3 glyph shapes with no extractable Unicode at all; recovering semantic math from a pure vector drawing is out of scope (a specialized tool in its own right, e.g. Mathpix/pix2tex, not a generic heuristic rule) — the region still gets rasterized as an ordinary image via Rule 7.2.

### Rule 15.1 — Symbol-Density Scoring

- **Condition:** Count characters in the Letterlike Symbols, Mathematical Operators, Superscripts/Subscripts, and Mathematical Alphanumeric Symbols Unicode blocks as *strong* math signals; Greek letters as a *weak* signal that only counts once a strong signal is already present in the same text.
- **Rationale:** Greek letters (α, β, θ, Σ, Π) are common in math notation but are also a real natural-language script — a book genuinely written in Greek would score 100% "math" on every page if Greek counted unconditionally.
- **Real-book-found gap:** ¹²³ (U+00B9/B2/B3) predate the "Superscripts and Subscripts" Unicode block and live in Latin-1 Supplement instead, for legacy compatibility — an equation as ordinary as "E = mc²" scored zero until these three codepoints were added as an explicit exception.

`mdook/core/rules/math.py`'s `score_symbol_density`.

### Rule 15.2 — Display Equation Detection

- **Condition:** A whole merged paragraph (already isolated by Rule 5.4's paragraph-boundary detection) contains at least one math symbol. A short paragraph (≤8 words) needs nothing more; a longer one also needs real symbol density (≥0.2) — being short and isolated no longer rules out ordinary prose that merely mentions a symbol in passing.
- **Real-book-found gap:** a flat density threshold alone missed "E = mc²" — most of an equation this short is *ordinary-looking* letters and digits (E, m, c) with only one truly exclusive math character (²), so density stays low even though the whole line is unmistakably an equation. Fixed with the two-tier word-count check above.
- **Action:** Render inside Obsidian's native MathJax delimiters (`$$...$$`), not a custom fenced block. A trailing `(3.14)`-style equation-number tag is split off and preserved as plain trailing text, not semantically parsed.

### Rule 15.3 — Inline Equation Detection

- **Condition:** A whitespace-delimited token within an otherwise-ordinary paragraph clears a token-level density threshold (≥0.5), *or* is a short (≤2-character) run made entirely of Greek letters (optionally with a trailing digit, e.g. "α1").
- **Rationale for the short-Greek exception:** unlike Rule 15.1's whole-paragraph scoring, a bare "α" sitting inline between English words is overwhelmingly more likely to be a math variable than an embedded Greek word — the ambiguity that motivates gating Greek behind a strong signal is a whole-paragraph/whole-book risk, not a two-character-token one.
- **Action:** Wrap the matched token in Obsidian's inline MathJax delimiters (`$...$`). Token-level rather than free-form substring matching, since finding an inline equation's correct boundaries within ordinary prose is otherwise ambiguous without real per-glyph layout structure.

### Rule 15.4 — Theorem-Like Environment Grouping

- **Condition:** A paragraph opens with `Theorem|Lemma|Corollary|Proposition|Definition|Axiom|Example|Remark|Exercise|Proof|Claim`, optionally numbered, followed by `.` or `:`.
- **Action:** Group it (and, for a `Proof`, however many subsequent paragraphs follow until a QED marker — □, ∎, or "Q.E.D." — or the next theorem-labeled paragraph) into a `CalloutBlock`, reusing Rule 13.2's callout rendering rather than inventing a second box-rendering path. Renders as `> [!theorem] Theorem 3.2`, `> [!proof] Proof`, etc. — Obsidian renders any callout type name it doesn't specifically recognize with a generic bordered style, so self-mapping each theorem-environment word is enough (`mdook/core/rules/callouts.py`'s `_OBSIDIAN_CALLOUT_TYPES`).
- **Note:** a real heading boundary can't appear mid-`Proof`, since headings already split into their own run before paragraph merging ever sees them (`mdook.core.stages.semantic._collect_content`) — so "until the next heading" from the original plan reduces to "until the next theorem label" in practice.

`mdook/core/rules/math.py`'s `group_theorem_environments`.

---

## 16. Non-Latin Script & Vertical-Text Robustness

**Goal:** make the existing structural rules (columns, headings) behave correctly — or at minimum not corrupt content — for RTL, case-less, and vertically-typeset scripts, without inventing genre/language-specific shortcuts. This section documents robustness fixes to *existing* rules (8 and 2.3, both updated above) plus one new detect-and-don't-corrupt behavior.

### Rule 16.1 — RTL Column Reading Order

See Rule 8.1's update above. `mdook/core/rules/scripts.py`'s `page_is_rtl` checks a page's own text against the Hebrew/Arabic Unicode ranges; `mdook.core.rules.columns.reorder_columns` reads the rightmost column first when it applies.

### Rule 16.2 — Case-Less Script Heading Confirmation

See Rule 2.3's OCR & Script Considerations above. `mdook/core/rules/scripts.py`'s `is_caseless_text` exempts CJK/Arabic/Hebrew/Devanagari/Thai text from the OCR-page uppercase-mandatory gate.

### Rule 16.3 — Vertical Text Detection (Detect-and-Don't-Corrupt)

- **Condition:** Most of a page's lines report vertical writing mode (`wmode == 1`, straight from the PDF's own `WMode` via PyMuPDF's per-line dict data) — traditional vertical CJK typesetting.
- **Action:** Record `PageData.is_vertical_text`. `mdook.core.rules.columns.reorder_columns_if_warranted` skips such a page entirely rather than attempting horizontal column reordering on it, which would scramble rather than fix vertical content.
- **Explicit scope limit:** full vertical-layout reading order (right-to-left columns of top-to-bottom text) is a large undertaking and is *not* implemented — this rule only prevents an existing horizontal-reading-order assumption from actively corrupting a vertical page. Heading-position heuristics (top-30%-of-page, etc.) are similarly not adapted for vertical layout; this is a known, deliberately deferred gap, not an oversight.

`mdook/core/stages/extraction.py`'s `_page_is_vertical_text`.

---

## 17. Pathological PDF Robustness

**Goal:** Handle corrupt, encrypted, oversized, or degenerate real-world PDFs regardless of subject or language.

### Rule 17.1 — Encrypted PDF Detection

- **Condition:** `pymupdf.open()`'s `doc.needs_pass` is true.
- **Action:** Raise `mdook.core.errors.EncryptedPDFError` with a clear, specific message, rather than letting a downstream stage fail opaquely on an unauthenticated document. The GUI (`mdook.gui.worker.ConversionWorker`) already catches any `Exception` broadly and surfaces `str(exc)`, so no special handling is needed at the call site.

### Rule 17.2 — Corrupt PDF Structure

- **Condition:** `pymupdf.open()` itself raises, or anything else in Stage 1 raises while reading a document that did open (MuPDF repairs many corrupt PDFs silently, but not all).
- **Action:** Re-raise as `mdook.core.errors.CorruptPDFError` with the filename and original error, rather than an opaque traceback. This is the same degrade-gracefully *philosophy* already used for `pdfplumber.open()` and per-image extraction failures elsewhere in the pipeline, applied to the one place a whole book truly can't be converted rather than just one piece of it.

`mdook/core/errors.py`, `mdook/core/stages/intake.py`.

### Rule 17.3 — CID-Keyed Fonts / Mojibake

`mdook.core.rules.text_quality`'s `SUSPICIOUS_CHAR_RE` catches the replacement-character/private-use-area corruption signature and routes it through the per-page OCR fallback. Glyphs mapping to other valid characters are handled at the structural level via chapter-tier selection and TOC-page hardening.

### Rule 17.4 — Very Large PDFs

- **Action:** Log an informational note at intake once a book reaches 1000 pages, so an unusually slow conversion (especially one needing heavy OCR) has an explanation up front. Algorithms for header/footer clustering and column reordering are linear in total blocks and scale reliably.

`mdook/core/stages/intake.py`'s `LARGE_BOOK_PAGE_COUNT`.

### Rule 17.5 — Duplicate Text Layers

- **Condition:** Two text blocks on the same page have matching text (case/whitespace-insensitive) and bounding boxes overlapping by at least 70% of the smaller block's area.
- **Action:** Keep the first-seen block, discard the later one as a duplicate. Targets a real, specific scenario: a scan carrying two overlapping text layers at once — a faint original layer plus a separately-applied OCR layer baked in by whatever archival tool processed the scan before it ever reached Mdook — which would otherwise double every paragraph.

`mdook/core/stages/extraction.py`'s `_deduplicate_overlapping_text`.

### Rule 17.6 — Blank Pages

- **Condition:** A page has 5 or fewer native characters *and* no embedded images at all.
- **Action:** Record `PageData.is_blank` and skip the OCR attempt entirely, rather than running OCR against nothing and logging what looks like an OCR failure. A page an author left intentionally blank between chapters has nothing for OCR to find — that's the expected, correct outcome, not an error. A page with an image but no text (a plate/illustration page) is *not* blank and is unaffected — OCR correctly finding no text there is accurate, not a false warning.

`mdook/core/models.py`'s `PageData.is_blank`, `mdook/core/stages/extraction.py`'s `_page_is_blank`.

---

## 18. AI Structure Review *(Phase 5)*

**Goal:** Review and refine the candidate heading hierarchy before chapter segmentation using an OpenAI-compatible LLM reviewer, catching OCR noise, demoted chapters, leaked running headers, or Part/Chapter confusion without generative hallucinations.

### Rule 18.1 — Token-Efficient Skeleton Serialization

- **Condition:** AI Structure Review is enabled (`LLMConfig.enabled == True`).
- **Action:** Serialize heading candidates into a compact outline skeleton (~200–500 tokens). Each entry lists candidate ID, level tier, page number, title text, and an excerpt of the immediately following body text. Full chapter contents are never sent.

### Rule 18.2 — Strictly Constrained Reviewer Role

- **Condition:** LLM receives skeleton with explicit instruction to act purely as a reviewer and return a JSON diff.
- **Action:** Parse structured corrections:
  - `demote_to_body`: Candidate heading is rejected as a heading; its text block remains in `PageData` and is merged into ordinary body prose (eliminates mid-sentence OCR artifacts and leaked running headers).
  - `set_level`: Adjust candidate level (e.g. promoting a chapter from level 2 to level 1).
  - `set_part`: Mark as a Part/Book/Volume division above the chapter tier.

### Rule 18.3 — Deterministic Guardrails & Graceful Fallback

- **Condition:** LLM response is returned or network/API failure occurs.
- **Action:**
  - Corrections targeting out-of-bounds IDs or invalid levels are discarded.
  - Demotions targeting 100% of the book's headings are rejected as rogue responses.
  - If the endpoint is unreachable, times out, returns HTTP errors, or returns invalid JSON, the pipeline logs a warning and proceeds seamlessly with the deterministic heuristic output.

### Rule 18.4 — Non-blocking Connection Verification, Model Discovery & UI Affordance

- **Condition:** User tests connection, discovers models, or configures AI settings in the GUI.
- **Action:**
  - Connection test issues a lightweight 5-token ping to the `/chat/completions` endpoint on a dedicated background `QThread` (`ConnectionTestWorker`) with an 8-second timeout, measuring roundtrip latency in milliseconds without freezing the UI. If a `model_not_found` error occurs (e.g. using an OpenAI default model on Groq or Ollama), the UI provides an explicit hint directing the user to fetch available models.
  - Model discovery queries the provider's `/models` endpoint via `normalize_models_endpoint()` on a background `QThread` (`ModelFetchWorker`), populating an editable, searchable `QComboBox` (`ai_model_combo`). The combo box supports live substring filtering (`Qt.MatchContains`), pre-populated common models across major providers (OpenAI, Groq, Ollama, DeepSeek), auto-selection of versatile/chat models, and custom model names.
  - The AI configuration section provides an explicit disclosure toggle button (`▾` / `▸`) indicating collapsible state, with transparent child containers (`TransparentRow`, `AISettingsWidget`) that blend seamlessly into the parent card.

`mdook/core/llm/` (`client.py`, `models.py`, `prompts.py`, `review.py`), `mdook/gui/` (`window.py`, `worker.py`, `styles.py`), `mdook/core/stages/semantic.py`.


