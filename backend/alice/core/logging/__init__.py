"""
日志系统包

提供结构化日志配置和格式化器
"""

from .configure import (
    configure_logging,
    get_logger,
    StructuredLogger,
)
from .formatters import (
    JSONFormatter,
    CompactFormatter,
    DetailedFormatter,
    MarkdownFormatter,
)

__all__ = [
    "configure_logging",
    "get_logger",
    "StructuredLogger",
    "JSONFormatter",
    "CompactFormatter",
    "DetailedFormatter",
    "MarkdownFormatter",
]
