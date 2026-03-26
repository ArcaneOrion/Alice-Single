"""
自定义日志格式化器

提供各种日志格式化器
"""

import logging
import json
from datetime import datetime
from typing import Any


class JSONFormatter(logging.Formatter):
    """JSON 格式化器（用于日志聚合）"""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }

        # 添加异常信息
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        # 添加额外字段
        if hasattr(record, 'extra'):
            log_data.update(record.extra)

        return json.dumps(log_data)


class CompactFormatter(logging.Formatter):
    """紧凑格式化器"""

    def __init__(self):
        super().__init__('%(levelname)s %(name)s: %(message)s')


class DetailedFormatter(logging.Formatter):
    """详细格式化器"""
    default_format = (
        '%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s'
    )

    def __init__(self, fmt: str = None):
        super().__init__(fmt or self.default_format)


class MarkdownFormatter(logging.Formatter):
    """Markdown 格式化器（用于生成日志报告）"""

    def formatException(self, exc_info) -> str:
        """格式化异常为 Markdown 代码块"""
        exception_text = super().formatException(exc_info)
        return f"\n```\n{exception_text}\n```\n"

    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()
        level_emoji = {
            'DEBUG': '🔍',
            'INFO': 'ℹ️',
            'WARNING': '⚠️',
            'ERROR': '❌',
            'CRITICAL': '🚨',
        }.get(record.levelname, '')

        return f"{level_emoji} **{record.levelname}** `{record.name}`: {message}"
