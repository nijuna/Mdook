from pathlib import Path

import pymupdf

from mdook.core.rules.zones import (
    _page_has_back_matter_signal,
    _page_has_front_matter_signal,
    detect_zones,
)


def test_front_matter_keyword_in_prose_is_not_matched(tmp_path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=600)
    page.insert_text(
        (72, 100),
        "Space is viewed purely, without contents, as a form of intuition.",
        fontsize=11,
    )
    assert not _page_has_front_matter_signal(page)
    doc.close()


def test_standalone_contents_heading_is_matched(tmp_path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=600)
    page.insert_text((72, 100), "Table of Contents", fontsize=18)
    assert _page_has_front_matter_signal(page)
    doc.close()


def test_preface_heading_is_matched(tmp_path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=600)
    page.insert_text((72, 100), "Preface to the Second Edition", fontsize=18)
    assert _page_has_front_matter_signal(page)
    doc.close()


def test_copyright_metadata_is_matched(tmp_path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=600)
    page.insert_text(
        (72, 100), "Copyright 2026 by Academic Press. All rights reserved.", fontsize=9
    )
    assert _page_has_front_matter_signal(page)
    doc.close()


def test_back_matter_heading_is_matched(tmp_path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=600)
    page.insert_text((72, 100), "Bibliography", fontsize=18)
    assert _page_has_back_matter_signal(page)
    doc.close()


def test_back_matter_keyword_in_prose_is_not_matched(tmp_path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=600)
    page.insert_text(
        (72, 100),
        "The author made notes in the margin while consulting earlier works.",
        fontsize=11,
    )
    assert not _page_has_back_matter_signal(page)
    doc.close()


def test_detect_zones_separates_front_body_and_back(tmp_path: Path) -> None:
    doc = pymupdf.open()
    # 20 pages total
    for i in range(20):
        p = doc.new_page(width=400, height=600)
        if i == 0:
            p.insert_text((72, 100), "Table of Contents", fontsize=18)
        elif i == 19:
            p.insert_text((72, 100), "Index", fontsize=18)
        else:
            p.insert_text((72, 100), f"Body paragraph on page {i + 1}.", fontsize=11)

    zones = detect_zones(doc)
    doc.close()

    assert len(zones) == 3
    assert zones[0].zone_type == "front_matter"
    assert zones[0].start_page == 1
    assert zones[0].end_page == 1

    assert zones[1].zone_type == "body"
    assert zones[1].start_page == 2
    assert zones[1].end_page == 19

    assert zones[2].zone_type == "back_matter"
    assert zones[2].start_page == 20
    assert zones[2].end_page == 20
