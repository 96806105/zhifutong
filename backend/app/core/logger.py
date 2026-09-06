"""智服通 - 日志模块

统一日志入口：控制台 + 文件（按大小轮转）。
日志分级：DEBUG / INFO / WARNING / ERROR。
"""

import logging
import sys
from logging.handlers import RotatingFileHandler

from .config import BASE_DIR

LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def _init_root_logger() -> logging.Logger:
    logger = logging.getLogger("support")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(_FORMAT))

    file_handler = RotatingFileHandler(
        LOG_DIR / "support.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(_FORMAT))

    logger.addHandler(console)
    logger.addHandler(file_handler)
    logger.propagate = False
    return logger


_get_logger = _init_root_logger


def get_logger(name: str = "support") -> logging.Logger:
    """获取带模块名的子 logger。"""
    return logging.getLogger(f"support.{name}")
