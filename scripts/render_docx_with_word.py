from __future__ import annotations

import argparse
from pathlib import Path

import fitz
import pythoncom
import win32com.client


WD_EXPORT_FORMAT_PDF = 17


def main() -> int:
    parser = argparse.ArgumentParser(description="Render DOCX pages with Microsoft Word and PyMuPDF.")
    parser.add_argument("docx", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--dpi", type=int, default=144)
    args = parser.parse_args()

    source = args.docx.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = output_dir / f"{source.stem}.pdf"

    pythoncom.CoInitialize()
    word = None
    document = None
    try:
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0
        document = word.Documents.Open(
            str(source), ReadOnly=True, AddToRecentFiles=False, ConfirmConversions=False
        )
        document.Repaginate()
        document.ExportAsFixedFormat(str(pdf_path), WD_EXPORT_FORMAT_PDF)
    finally:
        if document is not None:
            document.Close(False)
        if word is not None:
            word.Quit()
        pythoncom.CoUninitialize()

    scale = args.dpi / 72
    pdf = fitz.open(pdf_path)
    for index, page in enumerate(pdf, start=1):
        pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        pixmap.save(output_dir / f"page-{index:03d}.png")
    print(f"pages={len(pdf)} pdf={pdf_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
