from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path

import pythoncom
import win32com.client
from PIL import Image


def _natural_number(path: Path) -> int:
    match = re.search(r"(\d+)(?=\D*$)", path.stem)
    return int(match.group(1)) if match else 0


def render_pptx_slides(
    source_pptx: str | Path,
    output_dir: str | Path,
    *,
    width: int = 1600,
    height: int = 900,
) -> list[Path]:
    source = Path(source_pptx).resolve()
    destination = Path(output_dir).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    pythoncom.CoInitialize()
    app = None
    presentation = None
    try:
        app = win32com.client.DispatchEx("PowerPoint.Application")
        with tempfile.TemporaryDirectory(dir=destination) as temp:
            export_dir = Path(temp) / "export"
            presentation = app.Presentations.Open(
                str(source), ReadOnly=True, WithWindow=False
            )
            presentation.Export(str(export_dir), "PNG", width, height)
            exported = sorted(export_dir.glob("*.PNG"), key=_natural_number)
            if not exported:
                exported = sorted(export_dir.glob("*.png"), key=_natural_number)
            paths: list[Path] = []
            for index, exported_path in enumerate(exported, start=1):
                target = destination / f"slide-{index:03d}.png"
                shutil.copy2(exported_path, target)
                paths.append(target)
            return paths
    finally:
        if presentation is not None:
            presentation.Close()
        if app is not None:
            app.Quit()
        pythoncom.CoUninitialize()


def crop_shape_from_slide(
    slide_png: str | Path,
    output_png: str | Path,
    *,
    bbox_emu: list[int | float],
    slide_size_emu: list[int | float],
) -> Path:
    source = Path(slide_png)
    output = Path(output_png)
    with Image.open(source) as image:
        slide_width, slide_height = map(float, slide_size_emu)
        left, top, width, height = map(float, bbox_emu)
        x1 = max(0, round(left / slide_width * image.width))
        y1 = max(0, round(top / slide_height * image.height))
        x2 = min(image.width, round((left + width) / slide_width * image.width))
        y2 = min(image.height, round((top + height) / slide_height * image.height))
        if x2 <= x1 or y2 <= y1:
            raise ValueError("Shape crop is empty after mapping to slide pixels")
        output.parent.mkdir(parents=True, exist_ok=True)
        image.crop((x1, y1, x2, y2)).save(output)
    return output
