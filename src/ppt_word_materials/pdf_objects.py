from __future__ import annotations

import re


def rect_bbox(rect) -> list[float]:
    return [float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1)]


def area_ratio(rect, page_rect) -> float:
    page_area = max(1.0, float(page_rect.width * page_rect.height))
    return max(0.0, float(rect.width * rect.height) / page_area)


def overlap_over_smaller(left, right) -> float:
    intersection = left & right
    if intersection.is_empty:
        return 0.0
    denominator = max(1.0, min(float(left.get_area()), float(right.get_area())))
    return float(intersection.get_area()) / denominator


def expand_rect_with_nearby_text(page, primary_rect):
    """Include a close title/source line while excluding remote page furniture."""
    import fitz

    expanded = fitz.Rect(primary_rect)
    page_rect = page.rect
    above_limit = page_rect.height * 0.06
    below_limit = page_rect.height * 0.03
    primary_width = max(1.0, primary_rect.width)

    for block in page.get_text("blocks"):
        candidate = fitz.Rect(block[:4])
        text = str(block[4]).strip()
        if not text:
            continue
        horizontal = max(
            0.0,
            min(primary_rect.x1, candidate.x1) - max(primary_rect.x0, candidate.x0),
        )
        if horizontal / max(1.0, min(primary_width, candidate.width)) < 0.45:
            continue
        above_gap = primary_rect.y0 - candidate.y1
        below_gap = candidate.y0 - primary_rect.y1
        if 0 <= above_gap <= above_limit or 0 <= below_gap <= below_limit:
            expanded.include_rect(candidate)

    return expanded & page_rect


def classify_vector_region(text: str) -> str:
    numeric_tokens = re.findall(r"(?<!\w)\d+(?:\.\d+)?%?", text)
    return "pdf_chart_crop" if len(numeric_tokens) >= 2 else "pdf_diagram_crop"


def discover_pdf_object_regions(page) -> list[dict[str, object]]:
    """Return native images, tables and clustered vector graphics on one PDF page."""
    import fitz

    regions: list[dict[str, object]] = []
    occupied: list[fitz.Rect] = []
    seen_images: set[tuple[float, float, float, float]] = set()

    for info in page.get_image_info(xrefs=True):
        rect = fitz.Rect(info["bbox"])
        key = tuple(round(value, 2) for value in rect_bbox(rect))
        if key in seen_images or rect.is_empty:
            continue
        seen_images.add(key)
        regions.append(
            {
                "asset_type": "pdf_image_crop",
                "object_rect": rect,
                "xref": int(info.get("xref") or 0),
            }
        )
        occupied.append(rect)

    try:
        tables = page.find_tables().tables
    except (AttributeError, RuntimeError, ValueError):
        tables = []
    for table in tables:
        rect = fitz.Rect(table.bbox)
        if rect.is_empty:
            continue
        regions.append(
            {
                "asset_type": "pdf_table_crop",
                "object_rect": rect,
                "xref": 0,
            }
        )
        occupied.append(rect)

    drawings = page.get_drawings()
    for rect in page.cluster_drawings(
        drawings=drawings,
        x_tolerance=6,
        y_tolerance=6,
    ):
        rect = fitz.Rect(rect)
        if rect.is_empty or area_ratio(rect, page.rect) < 0.01:
            continue
        if any(overlap_over_smaller(rect, other) >= 0.65 for other in occupied):
            continue
        text = page.get_text("text", clip=rect).strip()
        regions.append(
            {
                "asset_type": classify_vector_region(text),
                "object_rect": rect,
                "xref": 0,
            }
        )
        occupied.append(rect)

    return regions
