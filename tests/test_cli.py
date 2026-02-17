from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from caviardeur.cli import main
from caviardeur.detectors.base import DetectedEntity, EntityType


def _mock_detect_all(text, **kwargs):
    entities = []
    for target, etype, conf in [
        ("Jean Dupont", EntityType.PERSON, 0.96),
        ("Nextech Solutions SAS", EntityType.COMPANY, 0.97),
    ]:
        start = 0
        while True:
            idx = text.find(target, start)
            if idx == -1:
                break
            entities.append(
                DetectedEntity(
                    entity_type=etype,
                    text=target,
                    start=idx,
                    end=idx + len(target),
                    confidence=conf,
                    source="mock",
                )
            )
            start = idx + 1
    return entities


@patch("caviardeur.pipeline.detect_all", side_effect=_mock_detect_all)
def test_cli_dry_run(mock_detect, tmp_path: Path):
    txt = tmp_path / "test.txt"
    txt.write_text("Jean Dupont travaille chez Nextech Solutions SAS.", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(main, [str(txt), "--dry-run"])

    assert result.exit_code == 0
    assert "Done" in result.output
    assert not (tmp_path / "output").exists()


@patch("caviardeur.pipeline.detect_all", side_effect=_mock_detect_all)
def test_cli_normal_run(mock_detect, tmp_path: Path):
    txt = tmp_path / "test.txt"
    txt.write_text("Jean Dupont travaille chez Nextech Solutions SAS.", encoding="utf-8")
    output_dir = tmp_path / "out"

    runner = CliRunner()
    result = runner.invoke(main, [str(txt), "-o", str(output_dir)])

    assert result.exit_code == 0
    assert "Done" in result.output
    assert "Mapping saved" in result.output
    assert (output_dir / "test.txt").exists()
    assert (output_dir / "mapping.json").exists()


@patch("caviardeur.pipeline.detect_all", side_effect=_mock_detect_all)
def test_cli_verbose(mock_detect, tmp_path: Path):
    txt = tmp_path / "test.txt"
    txt.write_text("Jean Dupont", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(main, [str(txt), "--dry-run", "-v"])

    assert result.exit_code == 0


@patch("caviardeur.pipeline.detect_all", side_effect=_mock_detect_all)
def test_cli_with_existing_mapping(mock_detect, tmp_path: Path):
    # First run: create mapping
    txt = tmp_path / "test.txt"
    txt.write_text("Jean Dupont", encoding="utf-8")
    output_dir = tmp_path / "out"

    runner = CliRunner()
    runner.invoke(main, [str(txt), "-o", str(output_dir)])

    mapping_path = output_dir / "mapping.json"
    assert mapping_path.exists()

    # Second run: reuse mapping
    txt2 = tmp_path / "test2.txt"
    txt2.write_text("Jean Dupont again", encoding="utf-8")
    output_dir2 = tmp_path / "out2"

    result = runner.invoke(main, [str(txt2), "-o", str(output_dir2), "-m", str(mapping_path)])

    assert result.exit_code == 0
    assert "Loading existing mapping" in result.output


def test_cli_no_supported_files(tmp_path: Path):
    unsupported = tmp_path / "file.xyz"
    unsupported.write_text("nothing", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(main, [str(unsupported)])

    assert result.exit_code == 1
    assert "No supported files found" in result.output


@patch("caviardeur.pipeline.detect_all", return_value=[])
def test_cli_no_entities_no_mapping_saved(mock_detect, tmp_path: Path):
    txt = tmp_path / "test.txt"
    txt.write_text("Texte sans PII.", encoding="utf-8")
    output_dir = tmp_path / "out"

    runner = CliRunner()
    result = runner.invoke(main, [str(txt), "-o", str(output_dir)])

    assert result.exit_code == 0
    assert "Mapping saved" not in result.output
