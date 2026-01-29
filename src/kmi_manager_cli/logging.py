from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from kmi_manager_cli.config import Config


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts_msk": _msk_now(),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        extras = {k: v for k, v in record.__dict__.items() if k not in logging.LogRecord("", 0, "", 0, "", (), None).__dict__}
        if extras:
            payload.update(extras)
        return json.dumps(payload, ensure_ascii=True)


def _msk_now() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S MSK")


def get_logger(config: Config, name: str = "kmi") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    log_path = Path(config.state_dir).expanduser() / "logs" / "kmi.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_path,
        maxBytes=config.log_max_bytes,
        backupCount=config.log_max_backups,
    )
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    return logger


def log_event(logger: logging.Logger, message: str, **fields: Any) -> None:
    logger.info(message, extra=fields)
