from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from backend.alice.application.dto.responses import RuntimeEventType


class GatewayErrorCode(str, Enum):
    UNAUTHORIZED = "UNAUTHORIZED"
    INVALID_FRAME = "INVALID_FRAME"
    INVALID_PROTOCOL = "INVALID_PROTOCOL"
    SESSION_REQUIRED = "SESSION_REQUIRED"
    REQUEST_CONFLICT = "REQUEST_CONFLICT"
    REQUEST_NOT_ACTIVE = "REQUEST_NOT_ACTIVE"
    REPLAY_GAP = "REPLAY_GAP"
    INTERNAL_ERROR = "INTERNAL_ERROR"


DROPPABLE_RUNTIME_EVENT_TYPES = {
    RuntimeEventType.REASONING_DELTA.value,
    RuntimeEventType.CONTENT_DELTA.value,
    RuntimeEventType.USAGE_UPDATED.value,
}

TERMINAL_REQUEST_STATES = {"done", "error", "interrupted"}


@dataclass(frozen=True)
class SessionRequestState:
    request_id: str = ""
    state: str = "idle"

    def to_dict(self) -> dict[str, str]:
        return {"request_id": self.request_id, "state": self.state}


@dataclass(frozen=True)
class SessionBindResult:
    session_id: str
    binding_generation: int
    live_from_event_index: int
    replay_frames: list[dict[str, Any]]
    replay_gap: bool
    active_request: SessionRequestState | None


def make_frame(
    frame_type: str,
    *,
    protocol_version: str,
    session_id: str,
    payload: dict[str, Any] | None = None,
    request_id: str | None = None,
    event_index: int | None = None,
) -> dict[str, Any]:
    return {
        "type": frame_type,
        "protocol_version": protocol_version,
        "session_id": session_id,
        "request_id": request_id,
        "event_index": event_index,
        "payload": payload or {},
    }


__all__ = [
    "GatewayErrorCode",
    "DROPPABLE_RUNTIME_EVENT_TYPES",
    "TERMINAL_REQUEST_STATES",
    "SessionRequestState",
    "SessionBindResult",
    "make_frame",
]
