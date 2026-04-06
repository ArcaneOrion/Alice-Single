from __future__ import annotations

from collections import deque
from typing import Any


class ReplayBuffer:
    def __init__(self, limit: int) -> None:
        self._limit = max(limit, 1)
        self._frames: deque[dict[str, Any]] = deque(maxlen=self._limit)
        self._next_event_index = 1

    @property
    def next_event_index(self) -> int:
        return self._next_event_index

    def append(self, frame: dict[str, Any]) -> dict[str, Any]:
        stored = dict(frame)
        stored["event_index"] = self._next_event_index
        self._next_event_index += 1
        self._frames.append(stored)
        return stored

    def replay_from(self, resume_from_event_index: int | None) -> tuple[list[dict[str, Any]], bool]:
        if resume_from_event_index is None:
            return list(self._frames), False
        if not self._frames:
            return [], False

        earliest = int(self._frames[0]["event_index"])
        if resume_from_event_index < earliest - 1:
            return self.recovery_frames(), True

        return [
            dict(frame)
            for frame in self._frames
            if int(frame.get("event_index") or 0) > resume_from_event_index
        ], False

    def recovery_frames(self) -> list[dict[str, Any]]:
        snapshot = self.latest_snapshot_frame()
        if snapshot is not None:
            return [snapshot]
        if self._frames:
            return [dict(self._frames[-1])]
        return []

    def latest_snapshot_frame(self) -> dict[str, Any] | None:
        for frame in reversed(self._frames):
            if frame.get("type") == "runtime.event":
                runtime_output = ((frame.get("payload") or {}).get("runtime_output"))
                if runtime_output:
                    return dict(frame)
        for frame in reversed(self._frames):
            if frame.get("type") == "request.completed":
                return dict(frame)
        return None


__all__ = ["ReplayBuffer"]
