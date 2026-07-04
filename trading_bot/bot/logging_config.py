"""
Centralized logging configuration.

Logs go to:
  - Console (INFO and above) — concise, human-readable
  - logs/trading_bot.log (DEBUG and above) — full detail, rotated by size

The file log captures every outgoing API request, every raw response,
and any exceptions, so it can be used as an audit trail for order activity.
"""

import logging
import os
from logging.handlers import RotatingFileHandler

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
LOG_FILE = os.path.join(LOG_DIR, "trading_bot.log")

_CONFIGURED = False


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """
    Configure and return the root application logger.

    Safe to call multiple times; only configures handlers once per process.
    """
    global _CONFIGURED

    os.makedirs(LOG_DIR, exist_ok=True)

    logger = logging.getLogger("trading_bot")
    logger.setLevel(logging.DEBUG)

    if _CONFIGURED:
        return logger

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Rotating file handler: full detail, capped at 5MB x 3 backups.
    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # Console handler: only what a user running the CLI needs to see.
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.propagate = False

    _CONFIGURED = True
    return logger
