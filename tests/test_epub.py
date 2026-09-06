from pathlib import Path

from ebooklib import epub

from mdook.core.formats.epub import parse_epub
from mdook.core.models import (
    BlockQuote,
    CodeBlock,
    ImageRef,
    ListData,
    MathBlock,
    Paragraph,
    TableData,
)
from mdook.core.pipeline import convert


def _create_sample_epub(
    path: Path,
    title: str = "Test Book",
    author: str = "Arthur Conan Doyle",
    isbn: str = "978-0123456789",
    publisher: str = "Classic Press",
    is_technical: bool = False,
) -> Path:
    book = epub.EpubBook()
    book.set_identifier(isbn)
    book.set_title(title)
    book.set_language("en")
    book.add_author(author)
    book.add_metadata("DC", "publisher", publisher)
    book.add_metadata("DC", "date", "2024-05-12")

    # Embedded Image
    img_item = epub.EpubItem(
        uid="diagram1",
        file_name="images/diagram.png",
        media_type="image/png",
        content=b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82",
    )
    book.add_item(img_item)

    # Front Matter: Preface
    preface = epub.EpubHtml(title="Preface", file_name="preface.xhtml", lang="en")
    preface.content = """
    <html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
    <body epub:type="frontmatter">
        <h1>Preface</h1>
        <p>This is the author's preface to the work.</p>
    </body>
    </html>
    """
    book.add_item(preface)

    # Chapter 1 with rich content and footnotes
    ch1 = epub.EpubHtml(title="Chapter 1: The Beginning", file_name="ch01.xhtml", lang="en")
    if is_technical:
        ch1_content = """
        <html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
        <body>
            <h1>1.1 System Architecture</h1>
            <p>Here is an introduction to the <b>core algorithm</b> and <i>data pipelines</i>.</p>
            <h2>1.1.1 Implementation Details</h2>
            <pre><code>def compute_delta(x, y):
    return abs(x - y)
</code></pre>
            <table border="1">
                <tr><th>Metric</th><th>Score</th></tr>
                <tr><td>Accuracy</td><td>99.4%</td></tr>
                <tr><td colspan="2">Consolidated Benchmark</td></tr>
            </table>
            <figure>
                <img src="images/diagram.png" alt="Architecture Diagram"/>
                <figcaption>Figure 1: High-level overview</figcaption>
            </figure>
            <aside class="note">
                <p>Note: Always verify convergence before terminating.</p>
            </aside>
            <math display="block">E = mc^2</math>
            <p>1.2 Analysis and Conclusion</p>
        </body>
        </html>
        """
    else:
        ch1_content = """
        <html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
        <body>
            <h1>Chapter 1: The Beginning</h1>
            <p>It was a <b>bright</b> cold day in April, and the clocks were
            striking thirteen.<a href="#fn1" epub:type="noteref">1</a></p>
            <blockquote>
                <p>Wisdom begins in wonder.</p>
                <cite>Socrates</cite>
            </blockquote>
            <ul>
                <li>First observation</li>
                <li>Second observation</li>
            </ul>
            <ol>
                <li>Step Alpha</li>
                <li>Step Beta</li>
            </ol>
            <figure>
                <img src="images/diagram.png" alt="Portrait"/>
            </figure>
            <aside epub:type="footnote" id="fn1">
                <p>1. An unusual meteorological occurrence.</p>
            </aside>
        </body>
        </html>
        """
    ch1.content = ch1_content
    book.add_item(ch1)

    # Back Matter: Appendix
    appendix = epub.EpubHtml(title="Appendix", file_name="appendix.xhtml", lang="en")
    appendix.content = """
    <html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
    <body epub:type="backmatter">
        <h1>Appendix</h1>
        <p>Supplementary historical documentation.</p>
    </body>
    </html>
    """
    book.add_item(appendix)

    book.spine = ["nav", preface, ch1, appendix]
    book.toc = (
        epub.Link("preface.xhtml", "Preface", "preface"),
        epub.Link("ch01.xhtml", "Chapter 1", "ch1"),
        epub.Link("appendix.xhtml", "Appendix", "appendix"),
    )
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    epub.write_epub(str(path), book)
    return path


def test_epub_metadata_and_structure(tmp_path: Path) -> None:
    epub_file = tmp_path / "literature_book.epub"
    _create_sample_epub(epub_file, is_technical=False)

    manifest, tree = parse_epub(epub_file, profile_override="auto")

    assert manifest.title == "Test Book"
    assert manifest.author == "Arthur Conan Doyle"
    assert manifest.profile == "literature"
    assert manifest.needs_ocr is False
    assert manifest.total_pages >= 1

    # Check front matter
    assert len(tree.front_matter) >= 1
    assert any(sec.title == "Preface" for sec in tree.front_matter)

    # Check chapters
    assert len(tree.chapters) == 1
    ch = tree.chapters[0]
    assert "Chapter 1" in ch.title

    # Check back matter
    assert len(tree.back_matter) >= 1
    assert any(sec.title == "Appendix" for sec in tree.back_matter)


def test_epub_content_types(tmp_path: Path) -> None:
    epub_file = tmp_path / "content_test.epub"
    _create_sample_epub(epub_file, is_technical=False)

    manifest, tree = parse_epub(epub_file)
    ch = tree.chapters[0]

    all_content = [item for sec in ch.sections for item in sec.content]

    # Paragraph with inline formatting and footnote
    paragraphs = [c for c in all_content if isinstance(c, Paragraph)]
    assert any("**bright**" in p.text for p in paragraphs)

    # Footnote extraction
    assert len(ch.footnotes) == 1
    assert ch.footnotes[0].marker == "1"
    assert "meteorological occurrence" in ch.footnotes[0].text

    # Blockquote
    quotes = [c for c in all_content if isinstance(c, BlockQuote)]
    assert len(quotes) == 1
    assert any("Wisdom begins in wonder" in line for line in quotes[0].lines)
    assert quotes[0].attribution == "Socrates"

    # Lists
    lists = [c for c in all_content if isinstance(c, ListData)]
    assert len(lists) == 2
    unordered = next(item for item in lists if not item.items[0].ordered)
    ordered = next(item for item in lists if item.items[0].ordered)
    assert len(unordered.items) == 2
    assert len(ordered.items) == 2

    # Image
    images = [c for c in all_content if isinstance(c, ImageRef)]
    assert len(images) == 1
    assert Path(images[0].source_path).exists()


def test_epub_technical_profile_auto_detection(tmp_path: Path) -> None:
    epub_file = tmp_path / "tech_book.epub"
    _create_sample_epub(epub_file, is_technical=True)

    manifest, tree = parse_epub(epub_file, profile_override="auto")

    assert manifest.profile == "technical"
    ch = tree.chapters[0]
    all_content = [item for sec in ch.sections for item in sec.content]

    # CodeBlock
    codes = [c for c in all_content if isinstance(c, CodeBlock)]
    assert len(codes) >= 1
    assert any("compute_delta" in line for line in codes[0].lines)

    # TableData with complex colspan
    tables = [c for c in all_content if isinstance(c, TableData)]
    assert len(tables) >= 1
    assert tables[0].is_complex is True

    # MathBlock
    maths = [c for c in all_content if isinstance(c, MathBlock)]
    assert len(maths) >= 1
    assert "E = mc^2" in maths[0].latex_or_text


def test_epub_end_to_end_conversion(tmp_path: Path) -> None:
    epub_file = tmp_path / "full_book.epub"
    _create_sample_epub(epub_file, is_technical=False)

    vault_dir = tmp_path / "vaults"
    result = convert(epub_file, vault_dir)

    assert result.success is True
    assert result.output_dir.exists()
    assert result.chapters == 1
    assert result.footnotes == 1

    # Check files created in vault
    md_files = list(result.output_dir.glob("*.md"))
    filenames = {f.name for f in md_files}
    assert "00 - Front Matter.md" in filenames
    assert "Appendix.md" in filenames

    # Check attachments
    attachments_dir = result.output_dir / "attachments"
    assert attachments_dir.exists()
    assert len(list(attachments_dir.glob("*.png"))) >= 1

    # Check footnote rendering in chapter file
    chapter_file = next(f for f in md_files if "01 - " in f.name)
    content = chapter_file.read_text()
    assert "[^1]" in content
    assert "[^1]:" in content
