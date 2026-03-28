"""Integration coverage for the JSONL logging pipeline."""

import json
import logging
from pathlib import Path

import pytest

from backend.alice.core.logging.jsonl_logger import JSONLCategoryFileHandler


REQUIRED_FIELDS = ("ts", "event_type", "level", "source")


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def _assert_required_fields(record: dict[str, object]) -> None:
    for field in REQUIRED_FIELDS:
        assert field in record, f"Missing {field} in {record}"


@pytest.mark.integration
def test_logging_e2e_creates_structured_jsonl_files(tmp_path: Path) -> None:
    """Validate the end-to-end logging pipeline for system, tasks, and changes."""

    log_dir = tmp_path / "logs" / "validation"
    handler = JSONLCategoryFileHandler(log_dir=log_dir)

    logger = logging.getLogger("alice.validation.e2e")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    logger.handlers.clear()
    logger.addHandler(handler)

    task_id = "task-lifecycle-001"

    logger.info(
        "Agent bootstrap",
        extra={"event_type": "system.start", "log_category": "system"},
    )
    logger.info(
        "Task queued",
        extra={
            "event_type": "task.created",
            "log_category": "tasks",
            "task_id": task_id,
            "data": {"intent": "validate logging"},
        },
    )
    logger.info(
        "Task starts exec",
        extra={
            "event_type": "task.started",
            "log_category": "tasks",
            "task_id": task_id,
            "span_id": "span-abc",
        },
    )
    logger.info(
        "Task progress update",
        extra={
            "event_type": "task.progress",
            "log_category": "tasks",
            "task_id": task_id,
            "data": {"phase": "logging"},
        },
    )
    logger.info(
        "Task finished",
        extra={
            "event_type": "task.completed",
            "log_category": "tasks",
            "task_id": task_id,
        },
    )
    logger.info(
        "Prompt file saved",
        extra={
            "event_type": "change.file_saved",
            "log_category": "changes",
            "data": {"file": "prompts/alice.md", "size": 512},
        },
    )

    handler.flush()
    handler.close()
    logger.removeHandler(handler)

    assert log_dir.exists(), "Log directory should be created by the handler"

    system_records = _read_jsonl(log_dir / "system.jsonl")
    assert len(system_records) == 1
    _assert_required_fields(system_records[0])
    assert system_records[0]["event_type"] == "system.start"

    tasks_records = _read_jsonl(log_dir / "tasks.jsonl")
    assert [record["event_type"] for record in tasks_records] == [
        "task.created",
        "task.started",
        "task.progress",
        "task.completed",
    ], "Task lifecycle events should appear in order"
    for record in tasks_records:
        _assert_required_fields(record)
        assert record.get("task_id") == task_id
    assert tasks_records[-1]["event_type"] == "task.completed"

    changes_records = _read_jsonl(log_dir / "changes.jsonl")
    assert len(changes_records) == 1
    _assert_required_fields(changes_records[0])
    assert changes_records[0]["event_type"] == "change.file_saved"
