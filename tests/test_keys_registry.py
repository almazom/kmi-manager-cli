from __future__ import annotations

from pathlib import Path

from kmi_manager_cli.keys import KeyRecord, Registry, iter_masked_keys, load_auths_dir


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def test_registry_active_key_clamps_index() -> None:
    registry = Registry(keys=[KeyRecord(label="a", api_key="sk-a")], active_index=5)
    assert registry.active_key is not None
    assert registry.active_key.label == "a"


def test_registry_find_by_label() -> None:
    registry = Registry(
        keys=[
            KeyRecord(label="a", api_key="sk-a"),
            KeyRecord(label="b", api_key="sk-b"),
        ]
    )
    assert registry.find_by_label("b").api_key == "sk-b"
    assert registry.find_by_label("missing") is None


def test_iter_masked_keys() -> None:
    records = [KeyRecord(label="alpha", api_key="sk-1234567890")]
    masked = iter_masked_keys(records)
    assert masked == [("alpha", "sk-1***7890")]


def test_mask_key_empty() -> None:
    assert iter_masked_keys([KeyRecord(label="a", api_key="")]) == [("a", "")]


def test_registry_active_key_none_when_empty() -> None:
    registry = Registry(keys=[], active_index=0)
    assert registry.active_key is None


def test_load_auths_dir_deduplicates_api_keys(tmp_path: Path) -> None:
    auths_dir = tmp_path / "auths"
    auths_dir.mkdir()
    _write(
        auths_dir / "a.env",
        "\n".join(
            [
                "KMI_API_KEY=sk-dup",
                "KMI_KEY_LABEL=alpha",
                "KMI_UPSTREAM_BASE_URL=https://example.com",
            ]
        )
        + "\n",
    )
    _write(
        auths_dir / "b.env",
        "\n".join(
            [
                "KMI_API_KEY=sk-dup",
                "KMI_KEY_LABEL=bravo",
                "KMI_UPSTREAM_BASE_URL=https://example.com",
            ]
        )
        + "\n",
    )

    registry = load_auths_dir(auths_dir, default_base_url="https://example.com")
    assert len(registry.keys) == 1
    assert registry.keys[0].api_key == "sk-dup"


def test_load_auths_dir_missing_dir(tmp_path: Path) -> None:
    registry = load_auths_dir(tmp_path / "missing")
    assert registry.keys == []


def test_load_auths_dir_invalid_priority(tmp_path: Path) -> None:
    auths_dir = tmp_path / "auths"
    auths_dir.mkdir()
    _write(
        auths_dir / "a.env",
        "\n".join(
            [
                "KMI_API_KEY=sk-alpha",
                "KMI_KEY_LABEL=alpha",
                "KMI_KEY_PRIORITY=bad",
                "KMI_UPSTREAM_BASE_URL=https://example.com",
            ]
        )
        + "\n",
    )
    registry = load_auths_dir(auths_dir, default_base_url="https://example.com")
    assert registry.keys[0].priority == 0
