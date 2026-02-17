import logging
from pathlib import Path

import fitz  # PyMuPDF

from .base import DocumentContent, TextChunk

logger = logging.getLogger(__name__)


def read_pdf(path: Path) -> DocumentContent:
    """Read a PDF file using PyMuPDF, extracting text blocks per page."""
    doc = fitz.open(str(path))
    chunks: list[TextChunk] = []
    has_text = False

    for page_idx in range(len(doc)):
        page = doc[page_idx]
        blocks = page.get_text("dict")["blocks"]

        for block_idx, block in enumerate(blocks):
            if block["type"] != 0:  # Skip image blocks
                continue
            for line_idx, line in enumerate(block["lines"]):
                for span_idx, span in enumerate(line["spans"]):
                    text = span["text"]
                    if text.strip():
                        has_text = True
                        chunks.append(
                            TextChunk(
                                text=text,
                                location={
                                    "type": "pdf_span",
                                    "page_idx": page_idx,
                                    "block_idx": block_idx,
                                    "line_idx": line_idx,
                                    "span_idx": span_idx,
                                    "bbox": list(span["bbox"]),
                                    "font": span["font"],
                                    "size": span["size"],
                                    "color": span["color"],
                                },
                            )
                        )
                # Add space between lines
                chunks.append(
                    TextChunk(
                        text=" ",
                        location={
                            "type": "pdf_line_separator",
                            "page_idx": page_idx,
                            "block_idx": block_idx,
                            "line_idx": line_idx,
                        },
                    )
                )

        # Add newline between pages
        chunks.append(
            TextChunk(
                text="\n",
                location={"type": "pdf_page_separator", "page_idx": page_idx},
            )
        )

    doc.close()

    if not has_text:
        logger.warning(
            "PDF '%s' contains no extractable text — it may be a scanned document. "
            "Scanned PDFs require OCR (not supported in v1).",
            path.name,
        )

    content = DocumentContent(chunks=chunks, metadata={"source_path": str(path), "format": "pdf"})
    content.assign_offsets()
    return content
