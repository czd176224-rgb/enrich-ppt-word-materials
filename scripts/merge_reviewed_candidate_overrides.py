from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate reviewed legacy decisions and merge reviewed additions.")
    parser.add_argument("--legacy-decisions", required=True, type=Path)
    parser.add_argument("--additions", required=True, type=Path)
    parser.add_argument("--shortlists", required=True, type=Path)
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--output-decisions", required=True, type=Path)
    parser.add_argument("--output-shortlists", required=True, type=Path)
    args = parser.parse_args()

    decisions = _load(args.legacy_decisions)
    additions = _load(args.additions)
    shortlists = _load(args.shortlists)
    inventory = _load(args.inventory)
    assets = {str(item["asset_id"]): item for item in inventory["assets"]}
    shortlist_by_page = {int(item["page"]): item for item in shortlists}
    additions_by_page = {int(item["page"]): item for item in additions}

    merged_decisions = []
    for legacy in decisions:
        page = int(legacy["page"])
        selected = [str(value) for value in legacy.get("selected_asset_ids", [])]
        reviews = list(legacy.get("visual_reviews", []))
        addition = additions_by_page.get(page, {"assets": []})
        for reviewed in addition.get("assets", []):
            asset_id = str(reviewed["asset_id"])
            if asset_id not in selected:
                selected.append(asset_id)
            reviews.append(
                {
                    "asset_id": asset_id,
                    "opened": True,
                    "visual_decision": "accept",
                    "reason": str(reviewed["reason"]),
                }
            )
            shortlist = shortlist_by_page[page]
            known = {str(item["asset_id"]) for item in shortlist.get("candidates", [])}
            if asset_id not in known:
                asset = assets[asset_id]
                shortlist.setdefault("candidates", []).append(
                    {
                        "asset_id": asset_id,
                        "score": 1.0,
                        "asset_type": asset.get("asset_type"),
                        "source_file": asset.get("source_file"),
                        "source_page_or_slide": asset.get("source_page_or_slide"),
                        "render_path": asset.get("render_path"),
                        "asset_family": str(reviewed["asset_family"]),
                        "director_role": str(reviewed["director_role"]),
                        "fidelity_mode": str(reviewed["fidelity_mode"]),
                        "logo_family": reviewed.get("logo_family"),
                        "quality_status": asset.get("quality_status"),
                    }
                )
        state = "ready" if selected else (
            "not_needed" if legacy.get("decision") == "not_needed" else "no_match"
        )
        merged_decisions.append(
            {
                "page": page,
                "decision": state,
                "candidate_asset_ids": selected,
                "reason": str(addition.get("page_reason") or legacy.get("reason") or "无准确材料"),
                "confidence": float(legacy.get("confidence") or 0),
                "visual_reviews": reviews,
            }
        )

    args.output_decisions.parent.mkdir(parents=True, exist_ok=True)
    args.output_decisions.write_text(
        json.dumps(merged_decisions, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    args.output_shortlists.write_text(
        json.dumps(shortlists, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "pages": len(merged_decisions),
                "pages_with_candidates": sum(bool(item["candidate_asset_ids"]) for item in merged_decisions),
                "candidate_assets": sum(len(item["candidate_asset_ids"]) for item in merged_decisions),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
