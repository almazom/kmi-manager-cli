from __future__ import annotations

from rich.console import Console

from kmi_manager_cli.health import HealthInfo
from kmi_manager_cli.keys import KeyRecord, Registry
from kmi_manager_cli.state import KeyState, State
from kmi_manager_cli import ui


def test_render_health_dashboard_no_crash() -> None:
    registry = Registry(keys=[KeyRecord(label="alpha", api_key="sk-test")])
    state = State(keys={"alpha": KeyState(last_used="2026-01-29T11:00:00Z")})
    health = {
        "alpha": HealthInfo(
            status="healthy",
            remaining_percent=50.0,
            used=50,
            limit=100,
            remaining=50,
            reset_hint="resets in 3600s",
            limits=[],
            error_rate=0.0,
        )
    }
    console = Console(record=True, width=120)
    ui.render_health_dashboard(registry, state, health, console=console)
    output = console.export_text()
    assert "Status" in output
