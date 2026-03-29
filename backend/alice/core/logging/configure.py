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
        "agent",
        "execution",
    }
)
CHANGE_EVENT_ROOTS = frozenset({"change", "memory", "skill", "config"})
TASK_CATEGORY_ROOTS = frozenset({"tasks", *TASK_EVENT_ROOTS})
CHANGE_CATEGORY_ROOTS = frozenset({"changes", *CHANGE_EVENT_ROOTS})


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
    if schema_path.exists():
        return

    payload = {
        "schema_version": "2.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "required_fields": ["ts", "event_type", "level", "source"],
        "log_files": [
            {
                "file": config.system_log_file,
                "event_types": ["system.start", "system.shutdown", "system.health_check", "system.config_reload", "system.alert"],
            },
            {
                "file": config.tasks_log_file,
                "event_types": [
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
                    "model.stream_chunk",
                    "model.stream_completed",
                    "model.tool_decision",
                    "bridge.message_sent",
                    "bridge.message_received",
                    "workflow.state_transition",
                    "executor.command_prepared",
                    "executor.command_result",
                ],
            },
            {
                "file": config.changes_log_file,
                "event_types": [
                    "change.file_saved",
                    "change.memory_updated",
                    "change.skill_loaded",
                    "change.config_mutation",
                    "change.execution_plan",
                ],
            },
        ],
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
    }
    schema_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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
