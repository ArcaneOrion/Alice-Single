"""
日志配置

配置结构化日志系统
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from ..config.settings import LoggingConfig


class ColoredFormatter(logging.Formatter):
    """彩色日志格式化器（开发模式）"""

    # ANSI 颜色代码
    COLORS = {
        'DEBUG': '\033[36m',      # 青色
        'INFO': '\033[32m',       # 绿色
        'WARNING': '\033[33m',    # 黄色
        'ERROR': '\033[31m',      # 红色
        'CRITICAL': '\033[35m',   # 紫色
    }
    RESET = '\033[0m'

    def format(self, record):
        # 添加颜色
        if record.levelname in self.COLORS:
            record.levelname = f"{self.COLORS[record.levelname]}{record.levelname}{self.RESET}"
        return super().format(record)


def configure_logging(config: LoggingConfig, enable_colors: Optional[bool] = None):
    """
    配置日志系统

    Args:
        config: 日志配置
        enable_colors: 是否启用彩色输出（开发模式）
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, config.level.upper(), logging.INFO))

    # 清除现有处理器
    root_logger.handlers.clear()

    # 格式化器
    if enable_colors or config.enable_colors:
        formatter = ColoredFormatter(config.format)
    else:
        formatter = logging.Formatter(config.format)

    # 文件处理器（带滚动）
    log_file = Path(config.file)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=config.max_size_mb * 1024 * 1024,
        backupCount=config.backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, config.level.upper(), logging.INFO))
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)


def get_logger(name: str) -> logging.Logger:
    """
    获取日志记录器

    Args:
        name: 日志记录器名称

    Returns:
        日志记录器实例
    """
    return logging.getLogger(name)


class StructuredLogger:
    """结构化日志记录器（支持 JSON 输出）"""

    def __init__(self, name: str, context: Optional[dict] = None):
        self.logger = logging.getLogger(name)
        self.context = context or {}

    def _log_with_context(self, level: str, message: str, **kwargs):
        """带上下文的日志记录"""
        extra = {**self.context, **kwargs}
        log_func = getattr(self.logger, level.lower())
        log_func(message, extra=extra)

    def debug(self, message: str, **kwargs):
        self._log_with_context('DEBUG', message, **kwargs)

    def info(self, message: str, **kwargs):
        self._log_with_context('INFO', message, **kwargs)

    def warning(self, message: str, **kwargs):
        self._log_with_context('WARNING', message, **kwargs)

    def error(self, message: str, **kwargs):
        self._log_with_context('ERROR', message, **kwargs)

    def critical(self, message: str, **kwargs):
        self._log_with_context('CRITICAL', message, **kwargs)
