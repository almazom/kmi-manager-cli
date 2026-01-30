from __future__ import annotations

import sys
from pathlib import Path

# Ensure src/ is importable when running from repo root without installation.
_ROOT = Path(__file__).resolve().parent
_SRC = _ROOT / "src"
if _SRC.exists():
    src_str = str(_SRC)
    if src_str not in sys.path:
        sys.path.insert(0, src_str)
