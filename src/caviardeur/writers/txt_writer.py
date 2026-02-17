from pathlib import Path

from ..readers.base import DocumentContent


def write_txt(content: DocumentContent, output_path: Path, source_path: Path | None = None) -> None:
    """Write pseudonymized text content to a plain text file (.txt, .md, .json, .xml)."""
    text = "".join(chunk.text for chunk in content.chunks)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")
