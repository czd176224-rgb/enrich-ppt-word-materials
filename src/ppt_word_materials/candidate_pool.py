from __future__ import annotations


DEFAULT_ROLE_CAPS = {
    "identity": 1,
    "factual_visual": 4,
    "structural_visual": 3,
    "scene_visual": 4,
}
PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


def _priority(candidate: dict[str, object], page_need: dict[str, object]) -> str:
    role = str(candidate.get("director_role") or "")
    required = {str(value) for value in page_need.get("required_roles", [])}
    acceptable = {str(value) for value in page_need.get("acceptable_roles", [])}
    if role in required:
        return "P0"
    if role in acceptable:
        return "P1"
    if float(candidate.get("score") or 0) > 0:
        return "P2"
    return "P3"


def _duplicate_keys(candidate: dict[str, object]) -> tuple[str, str]:
    exact = str(
        candidate.get("delivery_render_sha256")
        or candidate.get("source_media_sha256")
        or ""
    )
    visual = str(
        candidate.get("delivery_visual_phash")
        or candidate.get("visual_phash")
        or ""
    )
    return exact, visual


def build_candidate_pools(
    shortlists: list[dict[str, object]],
    *,
    hard_limit: int = 16,
) -> list[dict[str, object]]:
    hard_limit = min(16, max(0, hard_limit))
    used_content_assets: set[str] = set()
    results: list[dict[str, object]] = []

    for shortlist in shortlists:
        page = int(shortlist["page"])
        page_need = dict(shortlist.get("page_need") or {})
        if page_need.get("need_status") == "not_needed":
            results.append(
                {
                    "page": page,
                    "decision": "not_needed",
                    "candidate_asset_ids": [],
                    "candidates": [],
                    "pool_reason": "page visual intent does not require source materials",
                }
            )
            continue

        candidate_range = list(page_need.get("candidate_range") or [0, hard_limit])
        upper_bound = min(hard_limit, int(candidate_range[1]))
        role_caps = dict(DEFAULT_ROLE_CAPS)
        if len(page_need.get("entities", [])) > 1:
            role_caps["identity"] = min(3, len(page_need.get("entities", [])))

        ranked: list[dict[str, object]] = []
        for raw in shortlist.get("candidates", []):
            candidate = dict(raw)
            candidate["priority"] = _priority(candidate, page_need)
            role = str(candidate.get("director_role") or "")
            candidate["pool_reason"] = (
                f"{candidate['priority']} {role} candidate for page intent"
            )
            ranked.append(candidate)
        ranked.sort(
            key=lambda item: (
                PRIORITY_ORDER[str(item["priority"])],
                -float(item.get("score") or 0),
                str(item.get("asset_id") or ""),
            )
        )

        selected: list[dict[str, object]] = []
        seen_exact: set[str] = set()
        seen_visual: set[str] = set()
        role_counts: dict[str, int] = {}
        for candidate in ranked:
            if len(selected) >= upper_bound:
                break
            asset_id = str(candidate.get("asset_id") or "")
            role = str(candidate.get("director_role") or "")
            if not asset_id or role not in role_caps:
                continue
            if role != "identity" and asset_id in used_content_assets:
                continue
            exact_key, visual_key = _duplicate_keys(candidate)
            if (exact_key and exact_key in seen_exact) or (
                visual_key and visual_key in seen_visual
            ):
                continue
            if role_counts.get(role, 0) >= role_caps[role]:
                continue
            selected.append(candidate)
            if exact_key:
                seen_exact.add(exact_key)
            if visual_key:
                seen_visual.add(visual_key)
            role_counts[role] = role_counts.get(role, 0) + 1
            if role != "identity":
                used_content_assets.add(asset_id)

        decision = "ready" if selected else "no_match"
        results.append(
            {
                "page": page,
                "decision": decision,
                "candidate_asset_ids": [str(item["asset_id"]) for item in selected],
                "candidates": selected,
                "pool_reason": (
                    "ordered by required role, acceptable role, relevance, diversity, and reuse policy"
                    if selected
                    else "no accurate candidate survived page-local pool policy"
                ),
            }
        )
    return results
