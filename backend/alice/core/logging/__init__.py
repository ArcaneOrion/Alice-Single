"""
日志系统包

提供结构化日志配置和格式化器
"""

from .adapter import (
    StructuredLogger,
    bind_log_context,
    get_log_context,
    get_structured_logger,
    normalize_event_type,
    reset_log_context,
)
from .configure import configure_logging, get_logger
from .configure_legacy import configure_legacy_logging
from .formatters import (
    JSONFormatter,
    CompactFormatter,
    DetailedFormatter,
    MarkdownFormatter,
)
from .jsonl_formatter import JSONLFormatter, sanitize_log_payload
from .jsonl_logger import (
    JSONLCategoryFileHandler,
    NoopRotationStrategy,
    RotationStrategy,
    SizeBasedRotationStrategy,
    create_jsonl_logger,
)

__all__ = [
    "configure_logging",
    "configure_legacy_logging",
    "get_logger",
    "StructuredLogger",
    "get_structured_logger",
    "normalize_event_type",
    "bind_log_context",
    "get_log_context",
    "reset_log_context",
    "JSONFormatter",
    "JSONLFormatter",
    "sanitize_log_payload",
    "CompactFormatter",
    "DetailedFormatter",
    "MarkdownFormatter",
    "RotationStrategy",
    "NoopRotationStrategy",
    "SizeBasedRotationStrategy",
    "JSONLCategoryFileHandler",
    "create_jsonl_logger",
]
