"""
结构化日志适配器

为现有 logging API 提供渐进式结构化封装。
"""

from __future__ import annotations

import logging
import re
from contextvars import ContextVar, Token
from typing import Any


_LOG_CONTEXT: ContextVar[dict[str, Any]] = ContextVar("alice_log_context", default={})
DEFAULT_EVENT_TYPE = "system.log"
_DOTS_RE = re.compile(r"\.+")
_CANONICAL_TOP_LEVEL_FIELDS = (
    "trace_id",
    "request_id",
    "task_id",
    "session_id",
    "span_id",
    "component",
    "phase",
    "timing",
    "payload_kind",
)


def bind_log_context(**context: Any) -> Token:
    """绑定请求级上下文。"""
    merged = {**_LOG_CONTEXT.get(), **context}
    return _LOG_CONTEXT.set(merged)


def reset_log_context(token: Token) -> None:
    """重置上下文绑定。"""
    _LOG_CONTEXT.reset(token)


def get_log_context() -> dict[str, Any]:
    """获取当前请求级上下文。"""
    return dict(_LOG_CONTEXT.get())


class StructuredLogger:
    """兼容标准 logging 的结构化适配器。"""

    def __init__(
        self,
        name: str,
        *,
        category: str = "system",
        context: dict[str, Any] | None = None,
    ) -> None:
        self.logger = logging.getLogger(name)
        self.category = category
        self.context = context or {}

    def bind(self, **context: Any) -> "StructuredLogger":
        """返回带附加上下文的新 logger。"""
        merged = {**self.context, **context}
        return StructuredLogger(self.logger.name, category=self.category, context=merged)

    def event(
        self,
        event_type: str,
        message: str = "",
        *,
        level: int | str = logging.INFO,
        category: str | None = None,
        data: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        error: Any = None,
        exc_info: Any = None,
        **fields: Any,
    ) -> None:
        """记录结构化事件。"""
        self._log(
            level,
            message or event_type,
            event_type=event_type,
            category=category or self.category,
            data=data,
            context=context,
            error=error,
            exc_info=exc_info,
            **fields,
        )

    def debug(self, message: str, **fields: Any) -> None:
        self._log(logging.DEBUG, message, **fields)

    def info(self, message: str, **fields: Any) -> None:
        self._log(logging.INFO, message, **fields)

    def warning(self, message: str, **fields: Any) -> None:
        self._log(logging.WARNING, message, **fields)

    def error(self, message: str, **fields: Any) -> None:
        self._log(logging.ERROR, message, **fields)

    def critical(self, message: str, **fields: Any) -> None:
        self._log(logging.CRITICAL, message, **fields)

    def _log(
        self,
        level: int | str,
        message: str,
        *,
        event_type: str | None = None,
        category: str | None = None,
        data: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        error: Any = None,
        exc_info: Any = None,
        **fields: Any,
    ) -> None:
        merged_context = {**get_log_context(), **self.context, **(context or {})}
        canonical_fields = _extract_canonical_fields(fields, merged_context)
        extra = {
            "event_type": normalize_event_type(event_type or DEFAULT_EVENT_TYPE),
            "log_category": category or self.category,
            "context": merged_context,
            "data": data or {},
        }
        extra.update(canonical_fields)
        if error is not None:
            extra["error"] = error
        extra.update(fields)
        self.logger.log(level, message, extra=extra, exc_info=exc_info)


def get_structured_logger(
    name: str,
    *,
    category: str = "system",
    context: dict[str, Any] | None = None,
) -> StructuredLogger:
    """获取结构化日志适配器。"""
    return StructuredLogger(name, category=category, context=context)


def normalize_event_type(event_type: str | None) -> str:
    """统一事件名为点号风格，兼容旧的下划线风格。"""
    value = str(event_type or "").strip().lower()
    if not value:
        return DEFAULT_EVENT_TYPE

    value = value.replace("/", ".")
    value = _DOTS_RE.sub(".", value).strip(".")
    if "." not in value:
        value = value.replace("_", ".")
    value = _DOTS_RE.sub(".", value).strip(".")
    if not value:
        return DEFAULT_EVENT_TYPE
    if "." not in value:
        return f"{value}.event"
    return value


def _extract_canonical_fields(
    fields: dict[str, Any],
    merged_context: dict[str, Any],
) -> dict[str, Any]:
    """
    提升并统一核心字段命名。
    - 优先使用显式字段；
    - 其次从 context 提升；
    - 避免在顶层与 context 中重复出现同名字段。
    """
    canonical: dict[str, Any] = {}
    for name in _CANONICAL_TOP_LEVEL_FIELDS:
        value = fields.pop(name, None)
        if value is None and name in merged_context:
            value = merged_context.pop(name)
        if value is not None:
            canonical[name] = value
    return canonical
