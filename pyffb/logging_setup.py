"""Logging with a rotating local file and optional console output."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .config import default_log_dir

_CONFIGURED = False


def setup_logging(
    verbose: bool = False,
    *,
    log_dir: Path | None = None,
    console: bool = True,
) -> Path:
    global _CONFIGURED
    directory = Path(log_dir) if log_dir else default_log_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "pyffb.log"
    root = logging.getLogger()
    if _CONFIGURED:
        return path
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler = RotatingFileHandler(
        path,
        maxBytes=1_500_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)
    if console and sys.stderr is not None:
        stream = logging.StreamHandler()
        stream.setLevel(logging.DEBUG if verbose else logging.WARNING)
        stream.setFormatter(formatter)
        root.addHandler(stream)
    logging.captureWarnings(True)
    _CONFIGURED = True
    logging.getLogger(__name__).info("Logging to %s", path)
    return path


def log_path(log_dir: Path | None = None) -> Path:
    return (Path(log_dir) if log_dir else default_log_dir()) / "pyffb.log"
