from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ppt_word_materials.matching import validate_decisions


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--shortlists", type=Path, required=True)
    parser.add_argument("--require-visual-review", action="store_true")
    args = parser.parse_args()

    decisions = json.loads(args.decisions.read_text(encoding="utf-8"))
    shortlists = json.loads(args.shortlists.read_text(encoding="utf-8"))
    result = validate_decisions(
        decisions,
        shortlists,
        require_visual_review=args.require_visual_review,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
