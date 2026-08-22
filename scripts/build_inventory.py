from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ppt_word_materials.inventory import build_inventory


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a unified PDF/PPTX source-material inventory."
    )
    parser.add_argument("sources", nargs="+", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--no-render", action="store_true")
    args = parser.parse_args()

    result = build_inventory(
        args.sources, args.output_dir, render=not args.no_render
    )
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
