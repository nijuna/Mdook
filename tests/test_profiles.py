from pathlib import Path

import pymupdf

from mdook.core.models import Bookmark
from mdook.core.rules.profiles import (
    classify_profile,
)
from mdook.core.stages.intake import run_intake


def test_literature_profile_detected_for_novel(tmp_path: Path) -> None:
    pdf_path = tmp_path / "novel.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=600)
    page.insert_text(
        (72, 100),
        "Call me Ishmael. Some years ago—never mind how long precisely—having "
        "little or no money in my purse, and nothing particular to interest me on shore, "
        "I thought I would sail about a little and see the watery part of the world.",
        fontsize=11,
        fontname="times-roman",
    )
    doc.save(str(pdf_path))
    doc.close()

    manifest = run_intake(pdf_path, profile_override="auto")
    assert manifest.profile == "literature"


def test_technical_profile_detected_from_numbered_bookmarks(tmp_path: Path) -> None:
    pdf_path = tmp_path / "tech_manual.pdf"
    doc = pymupdf.open()
    page1 = doc.new_page(width=400, height=600)
    page1.insert_text((72, 100), "Overview of system design.", fontsize=11, fontname="helv")
    page2 = doc.new_page(width=400, height=600)
    page2.insert_text((72, 100), "Detailed component architecture.", fontsize=11, fontname="helv")
    doc.set_toc(
        [
            [1, "1.1 System Architecture", 1],
            [2, "1.1.1 Microservices", 1],
            [1, "1.2 Data Pipeline", 2],
        ]
    )
    doc.save(str(pdf_path))
    doc.close()

    manifest = run_intake(pdf_path, profile_override="auto")
    assert manifest.profile == "technical"


def test_technical_profile_detected_from_numbered_headings_in_text(tmp_path: Path) -> None:
    pdf_path = tmp_path / "spec.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=600)
    page.insert_text((72, 100), "1.1 Introduction and Scope\n", fontsize=14, fontname="helv")
    page.insert_text(
        (72, 150),
        "This specification defines the communication protocol.\n",
        fontsize=10,
        fontname="helv",
    )
    page.insert_text((72, 200), "1.2 Protocol Format\n", fontsize=14, fontname="helv")
    page.insert_text(
        (72, 250), "Packets are serialized as binary frames.\n", fontsize=10, fontname="helv"
    )
    doc.save(str(pdf_path))
    doc.close()

    manifest = run_intake(pdf_path, profile_override="auto")
    assert manifest.profile == "technical"


def test_technical_profile_detected_from_code_blocks(tmp_path: Path) -> None:
    pdf_path = tmp_path / "programming.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=600)
    page.insert_text((72, 100), "Here is an implementation:\n", fontsize=10, fontname="helv")
    page.insert_text(
        (72, 130), "def compute_hash(data: bytes) -> str:\n", fontsize=9, fontname="courier"
    )
    page.insert_text((72, 150), "    import hashlib\n", fontsize=9, fontname="courier")
    page.insert_text(
        (72, 170), "    return hashlib.sha256(data).hexdigest()\n", fontsize=9, fontname="courier"
    )
    doc.save(str(pdf_path))
    doc.close()

    manifest = run_intake(pdf_path, profile_override="auto")
    assert manifest.profile == "technical"


def test_technical_profile_detected_from_math_symbols(tmp_path: Path) -> None:
    pdf_path = tmp_path / "calculus.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=600)
    page.insert_text(
        (72, 100), "Theorem 1. Let f be a continuous function.\n", fontsize=11, fontname="helv"
    )
    page.insert_text((72, 140), "E = mc² ± 5 × 10\n", fontsize=10, fontname="helv")
    page.insert_text((72, 180), "f(x) = x² + y³\n", fontsize=10, fontname="helv")
    page.insert_text((72, 220), "Lemma 2. Energy is conserved.\n", fontsize=11, fontname="helv")
    doc.save(str(pdf_path))
    doc.close()

    manifest = run_intake(pdf_path, profile_override="auto")
    assert manifest.profile == "technical"


def test_explicit_profile_override_preempts_detection(tmp_path: Path) -> None:
    pdf_path = tmp_path / "manual_override.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=600)
    page.insert_text((72, 100), "1.1 Introduction\n1.2 Overview\n", fontsize=12, fontname="courier")
    doc.save(str(pdf_path))
    doc.close()

    # Even though it has technical signals, explicit "literature" must win
    manifest = run_intake(pdf_path, profile_override="literature")
    assert manifest.profile == "literature"


def test_classify_profile_fallback_on_invalid_doc() -> None:
    # Passing an arbitrary invalid object should safely return literature fallback
    profile = classify_profile(object(), bookmarks=[Bookmark(level=1, title="Test", page_number=1)])
    assert profile == "literature"
