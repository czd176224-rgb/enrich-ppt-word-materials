from __future__ import annotations


def bbox_xyxy(shape) -> list[int]:
    return [
        int(shape.left),
        int(shape.top),
        int(shape.left + shape.width),
        int(shape.top + shape.height),
    ]


def bbox_xywh(bbox: list[int]) -> list[int]:
    x0, y0, x1, y1 = bbox
    return [x0, y0, x1 - x0, y1 - y0]


def valid_bbox_xywh(bbox: list[int | float]) -> bool:
    return len(bbox) == 4 and bbox[2] > 0 and bbox[3] > 0


def _horizontal_overlap(left: list[int], right: list[int]) -> float:
    overlap = max(0, min(left[2], right[2]) - max(left[0], right[0]))
    denominator = max(1, min(left[2] - left[0], right[2] - right[0]))
    return overlap / denominator


def expand_bbox_with_nearby_text(
    primary_shape,
    slide_shapes,
    *,
    slide_width: int,
    slide_height: int,
) -> list[int]:
    """Include a nearby title/source line without absorbing the slide header."""
    expanded = bbox_xyxy(primary_shape)
    primary = list(expanded)
    above_limit = slide_height * 0.08
    below_limit = slide_height * 0.04

    for candidate in slide_shapes:
        if candidate is primary_shape or not getattr(candidate, "has_text_frame", False):
            continue
        if not candidate.text.strip():
            continue
        candidate_bbox = bbox_xyxy(candidate)
        if _horizontal_overlap(primary, candidate_bbox) < 0.45:
            continue
        above_gap = primary[1] - candidate_bbox[3]
        below_gap = candidate_bbox[1] - primary[3]
        if 0 <= above_gap <= above_limit or 0 <= below_gap <= below_limit:
            expanded[0] = min(expanded[0], candidate_bbox[0])
            expanded[1] = min(expanded[1], candidate_bbox[1])
            expanded[2] = max(expanded[2], candidate_bbox[2])
            expanded[3] = max(expanded[3], candidate_bbox[3])

    expanded[0] = max(0, expanded[0])
    expanded[1] = max(0, expanded[1])
    expanded[2] = min(slide_width, expanded[2])
    expanded[3] = min(slide_height, expanded[3])
    return expanded


def shape_text_recursive(shape) -> str:
    parts: list[str] = []
    if getattr(shape, "has_text_frame", False) and shape.text.strip():
        parts.append(shape.text.strip())
    if getattr(shape, "has_table", False):
        parts.extend(
            "\t".join(cell.text.strip() for cell in row.cells)
            for row in shape.table.rows
        )
    for child in getattr(shape, "shapes", []):
        child_text = shape_text_recursive(child)
        if child_text:
            parts.append(child_text)
    return "\n".join(part for part in parts if part)
