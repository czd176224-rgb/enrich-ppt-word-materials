from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps


def build_visual_review_packets(
    shortlists: list[dict[str, object]], output_dir: str | Path
) -> dict[str, object]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    pages: list[dict[str, object]] = []

    for shortlist in shortlists:
        page_number = int(shortlist["page"])
        candidates = list(shortlist.get("candidates", []))[:16]
        contact_sheet = None
        if candidates:
            sheet = Image.new("RGB", (1200, 280 * len(candidates)), "white")
            draw = ImageDraw.Draw(sheet)
            for index, candidate in enumerate(candidates, start=1):
                top = (index - 1) * 280
                render_path = Path(str(candidate["render_path"]))
                with Image.open(render_path) as source:
                    thumbnail = ImageOps.contain(source.convert("RGB"), (720, 240))
                sheet.paste(thumbnail, (10, top + 30))
                label = (
                    f"{index}. {candidate['asset_id']} | "
                    f"{candidate.get('asset_type')} | {candidate.get('score')}"
                )
                draw.text((750, top + 40), label, fill="black")
            target = destination / f"page-{page_number:03d}-candidates.png"
            sheet.save(target)
            contact_sheet = str(target.resolve())

        pages.append(
            {
                "page": page_number,
                "candidate_count": len(candidates),
                "contact_sheet": contact_sheet,
                "candidate_asset_ids": [item["asset_id"] for item in candidates],
            }
        )

    payload = {"schema_version": "visual-review-packet-v1", "pages": pages}
    (destination / "review-manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return payload
