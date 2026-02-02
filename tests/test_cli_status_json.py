from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from kmi_manager_cli.cli import app


runner = CliRunner()


def test_status_json_output(tmp_path: Path, monkeypatch) -> None:
    auths_dir = tmp_path / "auths"
    auths_dir.mkdir()
    (auths_dir / "alpha.env").write_text(
        "KMI_API_KEY=sk-test\nKMI_KEY_LABEL=alpha\n",
        encoding="utf-8",
    )
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "KMI_PROXY_LISTEN=127.0.0.1:9999",
                "KMI_PROXY_BASE_PATH=/kmi-rotor/v1",
                "KMI_UPSTREAM_BASE_URL=https://example.com",
                f"KMI_AUTHS_DIR={auths_dir}",
                f"KMI_STATE_DIR={tmp_path}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("KMI_ENV_PATH", str(env_file))

    result = runner.invoke(app, ["status", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["proxy"]["host"] == "127.0.0.1"
    assert payload["keys"]["total"] == 1
    assert payload["active_key"] == "alpha"
    assert "last_health_refresh" in payload
