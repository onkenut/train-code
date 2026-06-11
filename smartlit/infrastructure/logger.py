import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from ..config import get_config


def setup_logger(name: str = "smartlit", debug: bool = False) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    level = logging.DEBUG if debug else logging.INFO
    logger.setLevel(level)

    fmt = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(fmt)
    logger.addHandler(console_handler)

    log_dir = get_config().log_dir
    log_file = log_dir / "smartlit.log"
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    return logger


def get_logger(name: str = "smartlit") -> logging.Logger:
    return logging.getLogger(name)
