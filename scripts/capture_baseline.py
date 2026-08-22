from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ppt_word_materials.baseline import capture_document_baseline


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Capture OOXML, logical-page, and Word physical-page baselines."
    )
    parser.add_argument("docx", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    result = capture_document_baseline(args.docx)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output": str(args.output.resolve()),
                "logical_pages": result["logical_pages"]["logical_page_count"],
                "physical_pages": result["physical_pages"]["page_count"],
                "sha256": result["source_sha256"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
