from pathlib import Path
from unittest.mock import patch

from caviardeur.readers.registry import (
    _check_mime,
    list_supported_files,
    read_document,
)

# --- list_supported_files ---


def test_list_supported_single_file(tmp_path: Path):
    txt = tmp_path / "doc.txt"
    txt.write_text("hello", encoding="utf-8")
    assert list_supported_files(txt) == [txt]


def test_list_supported_single_unsupported_with_warning(tmp_path: Path):
    doc = tmp_path / "old.doc"
    doc.write_text("legacy", encoding="utf-8")
    assert list_supported_files(doc) == [doc]


def test_list_supported_single_unknown_extension(tmp_path: Path):
    xyz = tmp_path / "data.xyz"
    xyz.write_text("??", encoding="utf-8")
    assert list_supported_files(xyz) == []


def test_list_supported_directory(tmp_path: Path):
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    (tmp_path / "b.md").write_text("b", encoding="utf-8")
    (tmp_path / "c.xyz").write_text("c", encoding="utf-8")
    (tmp_path / "d.doc").write_text("d", encoding="utf-8")

    result = list_supported_files(tmp_path)
    names = [f.name for f in result]
    assert "a.txt" in names
    assert "b.md" in names
    assert "d.doc" in names
    assert "c.xyz" not in names


def test_list_supported_directory_sorted(tmp_path: Path):
    (tmp_path / "z.txt").write_text("z", encoding="utf-8")
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")

    result = list_supported_files(tmp_path)
    assert result[0].name == "a.txt"
    assert result[1].name == "z.txt"


# --- read_document ---


def test_read_document_unsupported_doc(tmp_path: Path):
    doc = tmp_path / "legacy.doc"
    doc.write_text("legacy content", encoding="utf-8")
    assert read_document(doc) is None


def test_read_document_unsupported_ppt(tmp_path: Path):
    ppt = tmp_path / "legacy.ppt"
    ppt.write_text("legacy content", encoding="utf-8")
    assert read_document(ppt) is None


def test_read_document_unknown_extension(tmp_path: Path):
    xyz = tmp_path / "data.xyz"
    xyz.write_text("hello", encoding="utf-8")
    assert read_document(xyz) is None


def test_read_document_txt(tmp_path: Path):
    txt = tmp_path / "hello.txt"
    txt.write_text("Bonjour le monde", encoding="utf-8")
    content = read_document(txt)
    assert content is not None
    assert "Bonjour le monde" in content.raw_text


# --- _check_mime ---


@patch("caviardeur.readers.registry._HAS_MAGIC", False)
def test_check_mime_no_magic(tmp_path: Path):
    # Should return without error when magic is not available
    txt = tmp_path / "test.txt"
    txt.write_text("hello", encoding="utf-8")
    _check_mime(txt, ".txt")


@patch("caviardeur.readers.registry._HAS_MAGIC", True)
@patch("caviardeur.readers.registry.magic")
def test_check_mime_matching(mock_magic, tmp_path: Path):
    mock_magic.from_file.return_value = "text/plain"
    txt = tmp_path / "test.txt"
    txt.write_text("hello", encoding="utf-8")
    _check_mime(txt, ".txt")  # Should not warn


@patch("caviardeur.readers.registry._HAS_MAGIC", True)
@patch("caviardeur.readers.registry.magic")
def test_check_mime_mismatch_warns(mock_magic, tmp_path: Path, caplog):
    mock_magic.from_file.return_value = "application/pdf"
    txt = tmp_path / "fake.txt"
    txt.write_text("not really text", encoding="utf-8")

    import logging

    with caplog.at_level(logging.WARNING):
        _check_mime(txt, ".txt")

    assert "may be misnamed or corrupted" in caplog.text


@patch("caviardeur.readers.registry._HAS_MAGIC", True)
@patch("caviardeur.readers.registry.magic")
def test_check_mime_exception_handled(mock_magic, tmp_path: Path):
    mock_magic.from_file.side_effect = OSError("magic failed")
    txt = tmp_path / "test.txt"
    txt.write_text("hello", encoding="utf-8")
    _check_mime(txt, ".txt")  # Should not raise


def test_check_mime_unknown_extension(tmp_path: Path):
    xyz = tmp_path / "data.xyz"
    xyz.write_text("hello", encoding="utf-8")
    _check_mime(xyz, ".xyz")  # No expected MIME, should return silently
