"""
JSONL 日志写入组件。

提供：
1. 按日志类别路由到不同 ``.jsonl`` 文件的 Handler
2. 可扩展的滚动策略接口（默认按大小滚动实现）
"""

from __future__ import annotations

import logging
import os
import re
from abc import ABC, abstractmethod
from pathlib import Path
from threading import RLock
from typing import Mapping

from .jsonl_formatter import JSONLFormatter

DEFAULT_LOG_CATEGORY = "app"
_INVALID_CATEGORY_CHARS = re.compile(r"[^A-Za-z0-9_.-]+")


class RotationStrategy(ABC):
    """日志文件滚动策略接口。"""

    @abstractmethod
    def rotate_if_needed(self, file_path: Path, incoming_bytes: int) -> None:
        """在写入前判断是否需要滚动。"""


class NoopRotationStrategy(RotationStrategy):
    """不滚动。"""

    def rotate_if_needed(self, file_path: Path, incoming_bytes: int) -> None:
        _ = (file_path, incoming_bytes)


class SizeBasedRotationStrategy(RotationStrategy):
    """按大小滚动，命名规则为 ``<name>.jsonl.1``、``.2``。"""

    def __init__(self, max_bytes: int = 10 * 1024 * 1024, backup_count: int = 5) -> None:
        self.max_bytes = max_bytes
        self.backup_count = backup_count

    def rotate_if_needed(self, file_path: Path, incoming_bytes: int) -> None:
        if self.max_bytes <= 0:
            return

        current_size = 0
        try:
            if file_path.exists():
                current_size = file_path.stat().st_size
        except FileNotFoundError:
            current_size = 0

        if current_size + incoming_bytes <= self.max_bytes:
            return

        self._rotate(file_path)

    def _rotate(self, file_path: Path) -> None:
        if self.backup_count <= 0:
            try:
                file_path.unlink(missing_ok=True)
            except FileNotFoundError:
                pass
            return

        oldest = file_path.with_name(f"{file_path.name}.{self.backup_count}")
        oldest.unlink(missing_ok=True)

        for index in range(self.backup_count - 1, 0, -1):
            src = file_path.with_name(f"{file_path.name}.{index}")
            dst = file_path.with_name(f"{file_path.name}.{index + 1}")
            if src.exists():
                src.replace(dst)

        if file_path.exists():
            file_path.replace(file_path.with_name(f"{file_path.name}.1"))


class JSONLCategoryFileHandler(logging.Handler):
    """
    按类别将日志路由写入不同 ``.jsonl`` 文件。

    类别来源默认读取 ``record.log_category``；如无则回退到 ``default_category``。
    """

    def __init__(
        self,
        log_dir: str | Path,
        *,
        category_field: str = "log_category",
        default_category: str = DEFAULT_LOG_CATEGORY,
        category_mapping: Mapping[str, str] | None = None,
        formatter: logging.Formatter | None = None,
        rotation_strategy: RotationStrategy | None = None,
        encoding: str = "utf-8",
    ) -> None:
        super().__init__()
        self._log_dir = Path(log_dir)
        self._category_field = category_field
        self._default_category = self._normalize_category(default_category)
        self._category_mapping = dict(category_mapping or {})
        self._rotation_strategy = rotation_strategy or NoopRotationStrategy()
        self._encoding = encoding
        self._write_lock = RLock()

        self._log_dir.mkdir(parents=True, exist_ok=True)
        self.setFormatter(formatter or JSONLFormatter())

    @property
    def log_dir(self) -> Path:
        return self._log_dir

    def emit(self, record: logging.LogRecord) -> None:
        try:
            line = self.format(record)
            single_line = line.replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\r")
            payload = (single_line + "\n").encode(self._encoding)
            category = self._resolve_category(record)
            target_path = self.get_category_path(category)

            with self._write_lock:
                self._rotation_strategy.rotate_if_needed(target_path, len(payload))
                self._append_bytes(target_path, payload)
        except Exception:
            self.handleError(record)

    def get_category_path(self, category: str) -> Path:
        """获取类别对应的目标 jsonl 文件路径。"""
        mapped_name = self._category_mapping.get(category, category)
        normalized = self._normalize_category(mapped_name)
        filename = normalized if normalized.endswith(".jsonl") else f"{normalized}.jsonl"
        return self._log_dir / filename

    def _resolve_category(self, record: logging.LogRecord) -> str:
        field_candidates = (self._category_field, "log_category", "category")
        for field in field_candidates:
            raw_value = getattr(record, field, None)
            if raw_value is not None:
                return self._normalize_category(str(raw_value))
        return self._default_category

    def _normalize_category(self, value: str) -> str:
        cleaned = _INVALID_CATEGORY_CHARS.sub("_", value.strip())
        return cleaned if cleaned else self._default_category

    @staticmethod
    def _append_bytes(file_path: Path, payload: bytes) -> None:
        flags = os.O_APPEND | os.O_CREAT | os.O_WRONLY
        fd = os.open(file_path, flags, 0o644)
        try:
            os.write(fd, payload)
        finally:
            os.close(fd)


def create_jsonl_logger(
    name: str,
    *,
    log_dir: str | Path,
    level: int | str = logging.INFO,
    category_field: str = "log_category",
    default_category: str = DEFAULT_LOG_CATEGORY,
    category_mapping: Mapping[str, str] | None = None,
    formatter: logging.Formatter | None = None,
    rotation_strategy: RotationStrategy | None = None,
) -> logging.Logger:
    """
    创建并返回兼容标准 ``logging`` 的 JSONL logger。
    """
    logger = logging.getLogger(name)
    logger.setLevel(_resolve_level(level))

    expected_dir = Path(log_dir)
    has_compatible_handler = any(
        isinstance(handler, JSONLCategoryFileHandler) and handler.log_dir == expected_dir
        for handler in logger.handlers
    )
    if not has_compatible_handler:
        handler = JSONLCategoryFileHandler(
            log_dir=log_dir,
            category_field=category_field,
            default_category=default_category,
            category_mapping=category_mapping,
            formatter=formatter,
            rotation_strategy=rotation_strategy,
        )
        logger.addHandler(handler)
    return logger


def _resolve_level(level: int | str) -> int:
    if isinstance(level, int):
        return level
    return getattr(logging, level.upper(), logging.INFO)
