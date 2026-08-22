from __future__ import annotations

import hashlib
import re
from pathlib import Path

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from .baseline import LOGICAL_PAGE_PATTERN


PLUGIN_PAGE_PATTERN = re.compile(r"^第\s*(\d+)\s*页(?:\s*PPT)?$")


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hidden_marker_paragraph(text: str):
    paragraph = OxmlElement("w:p")
    properties = OxmlElement("w:pPr")
    spacing = OxmlElement("w:spacing")
    spacing.set(qn("w:before"), "0")
    spacing.set(qn("w:after"), "0")
    spacing.set(qn("w:line"), "1")
    spacing.set(qn("w:lineRule"), "exact")
    properties.append(spacing)

    paragraph_mark_properties = OxmlElement("w:rPr")
    paragraph_mark_properties.append(OxmlElement("w:vanish"))
    properties.append(paragraph_mark_properties)
    paragraph.append(properties)

    run = OxmlElement("w:r")
    run_properties = OxmlElement("w:rPr")
    run_properties.append(OxmlElement("w:vanish"))
    size = OxmlElement("w:sz")
    size.set(qn("w:val"), "2")
    run_properties.append(size)
    run.append(run_properties)
    text_node = OxmlElement("w:t")
    text_node.text = text
    run.append(text_node)
    paragraph.append(run)
    return paragraph


def inject_hidden_plugin_markers(
    source_docx: str | Path, output_docx: str | Path
) -> dict[str, object]:
    source = Path(source_docx)
    output = Path(output_docx)
    document = Document(source)
    inserted = insert_hidden_markers_in_document(document)

    output.parent.mkdir(parents=True, exist_ok=True)
    document.save(output)
    return {
        "source": str(source.resolve()),
        "output": str(output.resolve()),
        "source_sha256": _hash(source),
        "output_sha256": _hash(output),
        "inserted_markers": len(inserted),
        "pages": inserted,
    }


def insert_hidden_markers_in_document(document: Document) -> list[int]:
    inserted: list[int] = []

    for paragraph in list(document.paragraphs):
        visible_text = paragraph.text.strip()
        logical_match = LOGICAL_PAGE_PATTERN.fullmatch(visible_text)
        if logical_match is None or paragraph.style.style_id != "PaginationLabel":
            continue
        if PLUGIN_PAGE_PATTERN.fullmatch(visible_text):
            continue
        page_number = int(logical_match.group(1))
        paragraph._p.addprevious(
            _hidden_marker_paragraph(f"第{page_number}页")
        )
        inserted.append(page_number)

    return inserted
