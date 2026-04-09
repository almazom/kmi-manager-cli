from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

from typer.testing import CliRunner

from kmi_manager_cli.cli import app


runner = CliRunner()
REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"


def test_cli_help_includes_required_flags() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for flag in ("--rotate", "--auto_rotate", "--trace", "--all", "--status"):
        assert flag in result.stdout
    assert "Version:" in result.stdout
    assert "Config file: .env" in result.stdout


def test_python_module_cli_registers_commands() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC_ROOT)
    result = subprocess.run(
        [sys.executable, "-m", "kmi_manager_cli.cli", "proxy", "--help"],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0
    assert "Run in background" in result.stdout


def test_python_package_module_entrypoint_help() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC_ROOT)
    result = subprocess.run(
        [sys.executable, "-m", "kmi_manager_cli", "--help"],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0
    assert "--status" in result.stdout
