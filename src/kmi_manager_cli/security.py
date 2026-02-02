from __future__ import annotations

import os
import stat
from pathlib import Path


def is_insecure_permissions(path: Path) -> bool:
    if os.name == "nt":
        return False
    try:
        mode = path.stat().st_mode
    except FileNotFoundError:
        return False
    return bool(mode & (stat.S_IRWXG | stat.S_IRWXO))


def warn_if_insecure(path: Path, logger, label: str) -> None:
    if is_insecure_permissions(path):
        try:
            logger.warning(
                "insecure_permissions", extra={"path": str(path), "label": label}
            )
        except Exception:
            logger.warning("insecure_permissions: %s (%s)", path, label)


def _secure_mode(is_dir: bool) -> int:
    return 0o700 if is_dir else 0o600


def ensure_secure_permissions(
    path: Path, logger, label: str, *, is_dir: bool, enforce: bool
) -> None:
    if not enforce or os.name == "nt":
        return
    if not path.exists():
        return
    try:
        current = stat.S_IMODE(path.stat().st_mode)
    except OSError:
        return
    if not (current & (stat.S_IRWXG | stat.S_IRWXO)):
        return
    desired = _secure_mode(is_dir)
    try:
        os.chmod(path, desired)
        logger.info(
            "permissions_hardened",
            extra={"path": str(path), "label": label, "mode": oct(desired)},
        )
    except Exception as exc:
        try:
            logger.warning(
                "permissions_harden_failed",
                extra={"path": str(path), "label": label, "error": str(exc)},
            )
        except Exception:
            logger.warning("permissions_harden_failed: %s (%s)", path, label)
