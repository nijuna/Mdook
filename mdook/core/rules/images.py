"""Rules 7.2-7.3 — Vector Diagram Rasterization & Caption Association.

Batch 16. Closes the two image rules explicitly deferred when Phase 3 (OCR)
took priority — see `Mdook-docs/RULES.md` section 7's evolution notes.

Implements:
- Rule 7.2: a page region covered by vector drawing operators
  (`page.get_drawings()`) but no extracted raster image is rasterized and
  saved like any other embedded image, so a diagram drawn with PDF paths
  (not a placed bitmap) isn't silently lost.
- Rule 7.3: a text block within `MAX_CAPTION_GAP` points of an image's
  bounding box, above or below, matching a caption-shaped prefix
  ("Figure 3.2", "Fig. 4", "Plate II", ...) becomes that image's caption.

Not implemented:
- Subfigure grouping ("(a)", "(b)" labels within one figure) — a plain
  caption match handles the common single-image-per-figure case; grouping
  related subfigures would need real multi-image test data to design well.
"""

from __future__ import annotations

import re

from mdook.core.models import TextBlock

BBox = tuple[float, float, float, float]

CAPTION_RE = re.compile(
    r"^(?:Figure|Fig\.?|Diagram|Illustration|Plate)\s*([\dIVXLCivxlc]+(?:\.\d+)?)?\.?\s*",
    re.IGNORECASE,
)
MAX_CAPTION_GAP = 30.0
MAX_CAPTION_WORDS = 40
MIN_DIAGRAM_SIZE = 50.0
"""A rasterized region shorter than this in either dimension (points) is
almost certainly a decorative rule or bullet glyph, not a real diagram."""
DRAWING_CLUSTER_GAP = 10.0
"""Two vector-drawing rects within this many points of each other are
treated as pieces of the same diagram (lines, fills, and curves that
together make up one figure rarely have larger gaps between them)."""


def find_caption(image_bbox: BBox, text_blocks: list[TextBlock]) -> TextBlock | None:
    """Returns the nearest caption-shaped `TextBlock` within
    `MAX_CAPTION_GAP` of `image_bbox` (checked both below and above the
    image — the conventional position is below, but some books set
    captions above a plate), or None if nothing nearby looks like a
    caption. The caller is responsible for removing the returned block from
    the page's ordinary text flow, the same way a footnote definition is
    removed once captured (`mdook.core.rules.footnotes`) — otherwise the
    caption text would render twice: once as a stray paragraph, once as the
    image's own caption line (Rule 7.5)."""
    best_gap: float | None = None
    best: TextBlock | None = None
    for block in text_blocks:
        stripped = block.text.strip()
        if CAPTION_RE.match(stripped) is None or len(stripped.split()) > MAX_CAPTION_WORDS:
            continue
        gap = _vertical_gap(image_bbox, block.bbox)
        if gap is None or gap > MAX_CAPTION_GAP:
            continue
        if best_gap is None or gap < best_gap:
            best_gap = gap
            best = block
    return best


def extract_figure_number(caption: str) -> str | None:
    """Pulls the figure number back out of an already-detected caption's
    text ("Figure 3.2: ..." -> "3.2"), for deriving a nicer attachment
    filename (`fig-3-2.png`) than the chapter/index-based fallback. None
    for an unnumbered caption."""
    match = CAPTION_RE.match(caption.strip())
    return match.group(1) if match else None


def _vertical_gap(image_bbox: BBox, other: BBox) -> float | None:
    _, iy0, _, iy1 = image_bbox
    _, by0, _, by1 = other
    if by0 >= iy1:
        return by0 - iy1  # other sits below the image
    if by1 <= iy0:
        return iy0 - by1  # other sits above the image
    return None  # vertically overlapping -- not a caption position


def cluster_drawing_regions(rects: list[BBox], exclude: list[BBox]) -> list[BBox]:
    """Groups vector-drawing rects into proximity clusters (union-find over
    all pairwise-close rects, so a connecting line between two boxes -- an
    ordinary flowchart -- correctly merges all three into one cluster
    rather than needing every rect to be close to every other) and returns
    each cluster's overall bounding box, for any cluster that (a) doesn't
    overlap an already-extracted image or a detected table's own bbox
    (both draw vector paths of their own -- a table's gridlines would
    otherwise be misidentified as a second copy of the same table) and (b)
    is at least `MIN_DIAGRAM_SIZE` in both width and height."""
    parent = list(range(len(rects)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            if _rects_close(rects[i], rects[j]):
                root_i, root_j = find(i), find(j)
                if root_i != root_j:
                    parent[root_i] = root_j

    groups: dict[int, list[BBox]] = {}
    for i, rect in enumerate(rects):
        groups.setdefault(find(i), []).append(rect)

    regions: list[BBox] = []
    for cluster in groups.values():
        region = _union_bbox(cluster)
        if region[2] - region[0] < MIN_DIAGRAM_SIZE or region[3] - region[1] < MIN_DIAGRAM_SIZE:
            continue
        if any(_rects_overlap(region, excluded) for excluded in exclude):
            continue
        regions.append(region)
    return regions


def _rects_close(a: BBox, b: BBox) -> bool:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    gap_x = max(bx0 - ax1, ax0 - bx1, 0.0)
    gap_y = max(by0 - ay1, ay0 - by1, 0.0)
    return gap_x <= DRAWING_CLUSTER_GAP and gap_y <= DRAWING_CLUSTER_GAP


def _rects_overlap(a: BBox, b: BBox) -> bool:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    return ax0 < bx1 and bx0 < ax1 and ay0 < by1 and by0 < ay1


def _union_bbox(rects: list[BBox]) -> BBox:
    return (
        min(r[0] for r in rects),
        min(r[1] for r in rects),
        max(r[2] for r in rects),
        max(r[3] for r in rects),
    )
