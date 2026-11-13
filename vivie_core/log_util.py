"""Structured logging helpers — no silent except: pass."""

import logging

LOG = logging.getLogger("vivie")


def configure():
    """Ensure Vivie logger is visible when log_config ran."""
    if not LOG.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("[%(name)s] %(levelname)s: %(message)s"))
        LOG.addHandler(handler)
    LOG.setLevel(logging.INFO)
    LOG.propagate = False


def warn(context: str, exc: BaseException | None = None) -> None:
    if exc is not None:
        LOG.warning("%s: %s", context, exc)
    else:
        LOG.warning("%s", context)


def debug(context: str, msg: str = "") -> None:
    if msg:
        LOG.debug("%s %s", context, msg)
    else:
        LOG.debug(context)


def error(context: str, exc: BaseException | None = None, *, exc_info: bool = False) -> None:
    LOG.error("%s: %s", context, exc if exc else "", exc_info=exc_info or exc is not None)
