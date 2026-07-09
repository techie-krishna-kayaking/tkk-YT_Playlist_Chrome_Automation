"""Structured logging configuration built on ``loguru``.

Provides a single :func:`setup_logging` entry point that wires up:

* a colourised console sink,
* a rotating application log (all levels),
* a rotating error log (WARNING and above).

The rest of the framework simply imports ``from loguru import logger``.
"""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

from .config import LoggingConfig

_CONSOLE_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{extra[profile]}</cyan> | "
    "<level>{message}</level>"
)

_FILE_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
    "profile={extra[profile]} | {name}:{function}:{line} | {message}"
)


def setup_logging(cfg: LoggingConfig, base_dir: Path) -> Path:
    """Configure global loguru sinks.

    Args:
        cfg: Logging configuration.
        base_dir: Directory the log ``dir`` is resolved relative to.

    Returns:
        The resolved log directory path.
    """
    log_dir = (base_dir / cfg.dir).resolve()
    log_dir.mkdir(parents=True, exist_ok=True)

    # Ensure every record has a `profile` field so the format string never fails.
    logger.configure(extra={"profile": "-"})
    logger.remove()

    logger.add(
        sys.stderr,
        level=cfg.level,
        format=_CONSOLE_FORMAT,
        colorize=True,
        backtrace=False,
        diagnose=False,
    )

    logger.add(
        log_dir / cfg.app_log,
        level=cfg.level,
        format=_FILE_FORMAT,
        rotation=cfg.rotation,
        retention=cfg.retention,
        encoding="utf-8",
        enqueue=True,
    )

    logger.add(
        log_dir / cfg.error_log,
        level="WARNING",
        format=_FILE_FORMAT,
        rotation=cfg.rotation,
        retention=cfg.retention,
        encoding="utf-8",
        enqueue=True,
    )

    return log_dir


def profile_logger(profile_name: str):
    """Return a logger bound to a specific profile name for contextual logs."""
    return logger.bind(profile=profile_name)
