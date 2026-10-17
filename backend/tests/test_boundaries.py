"""Architectural boundary enforcement tests."""

import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_module_boundaries() -> None:
    """Verify that backend modules strictly adhere to layer contracts defined in .importlinter."""
    cmd = "lint-imports"
    venv_bin = Path(sys.executable).parent / "lint-imports"
    if venv_bin.exists():
        cmd = str(venv_bin)
    elif shutil.which("lint-imports") is not None:
        cmd = "lint-imports"

    result = subprocess.run(
        [cmd],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Import boundary violation:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
