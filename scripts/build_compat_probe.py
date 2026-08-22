from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ppt_word_materials.probe_docx import insert_probe_images


COLORS = [(220, 30, 40), (20, 150, 70), (30, 90, 220)]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a page-ownership DOCX probe.")
    parser.add_argument("docx", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--pages", required=True, nargs="+", type=int)
    args = parser.parse_args()

    probe_dir = args.output.parent / "probe-images"
    probe_dir.mkdir(parents=True, exist_ok=True)
    assignments: dict[int, Path] = {}
    for index, page in enumerate(args.pages):
        image_path = probe_dir / f"probe-page-{page:03d}.png"
        image = Image.new("RGB", (160, 160), COLORS[index % len(COLORS)])
        ImageDraw.Draw(image).text((55, 72), f"P{page}", fill="white")
        image.save(image_path)
        assignments[page] = image_path

    result = insert_probe_images(
        args.docx, assignments, args.output, width_inches=0.15
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
