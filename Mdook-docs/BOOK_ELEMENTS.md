# Book Elements — Exhaustive Catalog

Every structural element, content type, and formatting pattern that real-world books contain, organized by location and type. This is the complete inventory that Mdook must eventually handle. Items marked with their current status:

- **[done]** — implemented and tested
- **[partial]** — basic handling exists, needs improvement
- **[stub]** — code module exists but no logic yet
- **[planned]** — in ROADMAP.md for a specific phase
- **[new]** — not previously documented anywhere

---

## 1. Front Matter

Everything before the body text begins. Most books have some subset of these; academic and technical books tend to have the most.

### 1.1 — Title Pages & Preliminaries

| Element | Description | Genres | Status |
|---------|-------------|--------|--------|
| **Half title page** | Book title only, no author/publisher. Usually the very first printed page. | All | [new] |
| **Series title page** | Lists other titles in the same series. Sometimes on verso of half title. | Fiction series, academic series | [new] |
| **Frontispiece** | Full-page illustration facing the title page. Common in older books. | Literature, art, occult, historical | [new] |
| **Title page** | Full title, subtitle, author(s), publisher, sometimes edition number. | All | [partial] — title extracted from metadata, not from page content |
| **Copyright page** | Publisher, year, ISBN, edition, printing history, legal notices, CIP data. | All | [new] |
| **Colophon** (front) | Typeface, paper stock, printer info. Some books put this up front. | Art, literary, fine editions | [new] |
| **Dedication** | Short, usually one line to a few lines. Often its own page. | All | [new] |
| **Epigraph** (book-level) | Quote at the book level (distinct from chapter epigraphs). | Literature, philosophy, occult | [partial] — chapter epigraphs detected, book-level not |
| **Table of Contents** | Chapter/section listing with page numbers. | All | [done] — detected and discarded (Rule 9.4) |
| **List of Figures** | Figure captions with page numbers. | Technical, science, textbooks | [new] |
| **List of Tables** | Table captions with page numbers. | Technical, science, textbooks | [new] |
| **List of Maps** | Map titles with page numbers. | History, geography, travel | [new] |
| **List of Plates** | Plate descriptions with page numbers (for grouped illustrations). | Art, archaeology, natural history | [new] |
| **List of Abbreviations** | Acronym/abbreviation → expansion table. | Academic, medical, legal, STEM | [new] |
| **List of Symbols** | Mathematical/scientific symbol → meaning table. | Math, physics, engineering | [new] |
| **List of Contributors** | Author bios for each chapter in an edited volume. | Academic anthologies, essay collections | [new] |
| **Foreword** | Written by someone other than the author. Signed and dated. | All (especially reprints/new editions) | [new] |
| **Preface** | Author's own introduction to the book, its purpose and scope. | All | [new] |
| **Acknowledgments** (front) | Thanks to people/institutions. Can also appear in back matter. | All | [new] |
| **Introduction** (front) | When the Introduction is not Chapter 1 but a standalone front section. | Academic, non-fiction, textbooks | [new] |
| **Prologue** | Narrative opening before Chapter 1. Distinct from Introduction. | Fiction, memoir | [new] |
| **Note to the Reader** | Usage instructions, content warnings, translation notes, reading guide. | Various | [new] |
| **How to Use This Book** | Explicit instructions for navigating the book's structure. | Textbooks, reference, self-help, workbooks | [new] |
| **Chronology / Timeline** | Key dates relevant to the book's subject. | History, biography | [new] |
| **Dramatis Personae** | Character list (plays, complex novels, mythology). | Drama, epic literature, occult | [new] |
| **Map pages** | Full-page maps (fantasy worlds, historical regions, battle plans). | Fantasy, history, military, travel | [new] |
| **Permissions / Credits** (front) | Reprint permissions for quoted material, image credits. | Anthologies, art books | [new] |
| **Editor's Note** | Context from the editor, especially for posthumous/translated works. | Translated, historical, academic | [new] |

### 1.2 — Front Matter Detection Challenges

- Front matter pages often lack page numbers entirely, or use roman numerals
- Dedication pages may have no identifying keyword — just a short centered line
- The boundary between front matter and body is ambiguous: some books number the Introduction as front matter, others as Chapter 1
- Forewords and prefaces can be multi-page prose that looks like body text
- List of Figures/Tables pages look like TOC pages but should be preserved, not discarded

---

## 2. Body Text — Structural Hierarchy

### 2.1 — Divisions Above Chapter Level

| Element | Description | Genres | Status |
|---------|-------------|--------|--------|
| **Parts** | Named or numbered groupings of chapters ("Part I: The Foundation"). | Literature, non-fiction, textbooks | [new] |
| **Books** (divisions) | Higher than Parts in some works ("Book One", "Book Two"). | Epic literature, long non-fiction | [new] |
| **Volumes** | When a single work spans multiple bound volumes, published as one PDF. | Encyclopedias, collected works, legal codes | [new] |
| **Acts / Scenes** | Drama/play structure. | Plays, screenplays | [new] |
| **Movements** | Musical score structure. | Music theory, composition texts | [new] |

### 2.2 — Chapters & Sections

| Element | Description | Genres | Status |
|---------|-------------|--------|--------|
| **Chapters** (numbered) | "Chapter 1", "Chapter I", "CHAPTER ONE", etc. | All | [done] |
| **Chapters** (named only) | Title only, no number ("The Raven", "On Liberty"). | Literature, philosophy | [done] |
| **Chapters** (numbered + named) | "Chapter 3: The Storm Breaks" — number and title are separate elements. | All | [partial] — the separate-element case sometimes loses the title |
| **Unnumbered sections** | Major divisions without numbers (common in essays, philosophy). | Non-fiction, philosophy | [partial] |
| **Numbered sections** | "1.1", "1.1.1", "1.1.1.1" — up to 4 levels deep. | Technical, academic, legal | [planned] — Rule 2.4, Phase 2 |
| **Lettered sections** | "A.", "B.", "C." or "(a)", "(b)", "(c)" subdivisions. | Legal, regulatory, standards | [new] |
| **Sub-sections** (H2–H6) | Multiple heading levels within a chapter. | Technical, academic, textbooks | [planned] — Phase 2 |
| **Interludes / Intermissions** | Named breaks between major sections (not quite chapters). | Literature, creative non-fiction | [new] |
| **Excurses / Excursus** | Extended digressions set apart from the main text. | Academic, theology | [new] |

### 2.3 — Chapter Numbering Variations

Books use wildly inconsistent chapter numbering schemes:

- Arabic: 1, 2, 3
- Roman: I, II, III, IV
- Spelled out: One, Two, Three / First, Second, Third
- Combined: "Chapter XII — The Descent"
- With subtitle: "3\nThe Politics of Fear" (number on one line, title on next)
- Decorative number: oversized numeral as a separate typographic element, title in smaller text below
- No number at all, just a title
- Prefixed: "Lesson 1", "Module 3", "Session 7", "Unit 5", "Step 4"
- Mixed: some chapters numbered, some not (common in books with a prologue/epilogue)

---

## 3. Body Text — Inline & Block Content

### 3.1 — Paragraph-Level Content

| Element | Description | Genres | Status |
|---------|-------------|--------|--------|
| **Regular paragraphs** | Standard prose body text. | All | [done] |
| **Indented paragraphs** | First-line indent (standard in most books). | All | [done] — used as paragraph boundary signal |
| **Block-indented text** | Entire paragraph indented from left margin (not just first line). | Academic, legal (quotes, extracts) | [partial] — detected as blockquote |
| **Flush-left paragraphs** | No indent, separated by vertical space instead. | Technical, modern non-fiction | [done] |
| **Hanging indent** | First line flush, subsequent lines indented. | Bibliographies, indexes, glossaries | [new] |
| **Centered text** | Single lines or short passages centered on page. | Poetry, dedications, title pages | [new] |
| **Right-aligned text** | Attributions, dates, signatures. | Letters, legal, formal documents | [new] |

### 3.2 — Inline Formatting

| Element | Description | Genres | Status |
|---------|-------------|--------|--------|
| **Bold** | Emphasis, key terms, headings within text. | All | [done] — extracted as flag |
| **Italic** | Emphasis, foreign words, titles, internal monologue, species names. | All | [done] — extracted as flag |
| **Bold italic** | Strong emphasis. | All | [done] — both flags set |
| **Underline** | Rare in print; sometimes used for hyperlinks in digital-native PDFs. | Technical, digital | [new] |
| **Strikethrough** | Very rare in published books; appears in drafts, legal redlines. | Legal, editorial | [new] |
| **Small caps** | Proper names (Tolkien), abbreviations (NASA), first words of chapters. | Literature, academic | [done] — span merging handles this |
| **ALL CAPS** | Headings, emphasis, abbreviations. | Various | [partial] — not explicitly detected |
| **Superscript** | Footnote markers, ordinals (1st, 2nd), exponents, trademark symbols. | All | [done] |
| **Subscript** | Chemical formulas (H₂O, CO₂), mathematical notation. | Science, chemistry, math | [new] |
| **Monospace / Code font** | Inline code, commands, file paths, URLs. | Technical | [new] |
| **Colored text** | Rare in print; common in textbooks and digital PDFs for emphasis. | Textbooks, educational, digital | [new] |
| **Highlighted / shaded text** | Background color behind text for emphasis. | Textbooks, digital | [new] |
| **Hyperlinks** | Clickable URLs in digital-native PDFs. | Technical, digital, modern non-fiction | [new] |
| **Cross-references** | "see Chapter 3", "see Figure 2.1", "as discussed on p. 42". | Technical, academic, textbooks | [new] |
| **Inline citations** | "(Smith, 2020)", "[1]", "(Smith 42)" — style varies by field. | Academic, scientific | [new] |
| **Ruby text / Furigana** | Pronunciation guides above CJK characters. | Japanese, Chinese texts | [new] |
| **Diacritical marks** | Accents, umlauts, cedillas, macrons in non-English text. | All multilingual | [partial] — preserved in text extraction |
| **Ligatures** | fi, fl, ffi, ffl — encoded as single glyphs in some PDFs. | All typeset books | [partial] — PyMuPDF usually resolves these |

### 3.3 — Block-Level Content

| Element | Description | Genres | Status |
|---------|-------------|--------|--------|
| **Block quotes** | Extended quotations, indented from both margins. | All | [partial] — epigraphs only |
| **Poetry / Verse** | Line-broken text with intentional line endings, stanza breaks. | Literature, anthologies, religious | [planned] — Rule 9.2, Phase 4 |
| **Song lyrics** | Similar to poetry but sometimes with chorus/verse markings. | Music, memoir, cultural studies | [new] |
| **Dialogue** | Conversations, especially when formatted with em-dashes (French style) vs. quotation marks (English style). | Fiction, oral history, interview books | [new] |
| **Letters / Epistolary** | Reproduced correspondence, often with date/address headers. | History, biography, epistolary fiction | [new] |
| **Diary entries** | Dated entries, often with different formatting from body text. | Memoir, biography, fiction | [new] |
| **Interviews / Transcripts** | Q&A format with speaker labels. | Journalism, oral history, non-fiction | [new] |
| **Lists** (bulleted) | Unordered lists with bullets (•, -, ○, ■, ▸). | Technical, self-help, educational | [new] |
| **Lists** (numbered) | Ordered lists (1., 2., 3. or a., b., c. or i., ii., iii.). | All non-fiction | [new] |
| **Lists** (nested) | Multi-level lists with indentation. | Technical, legal, outlines | [new] |
| **Lists** (definition) | Term followed by its definition, often with hanging indent. | Glossaries, dictionaries, reference | [new] |
| **Checklists** | Items with checkboxes (□/☐). | Workbooks, self-help, project management | [new] |
| **Horizontal rules** | Section breaks within a chapter (visual separator). | Literature, non-fiction | [done] — decorative elements → "---" |
| **Pull quotes** | Enlarged/highlighted excerpts from the main text, usually in magazines. | Magazines, journalism, textbooks | [new] |
| **Callout boxes** | Highlighted text in a box/frame with a label ("Note:", "Warning:", "Tip:"). | Technical, textbooks, self-help | [new] |
| **Sidebars** | Self-contained content boxes beside/within the main text. | Textbooks, journalism, popular science | [new] |
| **Margin notes / Marginalia** | Notes placed in the page margin, sometimes by the author, sometimes by a later editor. | Academic, annotated editions, religious | [new] |

---

## 4. Footnotes, Endnotes & Annotations

| Element | Description | Genres | Status |
|---------|-------------|--------|--------|
| **Page-bottom footnotes** (numbered) | 1, 2, 3... restarting per page or per chapter. | Academic, literature, history | [done] |
| **Page-bottom footnotes** (symbol) | *, †, ‡, §, ¶, ‖ — cycle repeats per page. | Literature, older academic | [partial] — detected but not all symbols |
| **Multi-paragraph footnotes** | A single footnote spanning multiple paragraphs. | Academic, legal | [new] |
| **Footnotes containing citations** | The footnote itself references other works. | Academic, history | [new] |
| **Footnotes containing equations** | Mathematical content within a footnote. | Math, physics, economics | [new] |
| **Continued footnotes** | "...continued from previous page" — a footnote too long for one page. | Academic, legal | [new] |
| **Chapter endnotes** | Notes collected at the end of each chapter. | Popular non-fiction, history | [planned] — Rules 4.3-4.4, Phase 2 |
| **Book-level endnotes** | All notes collected in a single back-matter section. | Academic, history | [planned] — Rules 4.3-4.4, Phase 2 |
| **Author notes vs. editor notes vs. translator notes** | Different origin markers (sometimes distinguished by number vs. symbol, or by label). | Translated works, annotated editions | [new] |
| **Marginal notes** | Notes in the margin rather than at page bottom. | Bibles, legal codes, annotated editions | [new] |
| **Glosses** | Explanatory notes between lines or in margins (medieval/religious texts). | Religious, historical manuscripts | [new] |
| **Commentary** | Extended annotation (distinct from footnotes), sometimes interleaved with source text. | Religious (Talmud-style), philosophy, legal | [new] |

---

## 5. Tables

| Element | Description | Genres | Status |
|---------|-------------|--------|--------|
| **Simple tables** | Regular rows/columns, no merged cells. ≤8 columns. | All non-fiction | [stub] — module exists, no pdfplumber logic |
| **Complex tables** | Merged cells (colspan/rowspan), nested headers. | Technical, scientific, financial | [stub] |
| **Multi-page tables** | Table continues across page break with repeated headers. | Technical, data-heavy, financial | [new] |
| **Rotated / landscape tables** | Table printed sideways on a portrait page. | Technical, data-heavy | [new] |
| **Borderless tables** | Aligned columns with no visible grid lines. | Various | [new] |
| **Statistical tables** | Dense numerical data with footnotes, significance markers. | Scientific, social science, economics | [new] |
| **Matrix / Grid tables** | Square grids (correlation matrices, truth tables, game theory payoffs). | Math, statistics, CS, economics | [new] |
| **Comparison tables** | Feature/attribute comparison grids. | Technical, consumer, textbooks | [new] |
| **Table captions** | "Table 3.1: Population Growth Rates" above or below the table. | All non-fiction | [stub] — Rule 6.4 exists |
| **Table notes** | Footnotes specific to the table (Source:, Note:, a, b, c markers). | Academic, scientific | [new] |
| **Correspondence tables** | Occult/esoteric mapping tables (element↔color↔planet↔symbol). | Occult, astrology, comparative religion | [new] |
| **Conjugation / Declension tables** | Verb/noun forms in language textbooks. | Language learning | [new] |
| **Periodic table references** | Chemistry-specific formatted tables. | Chemistry, science | [new] |
| **Truth tables** | Logic tables (T/F or 0/1). | Math, CS, philosophy | [new] |
| **Scheduling / Calendar tables** | Time-based grids. | Self-help, project management, educational | [new] |

---

## 6. Images, Figures & Visual Elements

### 6.1 — Image Types

| Element | Description | Genres | Status |
|---------|-------------|--------|--------|
| **Photographs** | Embedded raster photos. | All | [done] — basic extraction |
| **Line drawings / Illustrations** | Hand-drawn or vector-origin artwork. | Literature, children's, art, occult | [done] — extracted as raster |
| **Charts** (bar, line, pie, scatter, etc.) | Data visualization. | Technical, scientific, business, textbooks | [new] — often vector, needs rasterization |
| **Diagrams** (flowcharts, block, architecture) | Structural/process diagrams. | Technical, CS, engineering, business | [planned] — Rule 7.2, Phase 2 |
| **Maps** | Geographic, fantasy, historical, transit maps. | History, geography, fantasy, military | [new] |
| **Plates** | Full-page illustrations, often grouped in a separate section. | Art, natural history, archaeology | [new] |
| **Subfigures** | Multiple related images labeled (a), (b), (c), (d) within one figure. | Scientific, technical | [new] |
| **Inline figures** | Small images flowing within text (icons, small diagrams). | Technical, educational | [new] |
| **Full-page figures** | Image occupying an entire page. | Art, photography, atlases | [partial] — full-page scan backgrounds filtered |
| **Fold-out / gatefold pages** | Oversized images on fold-out pages (rare in PDFs but possible). | Engineering, atlases, art | [new] |
| **Color plate sections** | Grouped color images in a separate signature (common in older books). | Art, natural history, biology, medical | [new] |
| **Screenshots** | Computer/phone screen captures. | Technical, digital media | [new] |
| **Medical / anatomical illustrations** | Labeled body diagrams. | Medical, biology, anatomy | [new] |
| **Decorative ornaments** | Chapter-end ornaments, fleurons, printer's devices. | Literature, historical, fine editions | [done] — filtered as decorative |
| **Publisher logos** | Small logo on title/copyright page. | All | [partial] — small image filtering |
| **Author photos** | Portrait, usually on back matter or dust jacket page. | All | [new] |
| **QR codes** | Machine-readable codes linking to digital resources. | Modern technical, educational, marketing | [new] |
| **Watermarks** | Faint background images/text on pages. | Draft documents, proprietary | [new] |
| **Background textures** | Decorative page backgrounds (parchment effects, etc.). | Occult, fantasy, design books | [new] |

### 6.2 — Specialized Diagrams

| Element | Description | Genres | Status |
|---------|-------------|--------|--------|
| **Circuit diagrams** | Electronic/electrical schematics. | Electronics, engineering, physics | [new] |
| **Chemical structure diagrams** | Molecular structures, reaction mechanisms. | Chemistry, biochemistry, pharmacology | [new] |
| **Architectural drawings** | Floor plans, elevations, cross-sections. | Architecture, engineering | [new] |
| **Musical notation / Sheet music** | Staff notation, tablature, chord diagrams. | Music theory, composition, songbooks | [new] |
| **Genealogical trees** | Family trees, lineage charts. | History, biology, mythology, occult | [new] |
| **Organizational charts** | Hierarchy diagrams. | Business, political science | [new] |
| **UML diagrams** | Class, sequence, activity, state diagrams. | Software engineering, CS | [new] |
| **Network diagrams** | Topology, graph visualizations. | CS, networking, social science | [new] |
| **Feynman diagrams** | Particle interaction diagrams. | Quantum physics | [new] |
| **Free body diagrams** | Force diagrams in physics. | Physics, engineering | [new] |
| **Phase diagrams** | State-of-matter diagrams. | Chemistry, materials science | [new] |
| **Punnett squares** | Genetic cross diagrams. | Biology, genetics | [new] |
| **Cladograms / Phylogenetic trees** | Evolutionary relationship diagrams. | Biology, paleontology | [new] |
| **Venn diagrams** | Set relationship circles. | Math, logic, various | [new] |
| **Timelines** (visual) | Graphical date-based sequences. | History, biography, project management | [new] |
| **Sephirotic trees** | Kabbalistic tree of life diagrams. | Occult, Jewish mysticism | [new] |
| **Astrological charts** | Natal charts, horoscope wheels. | Astrology, occult | [new] |
| **Sigils and seals** | Magical symbols, spirit seals, pentacles. | Occult, grimoires | [new] |
| **Mandala / Sacred geometry** | Circular spiritual diagrams. | Occult, Buddhist, Hindu texts | [new] |
| **Tarot layouts** | Card spread position diagrams. | Occult, divination | [new] |
| **Alchemical symbols** | Elemental and process symbols. | Occult, history of science | [new] |
| **Rune charts** | Runic alphabet tables with meanings. | Occult, Norse studies | [new] |
| **I Ching hexagram tables** | 64 hexagram reference grids. | Occult, Chinese philosophy | [new] |
| **Chakra diagrams** | Energy center illustrations. | Occult, yoga, Ayurveda | [new] |
| **Enochian tables / Squares** | Angel magic letter grids. | Occult (specifically Enochian tradition) | [new] |
| **Geometric constructions** | Compass-and-straightedge diagrams with steps. | Math, geometry, sacred geometry | [new] |

### 6.3 — Figure Metadata

| Element | Description | Genres | Status |
|---------|-------------|--------|--------|
| **Figure captions** | "Figure 3.2: The results of..." below/above figure. | All non-fiction | [planned] — Rule 7.3, Phase 2 |
| **Figure numbering** | Sequential per-chapter (Fig 3.1, 3.2) or continuous (Fig 1, 2, 3...). | Non-fiction | [partial] — fig-{ch}-{n} naming exists |
| **Source/credit lines** | "Source: WHO, 2023" or "Photo by: J. Smith" under figures. | Academic, journalism | [new] |
| **Alt text** | Accessibility descriptions (in tagged PDFs). | Digital-native, accessible publications | [new] |
| **Figure cross-references** | "see Figure 3.2" in body text. | Technical, academic | [new] |

---

## 7. Mathematics & Formal Notation

### 7.1 — Mathematical Content

| Element | Description | Genres | Status |
|---------|-------------|--------|--------|
| **Inline equations** | Math within running text: "where $x = 5$". | Math, physics, CS, economics, engineering | [new] |
| **Display equations** | Centered, standalone math on its own line. | Same as above | [new] |
| **Equation numbering** | Right-aligned "(3.14)" or "(2)" tags. | Same as above | [new] |
| **Multi-line equations** | Aligned at = or other operator across lines. | Same as above | [new] |
| **Matrices** | Rectangular arrays in brackets/parentheses. | Linear algebra, physics, CS | [new] |
| **Built-up fractions** | Numerator over denominator with horizontal bar. | All STEM | [new] |
| **Summation / Integral / Product** | Big operators with limits. | All STEM | [new] |
| **Greek letters** | α, β, γ, δ, Σ, Π, etc. | All STEM, philosophy (logic) | [partial] — preserved as Unicode when in text layer |
| **Mathematical symbols** | ∀, ∃, ∈, ⊆, →, ⟹, ≤, ≥, ≠, ∞, ∂, ∇, etc. | Math, logic, CS | [partial] — same |
| **Set notation** | {x ∈ ℝ : x > 0} | Math, CS | [new] |
| **Logic notation** | ∧, ∨, ¬, →, ↔, ⊢, ⊨ | Math, CS, philosophy | [new] |
| **Vectors and tensors** | Bold, arrow, hat notation. | Physics, engineering, math | [new] |
| **Chemical equations** | Balanced reactions with arrows and state indicators. | Chemistry | [new] |
| **Units and dimensions** | kg·m/s², properly formatted with thin spaces. | All STEM | [new] |
| **Binomial coefficients** | (n choose k) notation. | Math, statistics, CS | [new] |
| **Continued fractions** | Nested fraction towers. | Number theory | [new] |
| **Commutative diagrams** | Arrow diagrams (category theory). | Abstract math, CS theory | [new] |

### 7.2 — Theorem-like Environments

Formal mathematical/scientific structure blocks:

| Element | Description | Genres | Status |
|---------|-------------|--------|--------|
| **Theorem** | Formal statement, usually numbered and bold-labeled. | Math, CS theory | [new] |
| **Lemma** | Intermediate result used to prove a theorem. | Math, CS theory | [new] |
| **Corollary** | Direct consequence of a theorem. | Math, CS theory | [new] |
| **Proposition** | Less major than a theorem. | Math, CS theory | [new] |
| **Conjecture** | Unproved statement. | Math | [new] |
| **Definition** (formal) | Precise mathematical/technical definition, often numbered. | Math, CS, philosophy, law | [new] |
| **Axiom / Postulate** | Assumed truth. | Math, philosophy | [new] |
| **Proof** | Follows a theorem; ends with QED symbol (□, ∎, or "Q.E.D."). | Math, CS theory | [new] |
| **Example** (numbered) | Worked example, often numbered and titled. | Math, CS, physics, textbooks | [new] |
| **Remark** | Informal observation following a formal result. | Math | [new] |
| **Exercise** (numbered) | Problem for the reader, sometimes with difficulty rating. | Math, CS, physics, textbooks | [new] |
| **Solution** | Answer to a preceding exercise. | Textbooks | [new] |
| **Algorithm** (numbered) | Pseudocode with step numbers, input/output specification. | CS, operations research | [new] |
| **Case** | Sub-case within a proof (Case 1, Case 2...). | Math, CS | [new] |
| **Claim** | A statement to be proved within a proof. | Math | [new] |
| **Notation** | Declaration of notation used. | Math, CS | [new] |
| **Warning / Caveat** | Common mistakes or misconceptions, often boxed. | Textbooks | [new] |

---

## 8. Code & Technical Content

| Element | Description | Genres | Status |
|---------|-------------|--------|--------|
| **Code blocks** | Multi-line source code, usually monospace. | CS, software engineering, technical | [planned] — Phase 2 |
| **Code with syntax highlighting** | Color-coded keywords (in color PDFs). | Same | [new] |
| **Code with line numbers** | Numbered lines for reference. | Same | [new] |
| **Code listing captions** | "Listing 3.1: Database connection handler" | Same | [new] |
| **Inline code** | `variable_name` or `command` within prose. | Same | [new] |
| **Command-line examples** | Terminal commands with `$` or `>` prompts. | Same | [new] |
| **Console output** | Program output, logs, stack traces. | Same | [new] |
| **File paths** | `/etc/nginx/nginx.conf` — often monospace. | Same | [new] |
| **API documentation** | Method signatures, parameter tables, return types. | Same | [new] |
| **Pseudocode** | Algorithm description not in a real language. | CS, math | [new] |
| **Configuration files** | YAML, JSON, XML, INI snippets. | Technical, DevOps | [new] |
| **Database schemas** | Table/column definitions, ER diagrams. | CS, data engineering | [new] |
| **Regular expressions** | Pattern strings, often in monospace. | CS, technical | [new] |
| **Shell scripts** | bash/zsh/sh snippets. | Technical, DevOps | [new] |
| **Makefile / Build config** | Build system configuration. | Technical | [new] |
| **Register / Memory diagrams** | Bit-field layouts. | Systems programming, embedded, hardware | [new] |

---

## 9. Citations & Bibliography

### 9.1 — In-Text Citation Styles

| Style | Format | Fields | Status |
|-------|--------|--------|--------|
| **Author-date** (APA) | (Smith, 2020) or (Smith & Jones, 2020, p. 42) | Social science, psychology, education | [new] |
| **Numeric** (IEEE/Vancouver) | [1], [2,3], [1-5] | Engineering, CS, medical | [new] |
| **Author-page** (MLA) | (Smith 42) | Humanities, literature | [new] |
| **Footnote/endnote** (Chicago) | Superscript number → full citation in note | History, humanities, law | [partial] — footnotes detected, not parsed as citations |
| **Author-date** (Harvard) | (Smith 2020) — no comma | Various | [new] |
| **Legal citations** | Case name, volume, reporter, page (e.g., *Brown v. Board*, 347 U.S. 483) | Legal | [new] |
| **Scripture citations** | John 3:16, Quran 2:255, Torah references | Religious | [new] |
| **Multiple works** | (Smith, 2020; Jones, 2019; Lee et al., 2018) | Academic | [new] |
| **ibid., op. cit., loc. cit.** | Latin abbreviation references to prior citations. | Academic, older style | [new] |

### 9.2 — Bibliography / Reference List Formats

| Element | Description | Genres | Status |
|---------|-------------|--------|--------|
| **Bibliography** | Alphabetical list of works cited. | Academic, non-fiction | [new] |
| **References** / **Works Cited** | Same purpose, different label by style. | Academic | [new] |
| **Annotated bibliography** | Each entry followed by a summary/evaluation paragraph. | Academic | [new] |
| **Suggested / Further reading** | Curated list without formal citations. | Popular non-fiction, textbooks | [new] |
| **Discography** | Music reference list. | Music, cultural studies | [new] |
| **Filmography** | Film reference list. | Film studies, biography | [new] |
| **Webography / Sitography** | Web resource list. | Digital media, modern reference | [new] |
| **Primary vs. Secondary sources** | Separate sections for original documents vs. scholarship. | History, academic | [new] |

---

## 10. Back Matter

| Element | Description | Genres | Status |
|---------|-------------|--------|--------|
| **Appendices** | Supplementary material (A, B, C...), each like a mini-chapter. | Technical, academic, non-fiction | [new] |
| **Glossary** | Term → definition list, alphabetical. | All non-fiction, especially technical | [new] |
| **Subject index** | Topic → page number(s), hierarchical, with cross-references ("see also"). | Non-fiction, academic, technical | [new] |
| **Author / Name index** | People mentioned → page numbers. | Academic, history | [new] |
| **Scripture index** | Biblical/religious verse references → page numbers. | Religious, theological | [new] |
| **Symbol index** | Mathematical/technical symbols → page numbers. | Math, science | [new] |
| **Endnotes section** | All footnotes collected at the end, grouped by chapter. | Non-fiction, history | [planned] — Rules 4.3-4.4 |
| **Bibliography / References** | (see §9.2 above) | Academic | [new] |
| **Afterword** | Author reflection written after the main text (sometimes years later). | Literature, non-fiction | [new] |
| **Epilogue** | Narrative conclusion after the story proper. | Fiction | [new] |
| **Postscript** | Brief addition after the main text. | Various | [new] |
| **About the Author** | Brief biography, sometimes with photo. | All | [new] |
| **Colophon** (back) | Type/paper/binding details. | Fine editions, art books | [new] |
| **Errata** | List of known errors and corrections. | Academic, technical | [new] |
| **Answer keys** | Solutions to exercises/problems from the body. | Textbooks, workbooks | [new] |
| **Resource lists** | Organizations, websites, hotlines mentioned in the text. | Self-help, health, educational | [new] |
| **Permissions & Credits** | Copyright notices for quoted/reproduced material. | Anthologies, art books | [new] |
| **Also by this author** | Promotional list of other books. | All | [new] |
| **Reading group questions** | Discussion prompts for book clubs. | Fiction, popular non-fiction | [new] |
| **Excerpt from next book** | Preview chapter from the author's upcoming work. | Fiction (series) | [new] |

---

## 11. Educational / Textbook-Specific Elements

| Element | Description | Status |
|---------|-------------|--------|
| **Learning objectives** | Bullet list at chapter start ("After reading this chapter, you will be able to..."). | [new] |
| **Chapter outlines** | Brief preview of chapter contents. | [new] |
| **Key terms** (margin) | Vocabulary words defined in the margin alongside their first use in text. | [new] |
| **Key terms** (list) | Vocabulary list at chapter end. | [new] |
| **Worked examples** | Step-by-step solutions with explanation at each step. | [new] |
| **Practice problems** | End-of-chapter exercises, often numbered and categorized by difficulty. | [new] |
| **Review questions** | Conceptual questions testing comprehension. | [new] |
| **Discussion questions** | Open-ended prompts for group work. | [new] |
| **Critical thinking questions** | Higher-order analysis/evaluation prompts. | [new] |
| **Lab procedures** | Step-by-step experimental instructions. | [new] |
| **Lab report sections** | Purpose, Materials, Procedure, Data, Analysis, Conclusion templates. | [new] |
| **Self-assessment quizzes** | Quick checks with answers (often at section end). | [new] |
| **Chapter summaries** | Condensed review of key points at chapter end. | [new] |
| **Concept maps / Mind maps** | Visual topic relationship diagrams. | [new] |
| **"Did You Know?" boxes** | Fun fact or interesting tangent callouts. | [new] |
| **Real-world application boxes** | Case studies connecting theory to practice. | [new] |
| **Career connection boxes** | How the topic relates to specific jobs/professions. | [new] |
| **Historical context boxes** | Background on how a concept was discovered/developed. | [new] |
| **Safety warnings** | ⚠️ Lab safety, hazard notices. | [new] |
| **Multiple choice questions** | A/B/C/D format with correct answer indicated (or in answer key). | [new] |
| **True/False questions** | Binary assessment items. | [new] |
| **Fill-in-the-blank** | Sentences with missing words. | [new] |
| **Matching exercises** | Two-column matching (term ↔ definition). | [new] |
| **Pronunciation guides** | IPA transcriptions, phonetic spelling. | [new] |
| **Conjugation tables** | Verb form tables in language textbooks. | [new] |
| **Grammar rules** | Formal rule statements with examples. | [new] |

---

## 12. Occult, Esoteric & Religious Book Elements

These are specific to the user's collection emphasis and surprisingly varied in structure:

| Element | Description | Status |
|---------|-------------|--------|
| **Ritual instructions** | Step-by-step ceremonial procedures, often numbered, with supplies lists. | [new] |
| **Invocations / Incantations** | Formatted as verse, sometimes in archaic or foreign language, often centered or indented. | [new] |
| **Prayers** | Similar to invocations but typically set in italics or a distinct typeface. | [new] |
| **Correspondences tables** | Multi-column mappings (element↔direction↔color↔deity↔planet↔herb↔stone). Very common, often large. | [new] |
| **Planetary hours / Moon phases** | Calendar-style tables with astrological data. | [new] |
| **Ritual supply lists** | Ingredient/material lists (similar structure to recipes). | [new] |
| **Circle diagrams** | Ceremonial layout diagrams with cardinal directions and placement instructions. | [new] |
| **Meditation scripts** | Extended guided visualization text, often in a different voice/tense. | [new] |
| **Journal prompts** | Reflective questions for the reader to answer. | [new] |
| **Workbook exercises** | Fill-in sections, self-reflection activities, record-keeping templates. | [new] |
| **Symbol glossaries** | Occult symbol → meaning reference tables (often with small images). | [new] |
| **Pronunciation guides** (specialized) | How to pronounce deity names, Hebrew/Latin/Greek terms, Enochian words. | [new] |
| **Warnings / Precautions** | Spiritual safety advisories before practice sections. Very distinct from educational safety warnings. | [new] |
| **Sacred text quotations** | Extended quotes from holy books (Bible, Quran, Torah, Vedas, Book of the Dead) with verse references. | [new] |
| **Parallel text** | Original language alongside translation (common in Bible commentaries, Talmud, classical texts). | [new] |
| **Interlinear text** | Translation directly between lines of original text. | [new] |
| **Verse numbering** | Scripture verse numbers embedded in text (1 In the beginning God created... 2 And the earth was...). | [new] |
| **Hierarchical cosmology diagrams** | Planes of existence, angelic hierarchies, elemental kingdoms. | [new] |
| **Deity/entity profiles** | Structured entries: name, domain, attributes, offerings, day, planet, color, sigil. | [new] |
| **Spell recipes** | Structured: intent, ingredients, timing, procedure, closing. Like a recipe card. | [new] |
| **Divination spreads** | Numbered positions with meanings (tarot, rune, oracle layouts). | [new] |
| **Gematria tables** | Letter-to-number conversion tables (Hebrew, Greek, English). | [new] |
| **Numerical tables** | Number → meaning associations (numerology reference). | [new] |

---

## 13. Layout & Typography Challenges

Elements that affect how content is spatially arranged, not what it contains:

| Element | Description | Status |
|---------|-------------|--------|
| **Multi-column layout** (2-col) | Common in textbooks, journals, reference, newspapers. | [planned] — Rule 8, Phase 2 |
| **Multi-column layout** (3-col) | Encyclopedias, dictionaries, some reference books. | [planned] — Rule 8, Phase 2 |
| **Text wrapping around figures** | Text flows around an image, not just above/below. | [new] |
| **Widow and orphan lines** | Isolated lines at page top/bottom — not a content issue but affects cross-page merging heuristics. | [partial] — handled implicitly |
| **Decorative initial caps / Illuminated letters** | Oversized, ornate first letter spanning multiple lines. | [done] — drop cap merge |
| **Running headers** (variable) | Header text changes per chapter/section. | [done] — header/footer detection |
| **Running footers** (variable) | Footer text changes per section. | [done] |
| **Thumb tabs** | Visual markers on page edges for sections (reference books). | [new] |
| **Color coding** | Different background/text colors for different sections/chapters. | [new] |
| **Rotated text** | Text rotated 90° or 270° (spine text, some figure labels). | [new] |
| **Vertical text** | Top-to-bottom text (CJK vertical typesetting). | [new] |
| **Mixed column widths** | Some pages single-column, others multi-column. | [new] |
| **Inset panels** | Smaller text box overlapping or inset into the main text area. | [new] |
| **Bleed images** | Images extending to page edge (no margin). | [new] |
| **Spread layouts** | Content designed to span two facing pages. | [new] |

---

## 14. Language & Script Considerations

| Element | Description | Status |
|---------|-------------|--------|
| **Right-to-left (RTL) text** | Arabic, Hebrew, Urdu, Persian, Pashto, Dari. | [partial] — doesn't crash, reading order not verified |
| **Vertical text** | Traditional CJK (top-to-bottom, right-to-left columns). | [new] |
| **Bidirectional (bidi) text** | Mixed LTR and RTL in the same paragraph (Hebrew with English terms, Arabic with numbers). | [new] |
| **Mixed-script text** | Body in one script with terms/quotes in another (English text with Arabic calligraphy, Sanskrit verses). | [new] |
| **Transliteration** | Foreign words rendered in Latin script (with diacriticals). | [partial] — preserved in extraction |
| **IPA phonetic transcription** | /fəˈnɛtɪk/ notation. | [new] |
| **Ancient scripts** | Hieroglyphics, cuneiform, runes (often as images, sometimes as Unicode). | [new] |
| **Non-Latin alphabets** | Cyrillic, Greek, Devanagari, Thai, Korean, Japanese, Chinese, etc. | [partial] — extraction works if text layer exists |
| **Ruby / Furigana** | Small pronunciation text above CJK characters. | [new] |
| **Tone marks** | Vietnamese, Thai, Mandarin pinyin diacriticals. | [partial] — preserved |
| **Right-to-left page order** | Books read from right to left (manga, some Arabic texts). | [new] |

---

## 15. Interactive & Digital-Native Elements

Elements found in PDFs created digitally (not from print scanning):

| Element | Description | Status |
|---------|-------------|--------|
| **Internal hyperlinks** | Clickable cross-references to other parts of the document. | [new] |
| **External hyperlinks** | URLs linking to websites. | [new] |
| **PDF bookmarks / outline** | Navigation tree in PDF viewer sidebar. | [done] — used for heading detection |
| **Tagged PDF structure** | Accessibility tags marking headings, paragraphs, tables, figures. | [new] — could use as authoritative structure signal |
| **Form fields** | Fillable text boxes, checkboxes, radio buttons, dropdowns. | [new] |
| **Annotations / Comments** | Sticky notes, highlights, markup added by readers. | [new] |
| **Embedded file attachments** | Files attached within the PDF. | [new] |
| **JavaScript actions** | Interactive elements triggered by JS (rare in books). | [new] — ignore |
| **Layers / Optional content** | Different visibility states (draft/final, answer key overlays). | [new] |
| **3D models** | Embedded 3D objects (rare; some engineering/anatomy texts). | [new] — ignore initially |
| **Multimedia references** | "Scan QR code for video" or embedded media links. | [new] |
| **Digital signatures** | Signed/certified documents. | [new] — ignore |

---

## 16. Edge Cases & Pathological PDFs

Things that aren't "content elements" but that the pipeline must handle gracefully:

| Issue | Description | Status |
|-------|-------------|--------|
| **Scanned books** (image-only) | No text layer at all — requires OCR. | [partial] — detected, not processed |
| **OCR over scan** | Text layer exists but is low-quality OCR output (misspellings, artifacts). | [new] |
| **Password-protected PDFs** | Encrypted, may require password to open. | [new] — detect and report |
| **Corrupt PDF structure** | Malformed cross-reference tables, missing objects. | [partial] — pymupdf error handling |
| **Very large PDFs** | 1000+ pages, 500MB+ file size. | [new] — memory/performance concerns |
| **Linearized ("fast web view") PDFs** | Different internal structure, same content. | [done] — pymupdf handles transparently |
| **PDF/A archival format** | Stricter PDF standard, same content extraction. | [done] — pymupdf handles transparently |
| **Multiple pages per sheet** | 2-up or 4-up imposed pages (print signatures). | [new] |
| **Mixed page sizes** | Different page dimensions within one document. | [partial] — per-page width/height tracked |
| **Redacted content** | Black rectangles covering text. | [new] — detect and note |
| **Invisible text** | Text with same color as background (white text on white). | [new] |
| **CID-keyed fonts (no ToUnicode)** | Font encoding produces garbage instead of readable text. | [new] |
| **Type3 fonts** | Custom-drawn glyph shapes, hard to extract. | [done] — name comparison removed |
| **Ligature encoding issues** | fi, fl rendered as single unrecognized glyph. | [partial] |
| **Mojibake / encoding errors** | Wrong character encoding produces garbage. | [new] |
| **Duplicate text layers** | Two overlapping text layers (e.g., OCR + original). | [new] |
| **Negative coordinates** | Text positioned outside normal page bounds. | [new] |
| **Zero-width characters** | Invisible Unicode characters (ZWJ, ZWNJ, soft hyphens). | [new] |
| **Pages with no content** | Intentionally blank pages ("This page intentionally left blank"). | [new] |

---

## Element Count Summary

| Category | Count |
|----------|-------|
| Front matter elements | 24 |
| Structural hierarchy | 18 |
| Inline & block content | 37 |
| Footnotes & annotations | 12 |
| Tables | 16 |
| Images & figures | 43 |
| Mathematics & formal notation | 28 |
| Code & technical | 16 |
| Citations & bibliography | 17 |
| Back matter | 16 |
| Educational / textbook | 27 |
| Occult / esoteric / religious | 22 |
| Layout & typography | 16 |
| Language & script | 12 |
| Interactive & digital-native | 12 |
| Edge cases & pathological | 17 |
| **Total distinct elements** | **~333** |

### By Implementation Status

| Status | Count |
|--------|-------|
| [done] | ~25 |
| [partial] | ~18 |
| [stub] | ~3 |
| [planned] (in existing ROADMAP) | ~8 |
| [new] (not previously documented) | ~279 |

---

## Implementation Priority Tiers

Based on frequency across real-world book collections and impact on vault quality:

### Tier A — High Impact, Common Across Genres
These appear in most books and their absence significantly degrades the output:
- Parts (above-chapter divisions)
- Block quotes (non-epigraph)
- Lists (bulleted, numbered, nested)
- Callout/sidebar boxes
- Front matter detection and preservation (foreword, preface, dedication)
- Back matter (glossary, appendices, index)
- Multi-column layout
- Code blocks (for technical profile)
- Numbered section detection (Rule 2.4)
- Chapter number + title merging (the "9" problem)
- Endnotes
- Inline citations → bibliography linking

### Tier B — Medium Impact, Genre-Specific
Important for specific book types in the user's collection:
- Tables (simple and complex)
- Mathematical equations (inline and display)
- Theorem-like environments
- Correspondence/reference tables (occult)
- Poetry/verse preservation
- Ritual/recipe structured content
- Dialogue formatting
- Letters/epistolary content
- Figure captions
- Cross-references
- Margin notes

### Tier C — Lower Impact, Enhancement Quality
Nice-to-have refinements:
- Decorative initial caps (ornate, beyond simple drop caps)
- Pronunciation guides
- Hyperlink extraction
- Tagged PDF structure usage
- Color/highlight preservation
- Ruby text
- Alt text extraction
- Form field content
- Advanced diagram classification
- Parallel text layouts

### Tier D — Specialized / Rare
Very specific use cases:
- 3D models
- Sheet music notation
- Feynman diagrams
- Multiple pages per sheet (imposed layouts)
- JavaScript actions
- Digital signatures
- Enochian tables
- Commutative diagrams
