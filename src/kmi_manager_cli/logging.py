from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from kmi_manager_cli.config import Config
from kmi_manager_cli.security import warn_if_insecure
from kmi_manager_cli.time_utils import format_timestamp, resolve_timezone


class JsonFormatter(logging.Formatter):
    def __init__(self, time_zone: str) -> None:
        super().__init__()
        self._tzinfo = resolve_timezone(time_zone)

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": format_timestamp(datetime.now(timezone.utc), self._tzinfo),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        extras = {k: v for k, v in record.__dict__.items() if k not in logging.LogRecord("", 0, "", 0, "", (), None).__dict__}
        if extras:
            payload.update(extras)
        return json.dumps(payload, ensure_ascii=True)


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
    handler.setFormatter(JsonFormatter(config.time_zone))
    logger.addHandler(handler)
    warn_if_insecure(log_path, logger, "log_file")
    return logger


def log_event(logger: logging.Logger, message: str, **fields: Any) -> None:
    logger.info(message, extra=fields)
