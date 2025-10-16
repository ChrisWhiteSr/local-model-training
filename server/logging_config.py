from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler

from .settings import get_settings


def configure_logging() -> None:
    s = get_settings()
    os.makedirs(s.LOG_DIR, exist_ok=True)
    level = getattr(logging, s.LOG_LEVEL.upper(), logging.INFO)
    logger = logging.getLogger()
    if logger.handlers:
        return  # already configured
    logger.setLevel(level)

    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s")

    # Console
    ch = logging.StreamHandler()
    ch.setLevel(level)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # File (rotating)
    fh = RotatingFileHandler(s.APP_LOG_PATH, maxBytes=5_000_000, backupCount=3, encoding="utf-8")
    fh.setLevel(level)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

