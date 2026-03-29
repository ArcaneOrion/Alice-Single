"""
JSONL 日志格式化器。

输出单行 JSON，便于按行采集和后续结构化处理。
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Final

from .adapter import normalize_event_type

DEFAULT_EVENT_TYPE: Final[str] = "system.log"
_REDACTED_TEXT: Final[str] = "[REDACTED]"
_CANONICAL_FIELDS: Final[tuple[str, ...]] = (
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
_MINIMAL_REDACTION_EXACT_KEYS: Final[frozenset[str]] = frozenset(
    {
        "authorization",
        "proxy-authorization",
        "x-api-key",
        "api_key",
        "apikey",
        "access_token",
        "refresh_token",
        "client_secret",
        "password",
        "passwd",
        "pwd",
        "cookie",
        "set-cookie",
        "secret",
    }
)
_MINIMAL_REDACTION_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"^token(\b|_)"),
    re.compile(r".*_token$"),
    re.compile(r".*_secret$"),
)
_STRICT_REDACTION_PARTS: Final[tuple[str, ...]] = (
    "token",
    "secret",
    "password",
    "authorization",
    "cookie",
    "api_key",
    "apikey",
    "private_key",
    "credential",
)
_THINKING_PARTS: Final[tuple[str, ...]] = (
    "thinking",
    "reasoning",
    "chain_of_thought",
    "cot",
)
_API_HEADERS_PARTS: Final[tuple[str, ...]] = (
    "headers",
    "request_headers",
    "response_headers",
)
_API_BODIES_PARTS: Final[tuple[str, ...]] = (
    "body",
    "request_body",
    "response_body",
    "http_body",
)
_TOOL_IO_PARTS: Final[tuple[str, ...]] = (
    "tool_input",
    "tool_output",
    "stdin",
    "stdout",
    "stderr",
    "command_output",
    "command_input",
)


class JSONLFormatter(logging.Formatter):
    """将 ``LogRecord`` 格式化为单行 JSON。"""

    def __init__(
        self,
        *,
        default_event_type: str = DEFAULT_EVENT_TYPE,
        default_source: str | None = None,
        include_empty_message: bool = False,
        payload_depth: int = -1,
        redaction_policy: str = "minimal",
        capture_thinking: bool = True,
        capture_api_headers: bool = True,
        capture_api_bodies: bool = True,
        capture_tool_io: bool = True,
        max_field_length: int = 0,
    ) -> None:
        super().__init__()
        self._default_event_type = normalize_event_type(default_event_type)
        self._default_source = default_source
        self._include_empty_message = include_empty_message
        self._payload_depth = payload_depth
        self._redaction_policy = redaction_policy.strip().lower() or "minimal"
        self._capture_thinking = capture_thinking
        self._capture_api_headers = capture_api_headers
        self._capture_api_bodies = capture_api_bodies
        self._capture_tool_io = capture_tool_io
        self._max_field_length = max_field_length

    def format(self, record: logging.LogRecord) -> str:
        payload = self.build_payload(record)
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=self._json_default)

    def build_payload(self, record: logging.LogRecord) -> dict[str, Any]:
        """构建结构化日志字典。"""
        payload: dict[str, Any] = {
            "ts": self._format_timestamp(record),
            "event_type": normalize_event_type(self._read_str(record, "event_type", self._default_event_type)),
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
            payload["message"] = self._sanitize_field(message, path=("message",))

        for field in _CANONICAL_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = self._sanitize_field(value, path=(field,))

        for field in ("context", "data"):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = self._sanitize_field(value, path=(field,))

        error = getattr(record, "error", None)
        if error is None and record.exc_info:
            error = self.formatException(record.exc_info)
        elif error is None and record.exc_text:
            error = record.exc_text

        if error is not None:
            payload["error"] = self._sanitize_field(error, path=("error",))

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

    def _sanitize_field(self, value: Any, *, path: tuple[str, ...]) -> Any:
        return sanitize_log_payload(
            value,
            path=path,
            redaction_policy=self._redaction_policy,
            payload_depth=self._payload_depth,
            max_field_length=self._max_field_length,
            capture_thinking=self._capture_thinking,
            capture_api_headers=self._capture_api_headers,
            capture_api_bodies=self._capture_api_bodies,
            capture_tool_io=self._capture_tool_io,
        )


def sanitize_log_payload(
    value: Any,
    *,
    path: tuple[str, ...] = (),
    redaction_policy: str = "minimal",
    payload_depth: int = -1,
    max_field_length: int = 0,
    capture_thinking: bool = True,
    capture_api_headers: bool = True,
    capture_api_bodies: bool = True,
    capture_tool_io: bool = True,
) -> Any:
    """
    通用日志 payload 清洗器（核心层复用）。
    默认策略：完整载荷 + 最少脱敏。
    """
    if payload_depth >= 0 and len(path) > payload_depth:
        return "[TRUNCATED_BY_DEPTH]"

    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            key_str = str(key)
            next_path = (*path, key_str)
            if not _should_capture_path(
                next_path,
                capture_thinking=capture_thinking,
                capture_api_headers=capture_api_headers,
                capture_api_bodies=capture_api_bodies,
                capture_tool_io=capture_tool_io,
            ):
                continue
            if _should_redact_key(key_str, redaction_policy):
                result[key_str] = _REDACTED_TEXT
                continue
            result[key_str] = sanitize_log_payload(
                item,
                path=next_path,
                redaction_policy=redaction_policy,
                payload_depth=payload_depth,
                max_field_length=max_field_length,
                capture_thinking=capture_thinking,
                capture_api_headers=capture_api_headers,
                capture_api_bodies=capture_api_bodies,
                capture_tool_io=capture_tool_io,
            )
        return result

    if isinstance(value, list):
        next_path = (*path, "[]")
        return [
            sanitize_log_payload(
                item,
                path=next_path,
                redaction_policy=redaction_policy,
                payload_depth=payload_depth,
                max_field_length=max_field_length,
                capture_thinking=capture_thinking,
                capture_api_headers=capture_api_headers,
                capture_api_bodies=capture_api_bodies,
                capture_tool_io=capture_tool_io,
            )
            for item in value
        ]

    if isinstance(value, tuple):
        next_path = (*path, "()")
        return tuple(
            sanitize_log_payload(
                item,
                path=next_path,
                redaction_policy=redaction_policy,
                payload_depth=payload_depth,
                max_field_length=max_field_length,
                capture_thinking=capture_thinking,
                capture_api_headers=capture_api_headers,
                capture_api_bodies=capture_api_bodies,
                capture_tool_io=capture_tool_io,
            )
            for item in value
        )

    if isinstance(value, str) and max_field_length > 0 and len(value) > max_field_length:
        return f"{value[:max_field_length]}...[TRUNCATED]"

    return value


def _should_capture_path(
    path: tuple[str, ...],
    *,
    capture_thinking: bool,
    capture_api_headers: bool,
    capture_api_bodies: bool,
    capture_tool_io: bool,
) -> bool:
    normalized_path = ".".join(part.strip().lower() for part in path if part)
    if not capture_thinking and any(part in normalized_path for part in _THINKING_PARTS):
        return False
    if not capture_api_headers and any(part in normalized_path for part in _API_HEADERS_PARTS):
        return False
    if not capture_api_bodies and any(part in normalized_path for part in _API_BODIES_PARTS):
        return False
    if not capture_tool_io and any(part in normalized_path for part in _TOOL_IO_PARTS):
        return False
    return True


def _should_redact_key(key: str, policy: str) -> bool:
    normalized_key = key.strip().lower()
    if not normalized_key:
        return False

    policy_name = (policy or "minimal").strip().lower()
    if policy_name == "none":
        return False
    if policy_name == "strict":
        return any(token in normalized_key for token in _STRICT_REDACTION_PARTS)

    if normalized_key in _MINIMAL_REDACTION_EXACT_KEYS:
        return True
    return any(pattern.search(normalized_key) for pattern in _MINIMAL_REDACTION_PATTERNS)
