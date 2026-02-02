from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from kmi_manager_cli.cli import app


def _write_auth(path: Path, label: str, key: str) -> None:
    path.write_text(f"KMI_API_KEY={key}\nKMI_KEY_LABEL={label}\n")


def test_cli_rotate_advances_on_tie_in_dry_run(tmp_path: Path, monkeypatch) -> None:
    auths_dir = tmp_path / "auths"
    auths_dir.mkdir()
    _write_auth(auths_dir / "a.env", "a", "sk-a")
    _write_auth(auths_dir / "b.env", "b", "sk-b")

    state_dir = tmp_path / "state"

    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                f"KMI_AUTHS_DIR={auths_dir}",
                f"KMI_STATE_DIR={state_dir}",
                "KMI_DRY_RUN=1",
                "KMI_PROXY_LISTEN=127.0.0.1:9999",
                "KMI_PROXY_BASE_PATH=/kmi-rotor/v1",
                "KMI_UPSTREAM_BASE_URL=https://example.com",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("KMI_ENV_PATH", str(env_file))

    runner = CliRunner()
    result = runner.invoke(app, ["--rotate"])
    assert result.exit_code == 0
    assert "Rotation complete" in result.stdout
    assert "Active key:" in result.stdout
