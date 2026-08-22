from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ppt_word_materials.forward_validation import validate_awesome_forward_project


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Awesome page/image bindings.")
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--assembly-receipt", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    receipt = json.loads(args.assembly_receipt.read_text(encoding="utf-8"))
    assembly = receipt["assembly"]
    expected = {
        int(page): [
            str(item.get("embedded_sha256") or item["sha256"])
            for item in items
        ]
        for page, items in assembly["assignments"].items()
    }
    result = validate_awesome_forward_project(
        args.project,
        expected,
        page_count=int(assembly["logical_pages"]),
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered)
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
