from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ppt_word_materials.candidate_pool import build_candidate_pools


def main() -> int:
    parser = argparse.ArgumentParser(description="Build ordered page-local Director candidate pools.")
    parser.add_argument("--shortlists", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    shortlists = json.loads(args.shortlists.read_text(encoding="utf-8"))
    pools = build_candidate_pools(shortlists)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(pools, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "pages": len(pools),
                "pages_with_candidates": sum(bool(item["candidate_asset_ids"]) for item in pools),
                "candidate_assets": sum(len(item["candidate_asset_ids"]) for item in pools),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
