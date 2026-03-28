"""
JSONL 日志格式化器。

输出单行 JSON，便于按行采集和后续结构化处理。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Final

DEFAULT_EVENT_TYPE: Final[str] = "log"


class JSONLFormatter(logging.Formatter):
    """将 ``LogRecord`` 格式化为单行 JSON。"""

    def __init__(
        self,
        *,
        default_event_type: str = DEFAULT_EVENT_TYPE,
        default_source: str | None = None,
        include_empty_message: bool = False,
    ) -> None:
        super().__init__()
        self._default_event_type = default_event_type
        self._default_source = default_source
        self._include_empty_message = include_empty_message

    def format(self, record: logging.LogRecord) -> str:
        payload = self.build_payload(record)
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=self._json_default)

    def build_payload(self, record: logging.LogRecord) -> dict[str, Any]:
        """构建结构化日志字典。"""
        payload: dict[str, Any] = {
            "ts": self._format_timestamp(record),
            "event_type": self._read_str(record, "event_type", self._default_event_type),
            "level": record.levelname,
            "source": self._read_str(record, "source", self._default_source or record.name),
        }

        log_category = getattr(record, "log_category", None)
        if log_category is None:
            log_category = getattr(record, "category", None)
        if log_category is not None:
            payload["log_category"] = str(log_category)

        message = record.getMessage()
        if message or self._include_empty_message:
            payload["message"] = message

        for field in ("context", "data", "task_id"):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value

        error = getattr(record, "error", None)
        if error is None and record.exc_info:
            error = self.formatException(record.exc_info)
        elif error is None and record.exc_text:
            error = record.exc_text

        if error is not None:
            payload["error"] = error

        return payload

    @staticmethod
    def _format_timestamp(record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc)
        return timestamp.isoformat().replace("+00:00", "Z")

    @staticmethod
    def _read_str(record: logging.LogRecord, field: str, default: str) -> str:
        value = getattr(record, field, None)
        if value is None:
            return default
        text = str(value).strip()
        return text if text else default

    @staticmethod
    def _json_default(value: Any) -> Any:
        """兜底序列化，避免因为不可 JSON 序列化对象而丢日志。"""
        if isinstance(value, BaseException):
            return repr(value)
        return str(value)
