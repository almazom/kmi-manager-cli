from __future__ import annotations

from pathlib import Path

__version__ = "0.1.0"

# Allow running from repo root without installation by extending package path to src.
_pkg_root = Path(__file__).resolve().parent
_src_pkg = _pkg_root.parent / "src" / "kmi_manager_cli"
if _src_pkg.exists():
    __path__.append(str(_src_pkg))  # type: ignore[name-defined]
