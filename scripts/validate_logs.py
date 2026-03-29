"""Simple schema-aware validator for JSONL logs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

REQUIRED_FIELDS = ("ts", "event_type", "level", "source")
FULL_PAYLOAD_MODE = "full_payload"
LLM_EVENT_PREFIX = "llm_"
CONTEXT_IDENTIFIERS = ("task_id", "request_id", "trace_id")


def iter_jsonl_records(path: Path) -> Iterable[tuple[int, dict[str, object]] | tuple[int, str]]:
    with path.open("r", encoding="utf-8") as fh:
        for index, line in enumerate(fh, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError as exc:
                error = f"invalid json: {exc.msg} at column {exc.colno}"
                yield index, error
                continue
            yield index, payload


def check_record(record: dict[str, object]) -> list[str]:
    failures: list[str] = []
    for field in REQUIRED_FIELDS:
        if field not in record:
            failures.append(f"missing field {field}")

    context = record.get("context")
    if context is not None and not isinstance(context, dict):
        failures.append("context must be an object")

    data = record.get("data")
    if data is not None and not isinstance(data, dict):
        failures.append("data must be an object")

    error = record.get("error")
    if error is not None and not isinstance(error, (dict, str)):
        failures.append("error must be a string or object")

    event_type = record.get("event_type", "")
    if event_type.startswith(LLM_EVENT_PREFIX):
        if not isinstance(context, dict):
            failures.append("llm event context should be an object containing task_id/request_id/trace_id")
        elif not any(key in context for key in CONTEXT_IDENTIFIERS):
            failures.append("llm event context should contain task_id/request_id/trace_id")

    if (
        isinstance(data, dict)
        and data.get("mode") == FULL_PAYLOAD_MODE
    ):
        payload = data.get("payload")
        if not isinstance(payload, dict):
            failures.append("full payload mode requires a payload object")
            return failures

        metadata = payload.get("metadata")
        length = None
        if not isinstance(metadata, dict):
            failures.append("full payload payload.metadata must be an object")
        else:
            length = metadata.get("length")
            if length is None or not isinstance(length, int):
                failures.append("full payload metadata.length should be an integer")
            else:
                length = int(length)
        content = payload.get("content")
        if isinstance(content, str) and isinstance(length, int):
            if len(content) > length:
                failures.append(
                    "full payload content length exceeds reported metadata.length"
                )
    return failures


def scan_files(paths: list[Path]) -> int:
    errors = 0
    for path in paths:
        if not path.exists():
            print(f"skipping missing file {path}")
            continue
        for line_no, payload in iter_jsonl_records(path):
            if isinstance(payload, str):
                errors += 1
                print(f"{path}:{line_no} parse error: {payload}")
                continue
            missing = check_record(payload)
            if missing:
                errors += 1
                print(f"{path}:{line_no} missing {', '.join(missing)}: {payload}")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate structured JSONL log files.")
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()

    errors = scan_files(args.paths)
    if errors:
        print(f"validation failed: {errors} issue(s) detected", file=sys.stderr)
        raise SystemExit(1)
    print("validation succeeded")


if __name__ == "__main__":
    main()
