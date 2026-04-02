"""
统一日志配置入口。

支持：
- 结构化 JSONL 日志
- legacy 文本日志双写
- 通过环境变量回退 legacy 模式
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from ..config.settings import LoggingConfig
from .adapter import normalize_event_type
from .configure_legacy import ColoredFormatter, configure_legacy_logging
from .jsonl_formatter import JSONLFormatter
from .jsonl_logger import JSONLCategoryFileHandler, SizeBasedRotationStrategy


TASK_EVENT_ROOTS = frozenset(
    {
        "task",
        "workflow",
        "iteration",
        "executor",
        "api",
        "model",
        "tool",
        "llm",
        "interrupt",
        "bridge",
        "binding",
        "agent",
        "execution",
    }
)
CHANGE_EVENT_ROOTS = frozenset({"change", "memory", "skill", "config"})
TASK_CATEGORY_ROOTS = frozenset({"tasks", *TASK_EVENT_ROOTS})
CHANGE_CATEGORY_ROOTS = frozenset({"changes", *CHANGE_EVENT_ROOTS})
SCHEMA_VERSION = "2.0.0"


class StructuredCategoryRouterFilter(logging.Filter):
    """将任意日志归类到 system/tasks/changes 三类输出文件。"""

    def filter(self, record: logging.LogRecord) -> bool:
        event_type = normalize_event_type(str(getattr(record, "event_type", "") or ""))
        raw_category = str(getattr(record, "log_category", "") or getattr(record, "category", "") or "")
        normalized = self._resolve_category(event_type, raw_category)
        record.event_type = event_type
        record.log_category = normalized
        if not getattr(record, "source", None):
            record.source = record.name
        return True

    def _resolve_category(self, event_type: str, raw_category: str) -> str:
        event_root = _get_root(event_type)
        if event_root in CHANGE_EVENT_ROOTS:
            return "changes"
        if event_root in TASK_EVENT_ROOTS:
            return "tasks"

        category = _normalize_category(raw_category)
        category_root = _get_root(category)
        if category in {"system", "tasks", "changes"}:
            return category
        if category_root in CHANGE_CATEGORY_ROOTS:
            return "changes"
        if category_root in TASK_CATEGORY_ROOTS:
            return "tasks"
        return "system"


def configure_logging(config: LoggingConfig, enable_colors: Optional[bool] = None) -> None:
    """配置日志系统。"""
    if _should_use_legacy_logging(config):
        configure_legacy_logging(config, enable_colors=enable_colors, clear_handlers=True)
        return

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, config.level.upper(), logging.INFO))
    root_logger.handlers.clear()

    # 桥接模式下 stdout 是 JSON 协议通道，日志只能走 stderr 或文件
    text_formatter = _build_text_formatter(config, enable_colors=enable_colors)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(getattr(logging, config.console_level.upper(), getattr(logging, config.level.upper(), logging.INFO)))
    console_handler.setFormatter(text_formatter)
    root_logger.addHandler(console_handler)

    if config.dual_write_legacy:
        root_logger.addHandler(_build_legacy_file_handler(config, text_formatter))

    logs_dir = Path(config.logs_dir)
    logs_dir.mkdir(parents=True, exist_ok=True)
    _ensure_schema_file(config, logs_dir)

    router_filter = StructuredCategoryRouterFilter()
    jsonl_handler = JSONLCategoryFileHandler(
        log_dir=logs_dir,
        default_category="system",
        category_mapping={
            "system": config.system_log_file,
            "tasks": config.tasks_log_file,
            "changes": config.changes_log_file,
        },
        formatter=JSONLFormatter(
            payload_depth=config.payload_depth,
            redaction_policy=config.redaction_policy,
            capture_thinking=config.capture_thinking,
            capture_api_headers=config.capture_api_headers,
            capture_api_bodies=config.capture_api_bodies,
            capture_tool_io=config.capture_tool_io,
            max_field_length=config.max_field_length,
        ),
        rotation_strategy=SizeBasedRotationStrategy(
            max_bytes=config.max_size_mb * 1024 * 1024,
            backup_count=config.backup_count,
        ),
    )
    jsonl_handler.setLevel(logging.DEBUG)
    jsonl_handler.addFilter(router_filter)
    root_logger.addHandler(jsonl_handler)


def get_logger(name: str) -> logging.Logger:
    """获取标准库 logger。"""
    return logging.getLogger(name)


def _should_use_legacy_logging(config: LoggingConfig) -> bool:
    env_override = os.getenv("USE_LEGACY_LOGGING", "").lower()
    if env_override in {"1", "true", "yes", "on"}:
        return True
    return not config.enable_structured


def _build_text_formatter(
    config: LoggingConfig,
    *,
    enable_colors: Optional[bool] = None,
) -> logging.Formatter:
    use_colors = config.enable_colors if enable_colors is None else enable_colors
    if use_colors:
        return ColoredFormatter(config.format)
    return logging.Formatter(config.format)


def _build_legacy_file_handler(
    config: LoggingConfig,
    formatter: logging.Formatter,
) -> RotatingFileHandler:
    legacy_path = Path(config.file)
    legacy_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        legacy_path,
        maxBytes=config.max_size_mb * 1024 * 1024,
        backupCount=config.backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    return file_handler


def _ensure_schema_file(config: LoggingConfig, logs_dir: Path) -> None:
    schema_path = logs_dir / config.schema_file
    payload = _build_schema_payload(config)
    if schema_path.exists():
        try:
            existing_payload = json.loads(schema_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            existing_payload = None
        else:
            if not _schema_requires_refresh(existing_payload, payload):
                return

    schema_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _build_schema_payload(config: LoggingConfig) -> dict[str, object]:
    system_event_types = [
        "system.start",
        "system.shutdown",
        "system.health_check",
        "system.config_reload",
        "system.alert",
    ]
    task_event_types = [
        "task.created",
        "task.started",
        "task.progress",
        "task.completed",
        "task.failed",
        "api.request",
        "api.response",
        "api.retry",
        "api.error",
        "model.prompt_built",
        "model.stream_started",
        "model.stream_chunk",
        "model.tool_decision",
        "model.stream_completed",
        "binding.tools_bound",
        "binding.capability_mismatch",
        "bridge.message_sent",
        "bridge.message_received",
        "bridge.error",
        "bridge.compatibility_serializer_used",
        "bridge.event_dropped_by_legacy_projection",
        "workflow.state_transition",
        "executor.command_prepared",
        "executor.command_result",
    ]
    change_event_types = [
        "change.file_saved",
        "change.memory_updated",
        "change.skill_loaded",
        "change.config_mutation",
        "change.execution_plan",
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "required_fields": ["ts", "event_type", "level", "source"],
        "log_files": [
            {
                "file": config.system_log_file,
                "event_types": system_event_types,
            },
            {
                "file": config.tasks_log_file,
                "event_types": task_event_types,
            },
            {
                "file": config.changes_log_file,
                "event_types": change_event_types,
            },
        ],
        "event_types": {
            "system.start": {
                "category": "system",
                "description": "Application or subsystem startup event.",
            },
            "system.shutdown": {
                "category": "system",
                "description": "Application or subsystem shutdown event.",
            },
            "system.health_check": {
                "category": "system",
                "description": "Health or readiness probe result.",
            },
            "system.config_reload": {
                "category": "system",
                "description": "Configuration reload or refresh event.",
            },
            "system.alert": {
                "category": "system",
                "description": "Operational alert that needs attention.",
            },
            "task.created": {
                "category": "tasks",
                "description": "A task has been created.",
            },
            "task.started": {
                "category": "tasks",
                "description": "A task has started execution.",
            },
            "task.progress": {
                "category": "tasks",
                "description": "Task progress update.",
            },
            "task.completed": {
                "category": "tasks",
                "description": "A task completed successfully.",
            },
            "task.failed": {
                "category": "tasks",
                "description": "A task failed.",
            },
            "api.request": {
                "category": "tasks",
                "description": "Outbound API request payload metadata.",
            },
            "api.response": {
                "category": "tasks",
                "description": "Inbound API response payload metadata.",
            },
            "api.retry": {
                "category": "tasks",
                "description": "API retry scheduling or attempt event.",
            },
            "api.error": {
                "category": "tasks",
                "description": "API-level failure details.",
            },
            "model.prompt_built": {
                "category": "tasks",
                "description": "Prompt assembly completed.",
            },
            "model.stream_started": {
                "category": "tasks",
                "description": "Model streaming started.",
            },
            "model.stream_chunk": {
                "category": "tasks",
                "description": "Incremental model output chunk.",
            },
            "model.stream_completed": {
                "category": "tasks",
                "description": "Model streaming finished.",
            },
            "model.tool_decision": {
                "category": "tasks",
                "description": "Model selected or declined tool usage.",
            },
            "binding.tools_bound": {
                "category": "tasks",
                "description": "Tool binding snapshot recorded for a provider request.",
            },
            "binding.capability_mismatch": {
                "category": "tasks",
                "description": "Tool binding was rejected because the provider does not support structured tool calling.",
            },
            "bridge.message_sent": {
                "category": "tasks",
                "description": "Frontend-to-backend bridge message.",
            },
            "bridge.message_received": {
                "category": "tasks",
                "description": "Backend-to-frontend bridge message.",
            },
            "bridge.error": {
                "category": "tasks",
                "description": "Bridge execution, transport, or initialization failure details.",
            },
            "bridge.compatibility_serializer_used": {
                "category": "tasks",
                "description": "Legacy compatibility serializer projected an internal response to legacy bridge output.",
            },
            "bridge.event_dropped_by_legacy_projection": {
                "category": "tasks",
                "description": "An internal bridge event was intentionally dropped because legacy projection cannot represent it.",
            },
            "workflow.state_transition": {
                "category": "tasks",
                "description": "Workflow state machine transition.",
            },
            "executor.command_prepared": {
                "category": "tasks",
                "description": "Executor command prepared for dispatch.",
            },
            "executor.command_result": {
                "category": "tasks",
                "description": "Executor command result captured.",
            },
            "change.file_saved": {
                "category": "changes",
                "description": "A file mutation was persisted.",
            },
            "change.memory_updated": {
                "category": "changes",
                "description": "Memory state was updated.",
            },
            "change.skill_loaded": {
                "category": "changes",
                "description": "A skill was loaded or refreshed.",
            },
            "change.config_mutation": {
                "category": "changes",
                "description": "Configuration value was changed.",
            },
            "change.execution_plan": {
                "category": "changes",
                "description": "Execution plan was created or updated.",
            },
        },
        "field_definitions": {
            "ts": {"type": "string", "required": True, "description": "UTC ISO 8601 timestamp."},
            "event_type": {"type": "string", "required": True, "description": "Dot-style event type identifier."},
            "level": {"type": "string", "required": True, "description": "Standard log level."},
            "source": {"type": "string", "required": True, "description": "Logger or module source."},
            "trace_id": {"type": "string", "required": False, "description": "Distributed trace correlation identifier."},
            "request_id": {"type": "string", "required": False, "description": "External request correlation identifier."},
            "task_id": {"type": "string", "required": False, "description": "Task correlation identifier."},
            "session_id": {"type": "string", "required": False, "description": "Session correlation identifier."},
            "span_id": {"type": "string", "required": False, "description": "Span correlation identifier."},
            "component": {"type": "string", "required": False, "description": "Subsystem or component name."},
            "phase": {"type": "string", "required": False, "description": "Lifecycle phase within the component."},
            "timing": {"type": "object", "required": False, "description": "Timing metrics such as elapsed_ms."},
            "payload_kind": {"type": "string", "required": False, "description": "High-level payload family."},
            "context": {"type": "object", "required": False, "description": "Structured contextual metadata."},
            "data": {"type": "object", "required": False, "description": "Structured event payload."},
            "error": {"type": "object", "required": False, "description": "Structured error payload or summary."},
        },
        "recommended_fields": [
            "trace_id",
            "request_id",
            "task_id",
            "session_id",
            "span_id",
            "component",
            "phase",
            "timing",
            "payload_kind",
            "context",
            "data",
            "error",
        ],
        "example_records": {
            config.system_log_file: [
                {
                    "ts": "2026-03-28T09:00:00Z",
                    "event_type": "system.health_check",
                    "level": "INFO",
                    "source": "alice.core.health",
                    "component": "startup.probe",
                    "phase": "ready",
                    "context": {"service": "bridge"},
                    "data": {"status": "ok"},
                }
            ],
            config.tasks_log_file: [
                {
                    "ts": "2026-03-28T09:00:01Z",
                    "event_type": "api.request",
                    "level": "INFO",
                    "source": "alice.domain.llm",
                    "trace_id": "tr-1",
                    "request_id": "req-1",
                    "task_id": "task-9",
                    "session_id": "sess-1",
                    "span_id": "span-1",
                    "component": "openai.client",
                    "phase": "send",
                    "payload_kind": "http",
                    "context": {"provider": "openai"},
                    "data": {
                        "method": "POST",
                        "url": "https://api.openai.com/v1/responses",
                    },
                },
                {
                    "ts": "2026-03-28T09:00:02Z",
                    "event_type": "model.stream_chunk",
                    "level": "DEBUG",
                    "source": "alice.domain.llm",
                    "trace_id": "tr-1",
                    "request_id": "req-1",
                    "task_id": "task-9",
                    "phase": "stream",
                    "timing": {"elapsed_ms": 120},
                    "payload_kind": "model_output",
                    "data": {"chunk": "..."},
                },
            ],
            config.changes_log_file: [
                {
                    "ts": "2026-03-28T09:00:03Z",
                    "event_type": "change.file_saved",
                    "level": "INFO",
                    "source": "alice.infrastructure.bridge",
                    "task_id": "task-9",
                    "component": "workspace.writer",
                    "payload_kind": "file_change",
                    "data": {"path": "prompts/alice.md", "bytes": 2048},
                }
            ],
        },
    }


def _schema_requires_refresh(existing_payload: object, expected_payload: dict[str, object]) -> bool:
    if not isinstance(existing_payload, dict):
        return True
    return _schema_comparable_view(existing_payload) != _schema_comparable_view(expected_payload)


def _schema_comparable_view(payload: dict[str, object]) -> dict[str, object]:
    return {
        key: value
        for key, value in payload.items()
        if key != "generated_at"
    }


def _get_root(value: str) -> str:
    normalized = value.strip().lower().strip(".")
    if not normalized:
        return ""
    return normalized.split(".", 1)[0]


def _normalize_category(value: str) -> str:
    normalized = value.strip().lower().replace("/", ".")
    normalized = normalized.replace("-", ".").replace("_", ".")
    while ".." in normalized:
        normalized = normalized.replace("..", ".")
    return normalized.strip(".")
