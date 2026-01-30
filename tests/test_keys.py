from __future__ import annotations

from pathlib import Path

from kmi_manager_cli.keys import load_auths_dir, mask_key


def _write_env(path: Path, content: str) -> None:
    path.write_text(content)


def test_load_auths_dir_orders_and_parses(tmp_path: Path) -> None:
    _write_env(
        tmp_path / "b.env",
        """
KMI_API_KEY=sk-test-b
KMI_KEY_LABEL=bravo
KMI_KEY_PRIORITY=5
""".strip(),
    )
    _write_env(
        tmp_path / "a.env",
        """
KMI_API_KEY=sk-test-a
KMI_KEY_LABEL=alpha
KMI_KEY_PRIORITY=5
KMI_KEY_DISABLED=true
""".strip(),
    )
    _write_env(
        tmp_path / "c.env",
        """
KMI_API_KEY=sk-test-c
KMI_KEY_LABEL=charlie
KMI_KEY_PRIORITY=1
""".strip(),
    )

    registry = load_auths_dir(tmp_path)
    labels = [record.label for record in registry.keys]
    assert labels == ["alpha", "bravo", "charlie"]
    assert registry.keys[0].disabled is True


def test_mask_key() -> None:
    assert mask_key("short") == "*****"
    assert mask_key("sk-1234567890") == "sk-1***7890"
