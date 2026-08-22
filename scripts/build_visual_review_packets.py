from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ppt_word_materials.visual_review import build_visual_review_packets


def main() -> int:
    parser = argparse.ArgumentParser(description="Build candidate contact sheets for review.")
    parser.add_argument("--shortlists", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    shortlists = json.loads(args.shortlists.read_text(encoding="utf-8"))
    result = build_visual_review_packets(shortlists, args.output_dir)
    print(
        json.dumps(
            {
                "pages": len(result["pages"]),
                "pages_with_candidates": sum(
                    item["candidate_count"] > 0 for item in result["pages"]
                ),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
