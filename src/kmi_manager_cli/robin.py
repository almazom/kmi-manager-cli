from __future__ import annotations

import sys

from kmi_manager_cli.cli import app


def main() -> None:
    # Always route through the existing "kmi kimi" wrapper so proxy env is injected.
    app(args=["kimi", *sys.argv[1:]], prog_name="kimi_robin")
