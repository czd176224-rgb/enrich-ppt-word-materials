from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ppt_word_materials.inventory import finalize_inventory_records


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reapply role, quality, and eligibility gates without rescanning sources."
    )
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    payload = json.loads(args.inventory.read_text(encoding="utf-8"))
    records, summary = finalize_inventory_records(
        list(payload["assets"]),
        source_file_count=int(payload.get("summary", {}).get("source_files") or 0),
    )
    result = {
        "schema_version": "ppt-word-material-inventory-v2",
        "summary": summary,
        "assets": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
