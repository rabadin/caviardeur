import logging
from pathlib import Path

import fitz  # PyMuPDF

from ..readers.base import DocumentContent

logger = logging.getLogger(__name__)


def write_pdf(content: DocumentContent, output_path: Path, source_path: Path) -> None:
    """Write pseudonymized content to a PDF using PyMuPDF's redaction API.

    For each modified span: whitewash the original text area, overlay the pseudonym.
    """
    doc = fitz.open(str(source_path))

    # Build lookup of original text -> new text per page/block/line/span
    span_map: dict[tuple[int, int, int, int], dict] = {}
    for chunk in content.chunks:
        loc = chunk.location
        if loc.get("type") != "pdf_span":
            continue
        key = (loc["page_idx"], loc["block_idx"], loc["line_idx"], loc["span_idx"])
        span_map[key] = {
            "new_text": chunk.text,
            "bbox": loc["bbox"],
            "font": loc.get("font", "helv"),
            "size": loc.get("size", 11),
            "color": loc.get("color", 0),
        }

    # Now re-read the original to find which spans actually changed
    for page_idx in range(len(doc)):
        page = doc[page_idx]
        blocks = page.get_text("dict")["blocks"]
        has_redactions = False

        for block_idx, block in enumerate(blocks):
            if block["type"] != 0:
                continue
            for line_idx, line in enumerate(block["lines"]):
                for span_idx, span in enumerate(line["spans"]):
                    key = (page_idx, block_idx, line_idx, span_idx)
                    if key not in span_map:
                        continue

                    info = span_map[key]
                    original_text = span["text"]
                    new_text = info["new_text"]

                    if original_text == new_text:
                        continue

                    # Add redaction annotation to whitewash original text
                    rect = fitz.Rect(info["bbox"])
                    # Use fontsize that fits the box, capped at original size
                    fontsize = min(info["size"], rect.height * 0.85)
                    # PyMuPDF redaction only supports base14 fonts;
                    # the original document font cannot be preserved.
                    page.add_redact_annot(
                        rect,
                        text=new_text,
                        fontname="helv",
                        fontsize=fontsize,
                        align=fitz.TEXT_ALIGN_LEFT,
                        fill=(1, 1, 1),  # White background
                        text_color=(0, 0, 0),  # Black text
                    )
                    has_redactions = True

        if has_redactions:
            page.apply_redactions()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
    doc.close()
