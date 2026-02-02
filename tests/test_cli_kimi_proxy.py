from __future__ import annotations

from typer.testing import CliRunner

from kmi_manager_cli.cli import app


runner = CliRunner()


def test_kmi_kimi_injects_proxy_env(monkeypatch, tmp_path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "KMI_PROXY_LISTEN=127.0.0.1:9999",
                "KMI_PROXY_BASE_PATH=/kmi-rotor/v1",
                "KMI_UPSTREAM_BASE_URL=https://example.com",
                "KMI_AUTHS_DIR=/tmp",
                "KMI_STATE_DIR=/tmp",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("KMI_ENV_PATH", str(env_file))
    monkeypatch.setenv("KIMI_BASE_URL", "http://wrong")

    captured = {}

    def fake_run(args, env=None, **_kwargs):
        captured["args"] = args
        captured["env"] = env or {}

        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr("kmi_manager_cli.cli.subprocess.run", fake_run)
    monkeypatch.setattr("kmi_manager_cli.cli.shutil.which", lambda _name: "kimi")

    result = runner.invoke(app, ["kimi", "--final-message-only", "--print", "-c", "test"])

    assert result.exit_code == 0
    assert captured["args"][0] == "kimi"
    assert "--final-message-only" in captured["args"]
    assert captured["env"]["KIMI_BASE_URL"] == "http://127.0.0.1:9999/kmi-rotor/v1"
    assert captured["env"]["KIMI_API_KEY"] == "proxy"
