from __future__ import annotations


CONTEXT_ASSET_TYPES = {"pdf_page", "ppt_slide"}
VISUAL_OBJECT_TYPES = {
    "ppt_picture",
    "ppt_chart_crop",
    "ppt_table_crop",
    "ppt_diagram_crop",
    "pdf_image_crop",
    "pdf_chart_crop",
    "pdf_table_crop",
    "pdf_diagram_crop",
    "photo",
    "chart",
    "table",
    "process_diagram",
    "architecture_diagram",
    "fund_structure",
    "map",
    "case_visual",
    "infographic_region",
}


def _full_page_like(asset: dict[str, object]) -> bool:
    bbox = asset.get("source_bbox")
    canvas = asset.get("source_canvas")
    if not isinstance(bbox, list) or len(bbox) != 4:
        return False
    if not isinstance(canvas, list) or len(canvas) != 2:
        return False
    x0, y0, x1, y1 = (float(value) for value in bbox)
    width, height = (float(value) for value in canvas)
    if width <= 0 or height <= 0 or x1 <= x0 or y1 <= y0:
        return False
    coverage = ((x1 - x0) * (y1 - y0)) / (width * height)
    edge_tolerance_x = width * 0.02
    edge_tolerance_y = height * 0.02
    touched_edges = sum(
        (
            x0 <= edge_tolerance_x,
            y0 <= edge_tolerance_y,
            x1 >= width - edge_tolerance_x,
            y1 >= height - edge_tolerance_y,
        )
    )
    return coverage >= 0.80 or touched_edges >= 3


def validate_deliverable_asset(asset: dict[str, object]) -> dict[str, object]:
    errors: list[str] = []
    asset_type = str(asset.get("asset_type") or "")
    scope = str(asset.get("asset_scope") or "")
    if asset_type in CONTEXT_ASSET_TYPES or scope == "context":
        errors.append("context_asset_not_deliverable")
    if scope != "visual_object":
        errors.append("asset_scope_not_visual_object")
    if not asset.get("deliverable"):
        errors.append("deliverable_flag_required")
    if asset_type not in VISUAL_OBJECT_TYPES:
        errors.append("unsupported_visual_object_type")
    if _full_page_like(asset):
        errors.append("full_page_like_crop")
    return {"valid": not errors, "errors": errors}
