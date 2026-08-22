from __future__ import annotations

import math
import re
from collections import Counter

from .page_needs import build_page_need_card


CHINESE_RUN = re.compile(r"[\u4e00-\u9fff]+")
ALNUM_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9+&/-]*|\d+(?:\.\d+)?%?")
PAGE_LABEL = re.compile(r"^第\s*\d+\s*页")


ASSET_FAMILY = {
    "ppt_chart_crop": "chart",
    "pdf_chart_crop": "chart",
    "ppt_table_crop": "table",
    "pdf_table_crop": "table",
    "ppt_diagram_crop": "diagram",
    "pdf_diagram_crop": "diagram",
    "ppt_picture": "image",
    "pdf_image_crop": "image",
}
DIRECTOR_ROLE = {
    "chart": "factual_visual",
    "table": "factual_visual",
    "diagram": "structural_visual",
    "image": "scene_visual",
    "logo": "identity",
}
ENTITY_PATTERN = re.compile(
    r"[\u4e00-\u9fffA-Za-z]{2,8}?(?:资本|基金|公会|协会|公司|集团|研究院|研究所|科技局)"
)
GENERIC_ENTITY_TERMS = {
    "社会资本", "政府投资基金", "政府引导基金", "私募投资基金", "投资基金",
    "母基金", "子基金", "产业基金", "并购基金", "基金", "公司", "子公司",
}
GENERIC_ENTITY_FRAGMENTS = (
    "投资基金", "引导基金", "产业基金", "并购基金", "母基金", "子基金",
    "社会资本", "证券基金", "股权基金",
)


def _valid_identity_entity(entity: str) -> bool:
    if entity in GENERIC_ENTITY_TERMS or entity.startswith(("年", "过", "与", "的")):
        return False
    if any(fragment in entity for fragment in GENERIC_ENTITY_FRAGMENTS):
        return False
    if entity.endswith("资本") and len(entity) > 6:
        return False
    return True
IDENTITY_PAGE_MARKERS = (
    "机构介绍", "公司介绍", "团队", "合作方", "合作伙伴", "联合", "管理人", "分工"
)


def _asset_family(asset: dict[str, object]) -> str | None:
    if asset.get("asset_role") == "identity_candidate":
        return "logo"
    return ASSET_FAMILY.get(str(asset.get("asset_type") or ""))


def _director_role(asset: dict[str, object]) -> str | None:
    family = _asset_family(asset)
    return DIRECTOR_ROLE.get(family or "")


def _fidelity_mode(asset: dict[str, object]) -> str:
    return "crop_ok" if _director_role(asset) == "scene_visual" else "exact"


def _identity_entities(asset: dict[str, object]) -> list[str]:
    supplied = [str(value) for value in asset.get("identity_entities", []) if str(value)]
    if supplied:
        return supplied
    text = "\n".join(
        str(asset.get(key) or "")
        for key in ("object_text", "text", "nearby_text", "source_file")
    )
    result: list[str] = []
    for entity in ENTITY_PATTERN.findall(text):
        if _valid_identity_entity(entity) and entity not in result:
            result.append(entity)
    return result


def _identity_page_context(page_text: str) -> tuple[bool, bool, str]:
    lines = [line.strip() for line in page_text.splitlines() if line.strip()]
    title_lines = [line for line in lines if not PAGE_LABEL.match(line)]
    # Identity must be the page subject, not an entity mentioned later in body text.
    title_context = title_lines[0] if title_lines else ""
    identity_intent = any(marker in title_context for marker in IDENTITY_PAGE_MARKERS)
    joint_page = any(marker in title_context for marker in ("联合", "合作方", "合作伙伴"))
    return identity_intent, joint_page, title_context


def _tokens(text: str) -> list[str]:
    normalized = text.lower()
    tokens = ALNUM_TOKEN.findall(normalized)
    for run in CHINESE_RUN.findall(normalized):
        if len(run) == 1:
            tokens.append(run)
            continue
        tokens.extend(run[index : index + 2] for index in range(len(run) - 1))
        if len(run) >= 3:
            tokens.extend(run[index : index + 3] for index in range(len(run) - 2))
    return tokens


def _title_weighted_tokens(text: str) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    title_lines = [line for line in lines if not PAGE_LABEL.match(line)][:2]
    title_tokens = _tokens("\n".join(title_lines))
    return _tokens(text) + title_tokens * 3


def _idf(documents: list[list[str]]) -> dict[str, float]:
    document_count = len(documents)
    frequency: Counter[str] = Counter()
    for tokens in documents:
        frequency.update(set(tokens))
    return {
        token: math.log((document_count + 1) / (count + 1)) + 1
        for token, count in frequency.items()
    }


def _vector(tokens: list[str], idf: dict[str, float]) -> dict[str, float]:
    counts = Counter(tokens)
    return {
        token: (1 + math.log(count)) * idf.get(token, 1.0)
        for token, count in counts.items()
    }


def _cosine(left: dict[str, float], right: dict[str, float]) -> float:
    common = set(left).intersection(right)
    numerator = sum(left[token] * right[token] for token in common)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if not left_norm or not right_norm:
        return 0.0
    return numerator / (left_norm * right_norm)


def decide_from_scores(
    scores: list[float], *, strong_threshold: float = 0.18, ambiguity_gap: float = 0.08
) -> str:
    if not scores or scores[0] < strong_threshold:
        return "no_match"
    if len(scores) > 1 and scores[0] - scores[1] < ambiguity_gap:
        return "ambiguous"
    return "strong"


def build_shortlists(
    logical_pages: list[dict[str, object]],
    assets: list[dict[str, object]],
    *,
    top_k: int = 5,
) -> list[dict[str, object]]:
    top_k = min(16, max(0, top_k))
    searchable: list[dict[str, object]] = []
    asset_tokens: list[list[str]] = []
    for asset in assets:
        if asset.get("asset_role") in {"decoration", "decorative", "forbidden"}:
            continue
        if not asset.get("eligible"):
            continue
        if asset.get("asset_scope") not in {None, "visual_object"}:
            continue
        if asset.get("deliverable") is False:
            continue
        if asset.get("contract_errors"):
            continue
        if asset.get("quality_status") not in {None, "pass", "pass_with_warning"}:
            continue
        if _asset_family(asset) is None:
            continue
        text = "\n".join(
            str(asset.get(key) or "")
            for key in ("text", "nearby_text", "source_file")
        )
        if asset.get("ocr_required") and not text.strip():
            continue
        tokens = _title_weighted_tokens(text)
        if not tokens:
            continue
        searchable.append(asset)
        asset_tokens.append(tokens)

    idf = _idf(asset_tokens)
    asset_vectors = [_vector(tokens, idf) for tokens in asset_tokens]
    results: list[dict[str, object]] = []

    for page in logical_pages:
        page_need = build_page_need_card(page)
        if page_need["need_status"] == "not_needed":
            results.append(
                {
                    "page": page["number"],
                    "page_text": page.get("text", ""),
                    "page_need": page_need,
                    "automatic_decision": "not_needed",
                    "candidates": [],
                }
            )
            continue
        page_tokens = _title_weighted_tokens(str(page.get("text") or ""))
        identity_intent, joint_identity_page, identity_title_context = _identity_page_context(
            str(page.get("text") or "")
        )
        page_vector = _vector(page_tokens, idf)
        ranked: list[tuple[float, dict[str, object]]] = []
        for asset, vector in zip(searchable, asset_vectors):
            score = _cosine(page_vector, vector)
            family = _asset_family(asset)
            if family is None:
                continue
            matched_identity_entity = None
            if family == "logo":
                entities = _identity_entities(asset)
                matched_identity_entity = next(
                    (
                        entity
                        for entity in entities
                        if entity and entity in str(page.get("text") or "")
                    ),
                    None,
                )
                if matched_identity_entity is None:
                    continue
                entity_is_page_subject = matched_identity_entity in identity_title_context
                if not entity_is_page_subject:
                    continue
            allowed = set(page_need["allowed_families"])
            if family not in allowed:
                continue
            type_weight = {
                "ppt_chart_crop": 1.2,
                "ppt_table_crop": 1.15,
                "pdf_chart_crop": 1.2,
                "pdf_table_crop": 1.15,
                "ppt_diagram_crop": 1.1,
                "pdf_diagram_crop": 1.1,
                "ppt_picture": 1.05,
                "pdf_image_crop": 1.05,
            }.get(str(asset.get("asset_type")), 1.0)
            score *= type_weight
            if family in page_need["preferred_families"]:
                score *= 1.15
            if family == "logo":
                score = score * 1.8 + 0.35
            if asset.get("evidence_level") == "A":
                score *= 1.05
            quality_score = float(asset.get("quality_score") or 100)
            score *= 0.9 + 0.1 * max(0.0, min(100.0, quality_score)) / 100
            if score <= 0:
                continue
            ranked.append((score, {**asset, "matched_identity_entity": matched_identity_entity}))
        ranked.sort(key=lambda item: item[0], reverse=True)
        selected_ranked: list[tuple[float, dict[str, object]]] = []
        logo_limit = 3 if joint_identity_page else 1
        logo_count = 0
        for score, asset in ranked:
            if _asset_family(asset) == "logo":
                if logo_count >= logo_limit:
                    continue
                logo_count += 1
            selected_ranked.append((score, asset))
            if len(selected_ranked) >= top_k:
                break
        candidates = [
            {
                "asset_id": asset["asset_id"],
                "score": round(score, 6),
                "asset_type": asset.get("asset_type"),
                "source_file": asset.get("source_file"),
                "source_page_or_slide": asset.get("source_page_or_slide"),
                "text": asset.get("text"),
                "render_path": asset.get("render_path"),
                "asset_family": _asset_family(asset),
                "director_role": _director_role(asset),
                "fidelity_mode": _fidelity_mode(asset),
                "logo_family": (
                    asset.get("matched_identity_entity")
                    or asset.get("logo_family")
                    if _asset_family(asset) == "logo"
                    else None
                ),
                "evidence_level": asset.get("evidence_level"),
                "quality_status": asset.get("quality_status"),
                "source_media_sha256": asset.get("source_media_sha256"),
                "delivery_render_sha256": asset.get("delivery_render_sha256"),
                "delivery_visual_phash": (
                    asset.get("delivery_visual_phash") or asset.get("visual_phash")
                ),
            }
            for score, asset in selected_ranked
        ]
        scores = [float(candidate["score"]) for candidate in candidates]
        results.append(
            {
                "page": page["number"],
                "page_text": page.get("text", ""),
                "page_need": page_need,
                "automatic_decision": decide_from_scores(scores),
                "candidates": candidates,
            }
        )
    return results


def validate_decisions(
    decisions: list[dict[str, object]],
    shortlists: list[dict[str, object]],
    *,
    max_per_page: int = 16,
    require_visual_review: bool = False,
) -> dict[str, object]:
    errors: list[str] = []
    shortlist_by_page = {int(item["page"]): item for item in shortlists}
    seen_pages: set[int] = set()
    selected_globally: dict[str, int] = {}
    candidate_count = 0

    for item in decisions:
        page = int(item["page"])
        if page in seen_pages:
            errors.append(f"duplicate_page:{page}")
        seen_pages.add(page)
        if page not in shortlist_by_page:
            errors.append(f"unknown_page:{page}")
            continue
        decision = str(item.get("decision") or "")
        if decision not in {"ready", "strong", "ambiguous", "no_match", "not_needed"}:
            errors.append(f"invalid_decision:{page}:{decision}")
        selected = [
            str(value)
            for value in item.get(
                "candidate_asset_ids",
                item.get("selected_asset_ids", []),
            )
        ]
        candidate_count += len(selected)
        if len(selected) > max_per_page:
            errors.append(f"too_many_assets:{page}:{len(selected)}")
        if len(selected) != len(set(selected)):
            errors.append(f"duplicate_asset_on_page:{page}")
        if decision not in {"ready", "strong"} and selected:
            errors.append(f"selection_requires_ready:{page}")
        if decision in {"ready", "strong"} and not selected:
            errors.append(f"ready_requires_selection:{page}")
        allowed = {
            str(candidate["asset_id"])
            for candidate in shortlist_by_page[page].get("candidates", [])
        }
        candidates_by_id = {
            str(candidate["asset_id"]): candidate
            for candidate in shortlist_by_page[page].get("candidates", [])
        }
        identity_selected = [
            asset_id
            for asset_id in selected
            if candidates_by_id.get(asset_id, {}).get("asset_family") == "logo"
        ]
        _, joint_identity_page, _ = _identity_page_context(
            str(shortlist_by_page[page].get("page_text") or "")
        )
        identity_limit = 3 if joint_identity_page else 1
        if len(identity_selected) > identity_limit:
            errors.append(f"too_many_identity_assets:{page}:{len(identity_selected)}")
        visual_reviews = {
            str(review.get("asset_id")): review
            for review in item.get("visual_reviews", [])
        }
        for asset_id in selected:
            if asset_id not in allowed:
                errors.append(f"not_in_shortlist:{page}:{asset_id}")
            previous_page = selected_globally.get(asset_id)
            if previous_page is not None and previous_page != page:
                candidate = candidates_by_id.get(asset_id, {})
                logo_family = str(candidate.get("logo_family") or "")
                page_text = str(shortlist_by_page[page].get("page_text") or "")
                reusable_identity = (
                    candidate.get("asset_family") == "logo"
                    and bool(logo_family)
                    and logo_family in page_text
                )
                if not reusable_identity:
                    errors.append(
                        f"asset_reused_across_pages:{asset_id}:{previous_page}:{page}"
                    )
            selected_globally[asset_id] = page
            candidate = candidates_by_id.get(asset_id, {})
            if require_visual_review:
                review = visual_reviews.get(asset_id)
                if review is None:
                    errors.append(f"missing_visual_review:{page}:{asset_id}")
                    continue
                if review.get("opened") is not True:
                    errors.append(f"visual_not_opened:{page}:{asset_id}")
                if review.get("visual_decision") != "accept":
                    errors.append(f"visual_not_accepted:{page}:{asset_id}")
                if not str(review.get("reason") or "").strip():
                    errors.append(f"visual_reason_required:{page}:{asset_id}")

    missing_pages = sorted(set(shortlist_by_page).difference(seen_pages))
    if missing_pages:
        errors.append("missing_pages:" + ",".join(map(str, missing_pages)))
    return {
        "valid": not errors,
        "errors": errors,
        "pages": len(decisions),
        "selected_assets": len(selected_globally),
        "candidate_assets": candidate_count,
    }
