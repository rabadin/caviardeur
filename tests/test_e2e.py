"""End-to-end packaging test. Skipped by default — run with: pytest -m e2e"""

import subprocess
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
ROOT = Path(__file__).parent.parent
BINARY_NAME = "caviardeur-e2e"


@pytest.mark.e2e
def test_packaged_binary():
    binary = ROOT / "dist" / BINARY_NAME

    build = subprocess.run(
        ["mise", "run", "package", "--name", BINARY_NAME],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert build.returncode == 0, f"Build failed:\n{build.stderr}"
    assert binary.exists(), f"Binary not found: {binary}"

    run = subprocess.run(
        [str(binary), str(FIXTURES), "--dry-run"],
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, f"Binary exited {run.returncode}:\n{run.stderr}"
    assert "entities detected" in run.stdout
