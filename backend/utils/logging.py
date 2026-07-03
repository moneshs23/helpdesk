"""Centralized logging configuration using loguru."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from loguru import logger

from backend.config import ROOT_DIR, settings

_CONFIGURED = False


class _InterceptHandler(logging.Handler):
    """Route standard logging records (uvicorn, sqlalchemy, ...) through loguru."""

    def emit(self, record: logging.LogRecord) -> None:  # pragma: no cover - glue code
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def configure_logging() -> None:
    """Configure loguru sinks (console + rotating file). Idempotent."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    logger.remove()
    logger.add(
        sys.stderr,
        level=settings.log_level,
        colorize=True,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan> - <level>{message}</level>"
        ),
    )
    log_dir = Path(ROOT_DIR) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.add(
        log_dir / "app.log",
        level=settings.log_level,
        rotation="10 MB",
        retention="14 days",
        compression="zip",
        enqueue=True,
        backtrace=False,
        diagnose=False,
    )

    # Intercept stdlib logging.
    logging.basicConfig(handlers=[_InterceptHandler()], level=0, force=True)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "sqlalchemy.engine"):
        logging.getLogger(name).handlers = [_InterceptHandler()]

    _CONFIGURED = True


__all__ = ["logger", "configure_logging"]
