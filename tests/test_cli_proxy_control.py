from __future__ import annotations

from typer.testing import CliRunner

from kmi_manager_cli.cli import app
from kmi_manager_cli.keys import KeyRecord, Registry
from kmi_manager_cli.state import State


runner = CliRunner()


def test_proxy_stop_uses_config_port(monkeypatch, tmp_path) -> None:
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

    called = {}

    def fake_find(port: int):
        called["port"] = port
        return [1234]

    def fake_terminate(pids, force):
        called["pids"] = pids
        called["force"] = force

    monkeypatch.setattr("kmi_manager_cli.cli._find_listening_pids", fake_find)
    monkeypatch.setattr("kmi_manager_cli.cli._terminate_pids", fake_terminate)

    result = runner.invoke(app, ["proxy-stop", "--yes"])
    assert result.exit_code == 0
    assert called["port"] == 9999
    assert called["pids"] == [1234]
    assert called["force"] is False


def test_proxy_restart_calls_proxy(monkeypatch, tmp_path) -> None:
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

    called = {"proxy": 0}

    def fake_stop(_config, *, yes, force):
        return True

    def fake_proxy():
        called["proxy"] += 1

    monkeypatch.setattr("kmi_manager_cli.cli._stop_proxy", fake_stop)
    monkeypatch.setattr("kmi_manager_cli.cli.proxy", fake_proxy)

    result = runner.invoke(app, ["proxy-restart", "--yes"])
    assert result.exit_code == 0
    assert called["proxy"] == 1


def test_proxy_auto_stops_existing_listener(monkeypatch, tmp_path) -> None:
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

    calls = {"terminate": 0}

    state = {"count": 0}

    def fake_listening(_host: str, _port: int) -> bool:
        state["count"] += 1
        return state["count"] == 1

    def fake_find(_port: int):
        return [4321]

    def fake_terminate(_pids, force=False):
        calls["terminate"] += 1

    monkeypatch.setattr("kmi_manager_cli.cli._proxy_listening", fake_listening)
    monkeypatch.setattr("kmi_manager_cli.cli._find_listening_pids", fake_find)
    monkeypatch.setattr("kmi_manager_cli.cli._terminate_pids", fake_terminate)
    monkeypatch.setattr("kmi_manager_cli.cli.run_proxy", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        "kmi_manager_cli.cli._load_registry_or_exit",
        lambda _config: Registry(keys=[KeyRecord(label="alpha", api_key="sk")]),
    )
    monkeypatch.setattr("kmi_manager_cli.cli.load_state", lambda _config, _registry: State())

    result = runner.invoke(app, ["proxy", "--foreground"])
    assert result.exit_code == 0
    assert calls["terminate"] >= 1
