import logging
from pathlib import Path

from .base import DocumentContent, TextChunk

logger = logging.getLogger(__name__)


def read_txt(path: Path) -> DocumentContent:
    """Read a plain text file, trying UTF-8 first then latin-1."""
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        logger.warning("%s: not valid UTF-8, falling back to latin-1 encoding", path.name)
        text = path.read_text(encoding="latin-1")

    chunk = TextChunk(text=text, location={"type": "txt"})
    content = DocumentContent(chunks=[chunk], metadata={"source_path": str(path)})
    content.assign_offsets()
    return content
