import logging
import os
import sys

from loguru import logger

_LOG_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> "
    "<dim>|</dim> <level>{level: <7}</level> "
    "<dim>|</dim> <cyan>{extra[name]}</cyan>"
    "<dim>:{function}:{line}</dim> "
    "<dim>-</dim> <level>{message}</level>"
)

_configured = False


class _LoguruInterceptHandler(logging.Handler):
    """Forward records from stdlib logging into loguru, preserving level
    and message."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        logger.bind(name=record.name).opt(
            depth=6, exception=record.exc_info
        ).log(level, record.getMessage())


def _bridge_to_loguru(name: str, level: int) -> None:
    """Route a specific stdlib logger through loguru."""
    lg = logging.getLogger(name)
    lg.handlers = [_LoguruInterceptHandler()]
    lg.setLevel(level)
    lg.propagate = False


def _configure() -> None:
    global _configured
    if _configured:
        return

    logger.remove()
    logger.add(
        sys.stderr,
        format=_LOG_FORMAT,
        level=os.getenv("ARPELS_LOG_LEVEL", "INFO"),
        colorize=True,
        backtrace=True,
        diagnose=True,
        enqueue=True,
    )

    # silence INFO/WARNING from third-party libraries that route through
    # the stdlib logging module.
    logging.getLogger().setLevel(logging.ERROR)
    for name in list(logging.Logger.manager.loggerDict.keys()):
        logging.getLogger(name).setLevel(logging.ERROR)

    # but bridge specific libs we want to see into loguru
    _bridge_to_loguru("Lark", logging.INFO)

    _configured = True


def get_logger(name: str):
    _configure()
    return logger.bind(name=name)
