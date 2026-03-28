"""
Legacy 日志配置

保留文本日志初始化逻辑，供结构化日志回退使用。
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from ..config.settings import LoggingConfig


class ColoredFormatter(logging.Formatter):
    """彩色日志格式化器（开发模式）"""

    COLORS = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[35m",
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        original_levelname = record.levelname
        if original_levelname in self.COLORS:
            record.levelname = (
                f"{self.COLORS[original_levelname]}{original_levelname}{self.RESET}"
            )
        try:
            return super().format(record)
        finally:
            record.levelname = original_levelname


def configure_legacy_logging(
    config: LoggingConfig,
    enable_colors: Optional[bool] = None,
    clear_handlers: bool = True,
) -> None:
    """配置 legacy 文本日志系统。"""
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, config.level.upper(), logging.INFO))

    if clear_handlers:
        root_logger.handlers.clear()

    if enable_colors or config.enable_colors:
        formatter: logging.Formatter = ColoredFormatter(config.format)
    else:
        formatter = logging.Formatter(config.format)

    log_file = Path(config.file)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=config.max_size_mb * 1024 * 1024,
        backupCount=config.backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, config.level.upper(), logging.INFO))
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

