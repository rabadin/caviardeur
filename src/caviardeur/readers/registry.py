import logging
from pathlib import Path

try:
    import magic

    _HAS_MAGIC = True
except ImportError:
    _HAS_MAGIC = False

from .base import DocumentContent

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".txt", ".md", ".json", ".xml", ".docx", ".xlsx", ".xls", ".pdf", ".pptx"}

UNSUPPORTED_WITH_WARNING: dict[str, str] = {
    ".doc": (
        "Legacy .doc format is not supported. "
        "Please convert to .docx first (e.g., using LibreOffice: "
        "libreoffice --headless --convert-to docx file.doc)"
    ),
    ".ppt": (
        "Legacy .ppt format is not supported. "
        "Please convert to .pptx first (e.g., using LibreOffice: "
        "libreoffice --headless --convert-to pptx file.ppt)"
    ),
}

# Expected MIME types for each extension. DOCX/XLSX/PPTX are all zip-based,
# so magic reports them as application/zip (or the specific OOXML type).
_EXPECTED_MIMES: dict[str, set[str]] = {
    ".txt": {"text/plain", "text/html", "application/csv"},
    ".md": {"text/plain", "text/html"},
    ".json": {"text/plain", "application/json"},
    ".xml": {"text/plain", "text/xml", "application/xml", "text/html"},
    ".docx": {"application/zip", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    ".xlsx": {"application/zip", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    ".xls": {"application/vnd.ms-excel", "application/x-ole-storage", "application/CDFV2"},
    ".pdf": {"application/pdf"},
    ".pptx": {"application/zip", "application/vnd.openxmlformats-officedocument.presentationml.presentation"},
}


def _check_mime(path: Path, ext: str) -> None:
    """Warn if the file's MIME type is inconsistent with its extension."""
    if not _HAS_MAGIC:
        return

    expected = _EXPECTED_MIMES.get(ext)
    if expected is None:
        return

    try:
        detected = magic.from_file(str(path), mime=True)
    except Exception:
        return

    if detected in expected:
        return

    # Some text-based formats get detected as generic text/plain, that's fine
    if detected == "text/plain" and ext in (".txt", ".md", ".json", ".xml"):
        return

    logger.warning(
        "%s: file extension is '%s' but content looks like '%s' — the file may be misnamed or corrupted",
        path.name,
        ext,
        detected,
    )


def read_document(path: Path) -> DocumentContent | None:
    """Read a document using the appropriate reader based on file extension.

    Returns None if the format is unsupported.
    """
    ext = path.suffix.lower()

    if ext in UNSUPPORTED_WITH_WARNING:
        logger.warning("%s: %s", path.name, UNSUPPORTED_WITH_WARNING[ext])
        return None

    if ext not in SUPPORTED_EXTENSIONS:
        logger.debug("Skipping unsupported file: %s", path.name)
        return None

    _check_mime(path, ext)

    if ext in (".txt", ".md", ".json", ".xml"):
        from .txt_reader import read_txt

        return read_txt(path)
    if ext == ".docx":
        from .docx_reader import read_docx

        return read_docx(path)
    if ext == ".xlsx":
        from .excel_reader import read_xlsx

        return read_xlsx(path)
    if ext == ".xls":
        from .excel_reader import read_xls

        return read_xls(path)
    if ext == ".pdf":
        from .pdf_reader import read_pdf

        return read_pdf(path)
    if ext == ".pptx":
        from .pptx_reader import read_pptx

        return read_pptx(path)
    return None  # unreachable but satisfies type checker


def list_supported_files(path: Path) -> list[Path]:
    """List all supported files in a directory (non-recursive) or return [path] if it's a file."""
    if path.is_file():
        ext = path.suffix.lower()
        if ext in SUPPORTED_EXTENSIONS or ext in UNSUPPORTED_WITH_WARNING:
            return [path]
        return []

    files = []
    for item in sorted(path.iterdir()):
        if item.is_file():
            ext = item.suffix.lower()
            if ext in SUPPORTED_EXTENSIONS or ext in UNSUPPORTED_WITH_WARNING:
                files.append(item)
    return files
