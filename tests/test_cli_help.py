from __future__ import annotations

from typer.testing import CliRunner

from kmi_manager_cli.cli import app


runner = CliRunner()


def test_cli_help_includes_required_flags() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for flag in ("--rotate", "--auto_rotate", "--trace", "--all", "--status"):
        assert flag in result.stdout
    assert "Version:" in result.stdout
    assert "Config file: .env" in result.stdout
