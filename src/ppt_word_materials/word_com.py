from __future__ import annotations

from pathlib import Path

import pythoncom
import win32com.client

from .baseline import make_text_signature


WD_GOTO_PAGE = 1
WD_GOTO_ABSOLUTE = 1
WD_STATISTIC_PAGES = 2


def _clean_word_range_text(text: str) -> str:
    return text.replace("\x07", "").replace("\x0c", "").strip("\r\n")


def capture_word_pages(path: str | Path) -> dict[str, object]:
    source = str(Path(path).resolve())
    pythoncom.CoInitialize()
    word = None
    document = None
    try:
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0
        document = word.Documents.Open(
            source,
            ReadOnly=True,
            AddToRecentFiles=False,
            ConfirmConversions=False,
        )
        document.Repaginate()
        page_count = int(document.ComputeStatistics(WD_STATISTIC_PAGES))
        page_starts = [
            int(
                document.GoTo(
                    What=WD_GOTO_PAGE,
                    Which=WD_GOTO_ABSOLUTE,
                    Count=page_number,
                ).Start
            )
            for page_number in range(1, page_count + 1)
        ]

        pages: list[dict[str, object]] = []
        for index, start in enumerate(page_starts):
            end = (
                page_starts[index + 1] - 1
                if index + 1 < len(page_starts)
                else int(document.Content.End)
            )
            text = _clean_word_range_text(document.Range(Start=start, End=end).Text)
            pages.append(
                {
                    "page": index + 1,
                    "range_start": start,
                    "range_end": end,
                    "text": text,
                    "signature": make_text_signature(text),
                }
            )

        return {"path": source, "page_count": page_count, "pages": pages}
    finally:
        if document is not None:
            document.Close(False)
        if word is not None:
            word.Quit()
        pythoncom.CoUninitialize()
