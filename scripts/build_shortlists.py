from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ppt_word_materials.matching import build_shortlists


def main() -> int:
    parser = argparse.ArgumentParser(description="Build page-local asset shortlists.")
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--top-k", type=int, default=16)
    args = parser.parse_args()

    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    results = build_shortlists(
        baseline["logical_pages"]["pages"],
        inventory["assets"],
        top_k=args.top_k,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    counts: dict[str, int] = {}
    for result in results:
        key = result["automatic_decision"]
        counts[key] = counts.get(key, 0) + 1
    print(json.dumps({"pages": len(results), "decisions": counts}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
