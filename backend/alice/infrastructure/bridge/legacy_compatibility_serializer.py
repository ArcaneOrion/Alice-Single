"""Compatibility serializer for the frozen legacy bridge protocol."""

from __future__ import annotations

from typing import Any

from backend.alice.infrastructure.bridge.canonical_bridge import (
    CanonicalBridgeEvent,
    CanonicalEventType,
)


def serialize_status_message(status: str) -> dict[str, Any]:
    return {"type": "status", "content": _normalize_legacy_status(status)}


def serialize_thinking_message(content: str) -> dict[str, Any]:
    return {"type": "thinking", "content": content}


def serialize_content_message(content: str) -> dict[str, Any]:
    return {"type": "content", "content": content}


def serialize_tokens_message(total: int, prompt: int, completion: int) -> dict[str, Any]:
    return {
        "type": "tokens",
        "total": total,
        "prompt": prompt,
        "completion": completion,
    }


def serialize_error_message(content: str, code: str = "") -> dict[str, Any]:
    result = {"type": "error", "content": content}
    if code:
        result["code"] = code
    return result


def _normalize_legacy_status(status: str) -> str:
    status = str(status or "")
    if status in {"thinking", "streaming"}:
        return "thinking"
    if status == "executing_tool":
        return "executing_tool"
    if status == "ready":
        return "ready"
    if status in {"done", "interrupted", "error"}:
        return "done"
    return status


def serialize_canonical_event(event: CanonicalBridgeEvent) -> dict[str, Any] | None:
    payload = event.payload or {}

    if event.event_type == CanonicalEventType.STATUS_CHANGED:
        status = str(payload.get("status") or "")
        return serialize_status_message(status) if status else None

    if event.event_type == CanonicalEventType.REASONING_DELTA:
        return serialize_thinking_message(str(payload.get("content") or ""))

    if event.event_type == CanonicalEventType.CONTENT_DELTA:
        return serialize_content_message(str(payload.get("content") or ""))

    if event.event_type == CanonicalEventType.USAGE_UPDATED:
        usage = payload.get("usage") or {}
        return serialize_tokens_message(
            total=int(usage.get("total_tokens", 0) or 0),
            prompt=int(usage.get("prompt_tokens", 0) or 0),
            completion=int(usage.get("completion_tokens", 0) or 0),
        )

    if event.event_type == CanonicalEventType.TOOL_CALL_STARTED:
        return serialize_status_message("executing_tool")

    if event.event_type == CanonicalEventType.MESSAGE_COMPLETED:
        return serialize_status_message("done")

    if event.event_type == CanonicalEventType.ERROR_RAISED:
        return serialize_error_message(
            content=str(payload.get("content") or ""),
            code=str(payload.get("code") or ""),
        )

    if event.event_type == CanonicalEventType.INTERRUPT_ACK:
        return serialize_status_message("done")

    return None


def serialize_runtime_event_response(response: Any) -> dict[str, Any] | None:
    raw_event_type = getattr(response, "event_type", "") or ""
    event_type = getattr(raw_event_type, "value", raw_event_type)
    payload = getattr(response, "payload", {}) or {}

    try:
        canonical_event_type = CanonicalEventType(event_type)
    except ValueError:
        return None

    return serialize_canonical_event(
        CanonicalBridgeEvent(
            event_type=canonical_event_type,
            payload=dict(payload),
        )
    )


def serialize_application_response(response: Any) -> dict[str, Any] | None:
    from backend.alice.application.dto.responses import (
        ContentResponse,
        DoneResponse,
        ErrorResponse,
        ExecutingToolResponse,
        RuntimeEventResponse,
        StatusResponse,
        ThinkingResponse,
        TokensResponse,
    )

    if isinstance(response, RuntimeEventResponse):
        return serialize_runtime_event_response(response)
    if isinstance(response, ContentResponse):
        return serialize_content_message(response.content)
    if isinstance(response, ThinkingResponse):
        return serialize_thinking_message(response.content)
    if isinstance(response, StatusResponse):
        return serialize_status_message(response.status.value)
    if isinstance(response, ErrorResponse):
        return serialize_error_message(response.content, response.code)
    if isinstance(response, TokensResponse):
        return serialize_tokens_message(response.total, response.prompt, response.completion)
    if isinstance(response, ExecutingToolResponse):
        return serialize_status_message("executing_tool")
    if isinstance(response, DoneResponse):
        return serialize_status_message("done")
    return None


__all__ = [
    "serialize_status_message",
    "serialize_thinking_message",
    "serialize_content_message",
    "serialize_tokens_message",
    "serialize_error_message",
    "serialize_canonical_event",
    "serialize_runtime_event_response",
    "serialize_application_response",
]
