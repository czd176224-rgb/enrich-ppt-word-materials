from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, ImageFilter, ImageStat


NATIVE_OBJECT_TYPES = {
    "pdf_image_crop",
    "ppt_picture",
    "ppt_chart_crop",
    "ppt_table_crop",
}
DIAGRAM_TYPES = {"pdf_diagram_crop", "ppt_diagram_crop"}
TEXT_IMAGE_TYPES = {"pdf_image_crop", "ppt_picture"}
STAMP_KEYWORDS = ("印章", "公章", "盖章", "专用章", "用印")
OFFICIAL_DOCUMENT_MARKERS = (
    "通知", "意见", "公报", "方案", "决定", "办法", "批复", "函", "文件"
)


def _run_lengths(values: list[bool]) -> list[tuple[bool, int]]:
    if not values:
        return []
    runs: list[tuple[bool, int]] = []
    current = values[0]
    length = 1
    for value in values[1:]:
        if value == current:
            length += 1
            continue
        runs.append((current, length))
        current = value
        length = 1
    runs.append((current, length))
    return runs


def _finder_pattern_matches(values: list[bool]) -> int:
    runs = _run_lengths(values)
    matches = 0
    for index in range(len(runs) - 4):
        window = runs[index : index + 5]
        if [color for color, _ in window] != [True, False, True, False, True]:
            continue
        lengths = [length for _, length in window]
        unit = sum((lengths[0], lengths[1], lengths[3], lengths[4])) / 4
        if unit < 1:
            continue
        expected = (1, 1, 3, 1, 1)
        if all(0.45 <= length / (unit * ratio) <= 1.8 for length, ratio in zip(lengths, expected)):
            matches += 1
    return matches


def _qr_finder_score(gray: Image.Image) -> int:
    sample = gray.copy()
    sample.thumbnail((280, 280))
    width, height = sample.size
    binary = [value < 110 for value in sample.getdata()]
    score = 0
    row_step = max(1, height // 120)
    column_step = max(1, width // 120)
    for y in range(0, height, row_step):
        score += _finder_pattern_matches(binary[y * width : (y + 1) * width])
    for x in range(0, width, column_step):
        score += _finder_pattern_matches([binary[y * width + x] for y in range(height)])
    return score


def _evidence(asset: dict[str, object]) -> tuple[str, str]:
    if asset.get("asset_scope") != "visual_object" or not asset.get("deliverable"):
        return "R", "not_deliverable"
    asset_type = str(asset.get("asset_type") or "")
    if asset_type == "pdf_image_crop" and (
        asset.get("xref") or asset.get("original_media_path")
    ):
        return "A", "pdf_native_image_object"
    if asset_type in NATIVE_OBJECT_TYPES:
        return "A", "source_object_with_rendered_crop"
    return "B", "bounded_rendered_source_region"


def evaluate_asset_quality(asset: dict[str, object]) -> dict[str, object]:
    evidence_level, evidence_basis = _evidence(asset)
    result: dict[str, object] = {
        "evidence_level": evidence_level,
        "evidence_basis": evidence_basis,
        "quality_status": "not_applicable",
        "quality_score": 0,
        "quality_errors": [],
        "quality_warnings": [],
        "quality_metrics": {},
    }
    if evidence_level == "R":
        return result

    errors: list[str] = []
    warnings: list[str] = []
    render_value = asset.get("render_path")
    if not render_value or not Path(str(render_value)).exists():
        errors.append("missing_quality_render")
        result.update(
            {
                "quality_status": "reject",
                "quality_errors": errors,
                "quality_score": 0,
            }
        )
        return result

    try:
        with Image.open(str(render_value)) as image:
            width, height = image.size
            rgba = image.convert("RGBA")
            white_background = Image.new("RGBA", rgba.size, "white")
            white_background.alpha_composite(rgba)
            rgb = white_background.convert("RGB")
            gray = rgb.convert("L")
            gray_stats = ImageStat.Stat(gray)
            visual_stddev = float(gray_stats.stddev[0])
            edge_variance = float(
                ImageStat.Stat(gray.filter(ImageFilter.FIND_EDGES)).var[0]
            )
            thumbnail = rgb.copy()
            thumbnail.thumbnail((600, 600))
            pixels = list(thumbnail.getdata())
            pixel_count = max(1, len(pixels))
            white_ratio = sum(
                red > 242 and green > 242 and blue > 242
                for red, green, blue in pixels
            ) / pixel_count
            dark_ratio = sum(
                max(red, green, blue) < 100 for red, green, blue in pixels
            ) / pixel_count
            red_ratio = sum(
                red > 145
                and red > green * 1.35
                and red > blue * 1.35
                and green < 150
                for red, green, blue in pixels
            ) / pixel_count
            mean_saturation = sum(
                (max(pixel) - min(pixel)) / 255 for pixel in pixels
            ) / pixel_count
            edge_mean = float(
                ImageStat.Stat(
                    gray.resize((300, 300)).filter(ImageFilter.FIND_EDGES)
                ).mean[0]
            )
            entropy = float(gray.entropy())
            qr_finder_score = _qr_finder_score(gray)
    except (OSError, ValueError):
        errors.append("unreadable_quality_render")
        result.update(
            {
                "quality_status": "reject",
                "quality_errors": errors,
                "quality_score": 0,
            }
        )
        return result

    pixel_area = width * height
    megapixels = pixel_area / 1_000_000
    aspect_ratio = width / max(1, height)
    object_text = str(asset.get("object_text") or "")
    text_chars = len(re.sub(r"\s+", "", object_text))
    text_chars_per_megapixel = text_chars / max(0.05, megapixels)
    object_lines = [line.strip() for line in object_text.splitlines() if line.strip()]
    long_object_lines = sum(len(re.sub(r"\s+", "", line)) >= 12 for line in object_lines)
    metrics = {
        "pixel_width": width,
        "pixel_height": height,
        "megapixels": round(megapixels, 4),
        "aspect_ratio": round(aspect_ratio, 4),
        "visual_stddev": round(visual_stddev, 3),
        "edge_variance": round(edge_variance, 3),
        "text_chars": text_chars,
        "text_chars_per_megapixel": round(text_chars_per_megapixel, 2),
        "object_text_lines": len(object_lines),
        "long_object_text_lines": long_object_lines,
        "white_ratio": round(white_ratio, 4),
        "dark_ratio": round(dark_ratio, 4),
        "red_ratio": round(red_ratio, 4),
        "mean_saturation": round(mean_saturation, 4),
        "edge_mean": round(edge_mean, 3),
        "entropy": round(entropy, 3),
        "qr_finder_score": qr_finder_score,
    }

    identity_candidate = asset.get("asset_role") == "identity_candidate"
    if identity_candidate:
        if width < 130 or height < 40 or pixel_area < 7_000:
            errors.append("insufficient_identity_dimensions")
    elif width < 180 or height < 100 or pixel_area < 30_000:
        errors.append("insufficient_pixel_dimensions")
    if aspect_ratio < 0.125 or aspect_ratio > 8:
        errors.append("extreme_aspect_ratio")
    if visual_stddev < 5:
        errors.append("low_visual_information")
    if (
        str(asset.get("asset_type") or "") in DIAGRAM_TYPES
        and text_chars >= 500
        and text_chars_per_megapixel >= 700
    ):
        errors.append("text_dominant_diagram")
    if (
        str(asset.get("asset_type") or "") in DIAGRAM_TYPES
        and white_ratio >= 0.75
        and mean_saturation <= 0.03
        and entropy < 2.2
    ):
        errors.append("text_or_title_only_diagram")

    asset_type = str(asset.get("asset_type") or "")
    source_name = Path(str(asset.get("source_file") or "")).name
    official_source = any(marker in source_name for marker in OFFICIAL_DOCUMENT_MARKERS)
    explicit_stamp = (
        asset_type == "pdf_image_crop"
        and official_source
        and any(keyword in object_text for keyword in STAMP_KEYWORDS)
    )
    date_or_institution = bool(
        re.search(r"20\d{2}\s*年|(?:公司|委员会|政府|局|中心)", object_text)
    )
    stamp_geometry = (
        asset_type == "pdf_image_crop"
        and red_ratio >= 0.08
        and white_ratio >= 0.60
        and 0.45 <= aspect_ratio <= 2.2
    )
    if explicit_stamp or (
        not identity_candidate
        and stamp_geometry
        and official_source
        and (date_or_institution or red_ratio >= 0.15)
    ):
        errors.append("stamp_or_seal")
    elif not identity_candidate and stamp_geometry:
        warnings.append("possible_stamp_or_seal")

    scanner_mark = (
        asset_type == "pdf_image_crop"
        and identity_candidate
        and bool(asset.get("ocr_required"))
        and not object_text.strip()
        and 2.0 <= aspect_ratio <= 5.0
        and white_ratio >= 0.45
        and dark_ratio >= 0.12
        and edge_mean >= 20
        and (entropy >= 4.5 or dark_ratio >= 0.20)
    )
    square_qr = (
        asset_type in TEXT_IMAGE_TYPES
        and 0.65 <= aspect_ratio <= 1.55
        and dark_ratio >= 0.10
        and white_ratio >= 0.20
        and qr_finder_score >= 6
    )
    if scanner_mark or square_qr:
        errors.append("qr_code_or_scanner_mark")

    document_text_layout = (
        text_chars_per_megapixel >= 450
        or (
            text_chars >= 150
            and len(object_lines) >= 8
            and long_object_lines >= 5
        )
    )
    metadata_text_panel = (
        asset_type in TEXT_IMAGE_TYPES
        and not identity_candidate
        and text_chars >= 120
        and document_text_layout
        and len(object_lines) >= 4
        and long_object_lines >= 3
        and white_ratio >= 0.35
        and mean_saturation <= 0.08
    )
    visual_text_panel = (
        asset_type in TEXT_IMAGE_TYPES
        and not identity_candidate
        and not object_text.strip()
        and white_ratio >= 0.72
        and mean_saturation <= 0.06
        and 0.008 <= dark_ratio <= 0.20
        and edge_mean >= 2.0
        and entropy < 3.5
    )
    if metadata_text_panel or visual_text_panel:
        errors.append("text_dominant_image")

    if (
        identity_candidate
        and entropy >= 6.8
        and dark_ratio >= 0.25
        and white_ratio < 0.25
    ):
        warnings.append("identity_visual_mismatch")

    if not errors:
        if (identity_candidate and (width < 180 or height < 55)) or (
            not identity_candidate and (width < 320 or height < 180)
        ):
            warnings.append("small_but_usable")
        if edge_variance < 80:
            warnings.append("low_edge_definition")
        if text_chars_per_megapixel >= 700:
            warnings.append("dense_text")

    score = max(0, 100 - 40 * len(errors) - 10 * len(warnings))
    result.update(
        {
            "quality_status": (
                "reject" if errors else "pass_with_warning" if warnings else "pass"
            ),
            "quality_score": score,
            "quality_errors": errors,
            "quality_warnings": warnings,
            "quality_metrics": metrics,
            "visual_review_required": bool(warnings) or identity_candidate,
        }
    )
    return result
