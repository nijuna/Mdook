"""Publication discovery and metadata scanning engine.

Discovers supported publication files (.pdf, .epub, .docx) in directories
and extracts lightweight metadata (title, author, file size) without running
the full conversion pipeline.
"""

from __future__ import annotations

import logging
import os
import re
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({".pdf", ".epub", ".docx"})
IGNORED_DIR_NAMES: frozenset[str] = frozenset(
    {
        ".git",
        ".github",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".obsidian",
    }
)

MAX_PLAUSIBLE_TITLE_LENGTH = 150
GARBAGE_TITLE_RE = re.compile(r"%[0-9A-Fa-f]{2}|[\\/]")
LAYOUT_FILENAME_RE = re.compile(
    r"^[\w\-.]+\.(?:qxd|indd|pmd|doc|docx|pdf|htm|html)$", re.IGNORECASE
)
WATERMARK_RE = re.compile(
    r"\s*(?:[-–—]\s*(?:PDFDrive(?:\.com)?|Z-Library|Libgen|Singlelogin|Anna's Archive).*"
    r"|\((?:z-lib\.org|pdfdrive\.com)\)\s*)$",
    re.IGNORECASE,
)


def format_file_size(size_bytes: int) -> str:
    """Formats bytes into human-readable size notation (B, KB, MB, GB)."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    if size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def _clean_title(raw_title: str | None, fallback: str) -> str:
    """Validates raw metadata titles, rejecting file paths, layout filenames, or
    URL-encoded noise."""
    if not raw_title:
        title = fallback
    else:
        stripped = raw_title.strip()
        if (
            not stripped
            or len(stripped) > MAX_PLAUSIBLE_TITLE_LENGTH
            or GARBAGE_TITLE_RE.search(stripped)
            or LAYOUT_FILENAME_RE.match(stripped)
        ):
            title = fallback
        else:
            title = stripped

    cleaned = WATERMARK_RE.sub("", title).strip()
    return cleaned or fallback


def _sniff_pdf_metadata(path: Path) -> tuple[str, str]:
    """Lightweight PDF metadata extraction via PyMuPDF."""
    try:
        import pymupdf

        doc = pymupdf.open(path)
        try:
            meta = doc.metadata or {}
            title = _clean_title(meta.get("title"), fallback=path.stem)
            author = (meta.get("author") or "Unknown").strip() or "Unknown"
            return title, author
        finally:
            doc.close()
    except Exception as exc:
        logger.debug("Failed to sniff PDF metadata for '%s': %s", path.name, exc)
        return path.stem, "Unknown"


def _sniff_epub_metadata(path: Path) -> tuple[str, str]:
    """Fast EPUB metadata extraction by inspecting container.xml and OPF package."""
    try:
        with zipfile.ZipFile(path, "r") as zf:
            # 1. Read META-INF/container.xml to find the OPF package path
            if "META-INF/container.xml" not in zf.namelist():
                return path.stem, "Unknown"

            container_xml = zf.read("META-INF/container.xml")
            container_root = ET.fromstring(container_xml)

            # Namespace-agnostic search for rootfile element
            opf_path = None
            for elem in container_root.iter():
                if elem.tag.endswith("rootfile") and "full-path" in elem.attrib:
                    opf_path = elem.attrib["full-path"]
                    break

            if not opf_path or opf_path not in zf.namelist():
                return path.stem, "Unknown"

            # 2. Parse OPF package metadata
            opf_xml = zf.read(opf_path)
            opf_root = ET.fromstring(opf_xml)

            title: str | None = None
            author: str | None = None

            for elem in opf_root.iter():
                tag_lower = elem.tag.lower()
                if tag_lower.endswith("title") and elem.text and not title:
                    title = elem.text.strip()
                elif tag_lower.endswith("creator") and elem.text and not author:
                    author = elem.text.strip()

            clean_title = _clean_title(title, fallback=path.stem)
            clean_author = (author or "Unknown").strip() or "Unknown"
            return clean_title, clean_author
    except Exception as exc:
        logger.debug("Failed to sniff EPUB metadata for '%s': %s", path.name, exc)
        return path.stem, "Unknown"


def _sniff_docx_metadata(path: Path) -> tuple[str, str]:
    """Fast DOCX metadata extraction by reading docProps/core.xml from the package."""
    try:
        with zipfile.ZipFile(path, "r") as zf:
            if "docProps/core.xml" not in zf.namelist():
                return path.stem, "Unknown"

            core_xml = zf.read("docProps/core.xml")
            root = ET.fromstring(core_xml)

            title: str | None = None
            author: str | None = None

            for elem in root.iter():
                tag_lower = elem.tag.lower()
                if tag_lower.endswith("title") and elem.text and not title:
                    title = elem.text.strip()
                elif tag_lower.endswith("creator") and elem.text and not author:
                    author = elem.text.strip()

            clean_title = _clean_title(title, fallback=path.stem)
            clean_author = (author or "Unknown").strip() or "Unknown"
            return clean_title, clean_author
    except Exception as exc:
        logger.debug("Failed to sniff DOCX metadata for '%s': %s", path.name, exc)
        return path.stem, "Unknown"


def sniff_book_metadata(path: Path) -> tuple[str, str]:
    """Inspects a publication file to extract (title, author) without full parsing."""
    ext = path.suffix.lower()
    if ext == ".pdf":
        return _sniff_pdf_metadata(path)
    if ext == ".epub":
        return _sniff_epub_metadata(path)
    if ext == ".docx":
        return _sniff_docx_metadata(path)
    return path.stem, "Unknown"


@dataclass(frozen=True)
class DiscoveredBook:
    """Represents a supported book publication discovered during scanning."""

    path: Path
    format: str
    size_bytes: int
    title: str
    author: str

    @property
    def filename(self) -> str:
        return self.path.name

    @property
    def stem(self) -> str:
        return self.path.stem

    @property
    def formatted_size(self) -> str:
        return format_file_size(self.size_bytes)


def scan_directory(
    target_dir: Path | str,
    recursive: bool = False,
) -> list[DiscoveredBook]:
    """Scans a directory for supported publication files (.pdf, .epub, .docx).

    Args:
        target_dir: Directory path to scan.
        recursive: If True, recursively scans child subdirectories while
            ignoring hidden and common package cache directories.

    Returns:
        List of DiscoveredBook objects sorted alphabetically by filename.

    Raises:
        FileNotFoundError: If target_dir does not exist.
        NotADirectoryError: If target_dir is not a directory.
    """
    path_obj = Path(target_dir).expanduser().resolve()
    if not path_obj.exists():
        raise FileNotFoundError(f"Directory not found: {path_obj}")
    if not path_obj.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {path_obj}")

    candidate_files: list[Path] = []

    if recursive:
        for root, dirs, files in os.walk(path_obj):
            # Prune ignored and hidden directories in-place
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in IGNORED_DIR_NAMES]
            root_path = Path(root)
            for file_name in files:
                if file_name.startswith(".") or file_name.startswith("~$"):
                    continue
                p = root_path / file_name
                if p.suffix.lower() in SUPPORTED_EXTENSIONS:
                    candidate_files.append(p)
    else:
        for p in path_obj.iterdir():
            if p.is_file():
                if p.name.startswith(".") or p.name.startswith("~$"):
                    continue
                if p.suffix.lower() in SUPPORTED_EXTENSIONS:
                    candidate_files.append(p)

    discovered: list[DiscoveredBook] = []
    for f in candidate_files:
        try:
            stat = f.stat()
            size = stat.st_size
            title, author = sniff_book_metadata(f)
            discovered.append(
                DiscoveredBook(
                    path=f,
                    format=f.suffix.lower().lstrip("."),
                    size_bytes=size,
                    title=title,
                    author=author,
                )
            )
        except Exception as exc:
            logger.debug("Skipping unreadable candidate file '%s': %s", f.name, exc)
            continue

    # Sort alphabetically by filename (case-insensitive)
    discovered.sort(key=lambda b: (b.filename.lower(), str(b.path)))
    return discovered
