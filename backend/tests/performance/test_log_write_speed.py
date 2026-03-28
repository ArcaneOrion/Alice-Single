"""Performance-focused placeholder for structured logging write throughput."""

import json
import logging
import time
from pathlib import Path

import pytest

from backend.alice.core.logging.jsonl_logger import JSONLCategoryFileHandler


REQUIRED_FIELDS = ("ts", "event_type", "level", "source")


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _assert_required_fields(record: dict[str, object]) -> None:
    for field in REQUIRED_FIELDS:
        assert field in record, f"Missing {field}"


@pytest.mark.performance
def test_log_write_throughput(tmp_path: Path) -> None:
    """Benchmark JSONL handler throughput while verifying a simple task lifecycle log stream."""

    logger = logging.getLogger("alice.validation.perf")
    logger.handlers.clear()
    logger.propagate = False
    logger.setLevel(logging.INFO)

    handler = JSONLCategoryFileHandler(log_dir=tmp_path)
    logger.addHandler(handler)

    total_messages = 1024
    start = time.perf_counter()
    for index in range(total_messages):
        logger.info(
            "perf log",
            extra={
                "event_type": "task.progress",
                "log_category": "tasks",
                "task_id": f"perf-{index // 4}",
                "data": {"step": index},
            },
        )
    elapsed = time.perf_counter() - start

    handler.flush()
    handler.close()
    logger.removeHandler(handler)

    assert elapsed > 0, "Elapsed time must be measurable"

    throughput = total_messages / elapsed
    assert throughput > 1000, f"Expected throughput > 1000 events/sec, got {throughput:.2f}"

    tasks_file = tmp_path / "tasks.jsonl"
    records = _read_jsonl(tasks_file)
    assert len(records) == total_messages
    for record in records:
        _assert_required_fields(record)
        assert record.get("task_id") is not None
