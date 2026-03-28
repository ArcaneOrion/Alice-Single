"""Simple schema-aware validator for JSONL logs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

REQUIRED_FIELDS = ("ts", "event_type", "level", "source")


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
