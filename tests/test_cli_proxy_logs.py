from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from kmi_manager_cli.cli import app


runner = CliRunner()


def test_proxy_logs_no_follow(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "KMI_PROXY_LISTEN=127.0.0.1:9999",
                "KMI_PROXY_BASE_PATH=/kmi-rotor/v1",
                "KMI_UPSTREAM_BASE_URL=https://example.com",
                "KMI_AUTHS_DIR=/tmp",
                f"KMI_STATE_DIR={tmp_path}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("KMI_ENV_PATH", str(env_file))

    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "proxy.out"
    log_file.write_text("line1\nline2\n", encoding="utf-8")

    result = runner.invoke(app, ["proxy-logs", "--no-follow", "--lines", "1"])
    assert result.exit_code == 0
    assert "line2" in result.stdout


def test_proxy_logs_since_app_json(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "KMI_PROXY_LISTEN=127.0.0.1:9999",
                "KMI_PROXY_BASE_PATH=/kmi-rotor/v1",
                "KMI_UPSTREAM_BASE_URL=https://example.com",
                "KMI_AUTHS_DIR=/tmp",
                f"KMI_STATE_DIR={tmp_path}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("KMI_ENV_PATH", str(env_file))

    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "kmi.log"
    log_file.write_text(
        "\n".join(
            [
                '{"ts":"2020-01-01 00:00:00 +0000","level":"INFO","message":"old"}',
                '{"ts":"2099-01-01 00:00:00 +0000","level":"INFO","message":"new"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["proxy-logs", "--app", "--no-follow", "--since", "2030-01-01T00:00:00Z"])
    assert result.exit_code == 0
    assert "new" in result.stdout
    assert "old" not in result.stdout
