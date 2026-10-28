"""Logging configuration for Resume Scanner & Ranker.

Logs filenames, counts and timings only. Never writes extracted text,
resume text or JD text to disk.
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from scanner.config import LOG_DIR, LOG_FILE


def setup_logging() -> None:
    """Configure rotating file handler plus console logging at INFO level."""
    log_dir = Path(LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / LOG_FILE

    file_handler = RotatingFileHandler(
        log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    console_handler = logging.StreamHandler()

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    root.addHandler(file_handler)
    root.addHandler(console_handler)
