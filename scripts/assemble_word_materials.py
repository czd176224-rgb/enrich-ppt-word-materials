from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ppt_word_materials.assembly import assemble_material_docx
from ppt_word_materials.baseline import capture_document_baseline


def main() -> int:
    parser = argparse.ArgumentParser(description="Insert approved page-local materials into Word.")
    parser.add_argument("--word", required=True, type=Path)
    parser.add_argument("--decisions", required=True, type=Path)
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--width-inches", type=float, default=4.4)
    parser.add_argument("--multi-width-inches", type=float, default=3.1)
    args = parser.parse_args()

    decisions = json.loads(args.decisions.read_text(encoding="utf-8"))
    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    assembly = assemble_material_docx(
        args.word,
        decisions,
        inventory,
        args.output,
        width_inches=args.width_inches,
        multi_width_inches=args.multi_width_inches,
    )
    before = capture_document_baseline(args.word)
    after = capture_document_baseline(args.output)
    receipt = {
        "assembly": assembly,
        "before": {
            "physical_page_count": before["physical_pages"]["page_count"],
            "logical_page_count": before["logical_pages"]["logical_page_count"],
            "comments": before["package"]["comments"],
            "comments_sha256": before["package"]["comments_sha256"],
            "tables": before["package"]["tables"],
            "table_sha256": before["package"]["table_sha256"],
            "visible_text_sha256": before["package"]["text_signature"]["sha256"],
        },
        "after": {
            "physical_page_count": after["physical_pages"]["page_count"],
            "logical_page_count": after["logical_pages"]["logical_page_count"],
            "comments": after["package"]["comments"],
            "comments_sha256": after["package"]["comments_sha256"],
            "tables": after["package"]["tables"],
            "table_sha256": after["package"]["table_sha256"],
            "embedded_media": after["package"]["embedded_media"],
            "visible_text_sha256": after["package"]["text_signature"]["sha256"],
        },
    }
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(receipt["after"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
