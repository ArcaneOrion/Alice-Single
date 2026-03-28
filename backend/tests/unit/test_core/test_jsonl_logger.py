"""
JSONL formatter / logger 单元测试。
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from threading import Thread
from uuid import uuid4

from backend.alice.core.logging.jsonl_formatter import JSONLFormatter
from backend.alice.core.logging.jsonl_logger import (
    JSONLCategoryFileHandler,
    SizeBasedRotationStrategy,
)


def _build_record(
    message: str,
    *,
    level: int = logging.INFO,
    exc_info: object = None,
    **extra: object,
) -> logging.LogRecord:
    record = logging.LogRecord(
        name="alice.test",
        level=level,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=(),
        exc_info=exc_info,
    )
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    content = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in content if line.strip()]


def _new_test_logger() -> logging.Logger:
    logger = logging.getLogger(f"alice.test.jsonl.{uuid4().hex}")
    logger.handlers.clear()
    logger.propagate = False
    logger.setLevel(logging.DEBUG)
    return logger


def test_formatter_outputs_required_and_structured_fields() -> None:
    formatter = JSONLFormatter()
    record = _build_record(
        "task started",
        event_type="task.started",
        log_category="tasks",
        source="core.runner",
        context={"worker": "core"},
        data={"step": 1},
        task_id="task-001",
    )

    line = formatter.format(record)

    assert "\n" not in line
    payload = json.loads(line)
    assert payload["event_type"] == "task.started"
    assert payload["level"] == "INFO"
    assert payload["source"] == "core.runner"
    assert payload["message"] == "task started"
    assert payload["context"] == {"worker": "core"}
    assert payload["data"] == {"step": 1}
    assert payload["task_id"] == "task-001"
    assert payload["log_category"] == "tasks"

    ts = str(payload["ts"]).replace("Z", "+00:00")
    assert datetime.fromisoformat(ts).tzinfo is not None


def test_formatter_captures_error_from_exc_info() -> None:
    formatter = JSONLFormatter()
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        record = _build_record(
            "failed",
            level=logging.ERROR,
            exc_info=sys.exc_info(),
            event_type="task.failed",
            log_category="tasks",
        )

    payload = json.loads(formatter.format(record))
    assert payload["event_type"] == "task.failed"
    assert "error" in payload
    assert "RuntimeError" in str(payload["error"])


def test_handler_routes_records_by_log_category_and_initializes_directory(tmp_path: Path) -> None:
    log_dir = tmp_path / "nested" / "logs"
    handler = JSONLCategoryFileHandler(log_dir=log_dir)
    logger = _new_test_logger()
    logger.addHandler(handler)

    logger.info(
        "system message",
        extra={"event_type": "system.tick", "log_category": "system", "context": {"node": "A"}},
    )
    logger.info(
        "task message",
        extra={"event_type": "task.progress", "log_category": "tasks", "task_id": "task-42"},
    )

    handler.close()
    logger.removeHandler(handler)

    assert log_dir.exists()
    system_records = _read_jsonl(log_dir / "system.jsonl")
    task_records = _read_jsonl(log_dir / "tasks.jsonl")

    assert len(system_records) == 1
    assert system_records[0]["event_type"] == "system.tick"
    assert system_records[0]["context"] == {"node": "A"}
    assert len(task_records) == 1
    assert task_records[0]["task_id"] == "task-42"


def test_handler_size_rotation_creates_backup_file(tmp_path: Path) -> None:
    log_dir = tmp_path / "logs"
    strategy = SizeBasedRotationStrategy(max_bytes=1, backup_count=2)
    handler = JSONLCategoryFileHandler(log_dir=log_dir, rotation_strategy=strategy)
    logger = _new_test_logger()
    logger.addHandler(handler)

    logger.info("first", extra={"event_type": "test.event", "log_category": "changes"})
    logger.info("second", extra={"event_type": "test.event", "log_category": "changes"})

    handler.close()
    logger.removeHandler(handler)

    current_file = log_dir / "changes.jsonl"
    backup_file = log_dir / "changes.jsonl.1"
    assert current_file.exists()
    assert backup_file.exists()
    assert len(_read_jsonl(current_file)) == 1
    assert len(_read_jsonl(backup_file)) == 1


def test_handler_thread_safe_append_without_line_loss(tmp_path: Path) -> None:
    log_dir = tmp_path / "logs"
    handler = JSONLCategoryFileHandler(log_dir=log_dir)
    logger = _new_test_logger()
    logger.addHandler(handler)

    thread_count = 5
    logs_per_thread = 25

    def worker(thread_id: int) -> None:
        for index in range(logs_per_thread):
            logger.info(
                "parallel write",
                extra={
                    "event_type": "thread.write",
                    "log_category": "tasks",
                    "data": {"thread": thread_id, "index": index},
                },
            )

    threads = [Thread(target=worker, args=(index,)) for index in range(thread_count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    handler.close()
    logger.removeHandler(handler)

    records = _read_jsonl(log_dir / "tasks.jsonl")
    assert len(records) == thread_count * logs_per_thread

