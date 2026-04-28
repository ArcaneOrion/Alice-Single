"""Compatibility serializer for the frozen legacy bridge protocol."""

from __future__ import annotations

import logging
from typing import Any

from backend.alice.infrastructure.bridge.canonical_bridge import (
    CanonicalBridgeEvent,
    CanonicalEventType,
)

logger = logging.getLogger(__name__)


def _compatibility_log_extra(
    event_type: str,
    *,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "log_category": "bridge.compatibility",
        "context": {
            "component": "legacy_compatibility_serializer",
        },
        "data": data or {},
    }


def _emit_serializer_used(
    *,
    source_kind: str,
    projected: dict[str, Any],
    response_type: str = "",
    canonical_event_type: str = "",
) -> None:
    data = {
        "source_kind": source_kind,
        "legacy_message_type": str(projected.get("type") or ""),
    }
    if response_type:
        data["response_type"] = response_type
    if canonical_event_type:
        data["canonical_event_type"] = canonical_event_type

    if data["legacy_message_type"] == "status":
        data["legacy_status"] = str(projected.get("content") or "")

    logger.info(
        "Legacy compatibility serializer used",
        extra=_compatibility_log_extra(
            "bridge.compatibility_serializer_used",
            data=data,
        ),
    )


def _emit_projection_drop(
    *,
    source_kind: str,
    dropped_event_type: str,
    reason: str,
    payload: dict[str, Any] | None = None,
) -> None:
    logger.info(
        "Bridge event dropped by legacy projection",
        extra=_compatibility_log_extra(
            "bridge.event_dropped_by_legacy_projection",
            data={
                "source_kind": source_kind,
                "dropped_event_type": dropped_event_type,
                "reason": reason,
                "payload_keys": sorted((payload or {}).keys()),
            },
        ),
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
    serialized: dict[str, Any] | None = None

    if event.event_type == CanonicalEventType.STATUS_CHANGED:
        status = str(payload.get("status") or "")
        serialized = serialize_status_message(status) if status else None
    elif event.event_type == CanonicalEventType.REASONING_DELTA:
        serialized = serialize_thinking_message(str(payload.get("content") or ""))
    elif event.event_type == CanonicalEventType.CONTENT_DELTA:
        serialized = serialize_content_message(str(payload.get("content") or ""))
    elif event.event_type == CanonicalEventType.USAGE_UPDATED:
        usage = payload.get("usage") or {}
        serialized = serialize_tokens_message(
            total=int(usage.get("total_tokens", 0) or 0),
            prompt=int(usage.get("prompt_tokens", 0) or 0),
            completion=int(usage.get("completion_tokens", 0) or 0),
        )
    elif event.event_type == CanonicalEventType.TOOL_CALL_STARTED:
        serialized = serialize_status_message("executing_tool")
    elif event.event_type == CanonicalEventType.MESSAGE_COMPLETED:
        has_tool_calls = bool(payload.get("tool_calls"))
        runtime_status = str(getattr(getattr(event, "runtime_output", None), "status", "") or "")
        if has_tool_calls and runtime_status != "done":
            serialized = None
        else:
            serialized = serialize_status_message("done")
    elif event.event_type == CanonicalEventType.ERROR_RAISED:
        serialized = serialize_error_message(
            content=str(payload.get("content") or ""),
            code=str(payload.get("code") or ""),
        )
    elif event.event_type == CanonicalEventType.INTERRUPT_ACK:
        serialized = serialize_status_message("done")

    canonical_event_type = event.event_type.value
    if serialized is not None:
        _emit_serializer_used(
            source_kind="canonical_event",
            canonical_event_type=canonical_event_type,
            projected=serialized,
        )
        return serialized

    _emit_projection_drop(
        source_kind="canonical_event",
        dropped_event_type=canonical_event_type,
        reason="unsupported_canonical_event",
        payload=payload,
    )
    return None

def serialize_runtime_event_response(response: Any) -> dict[str, Any] | None:
    raw_event_type = getattr(response, "event_type", "") or ""
    event_type = getattr(raw_event_type, "value", raw_event_type)
    payload = getattr(response, "payload", {}) or {}

    try:
        canonical_event_type = CanonicalEventType(event_type)
    except ValueError:
        _emit_projection_drop(
            source_kind="runtime_event_response",
            dropped_event_type=str(event_type),
            reason="unknown_runtime_event_type",
            payload=dict(payload),
        )
        return None

    return serialize_canonical_event(
        CanonicalBridgeEvent(
            event_type=canonical_event_type,
            payload=dict(payload),
            runtime_output=getattr(response, "runtime_output", None),
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

    serialized: dict[str, Any] | None = None

    if isinstance(response, RuntimeEventResponse):
        return serialize_runtime_event_response(response)
    if isinstance(response, ContentResponse):
        serialized = serialize_content_message(response.content)
    elif isinstance(response, ThinkingResponse):
        serialized = serialize_thinking_message(response.content)
    elif isinstance(response, StatusResponse):
        serialized = serialize_status_message(response.status.value)
    elif isinstance(response, ErrorResponse):
        serialized = serialize_error_message(response.content, response.code)
    elif isinstance(response, TokensResponse):
        serialized = serialize_tokens_message(response.total, response.prompt, response.completion)
    elif isinstance(response, ExecutingToolResponse):
        serialized = serialize_status_message("executing_tool")
    elif isinstance(response, DoneResponse):
        serialized = serialize_status_message("done")
    else:
        _emit_projection_drop(
            source_kind="application_response",
            dropped_event_type=type(response).__name__,
            reason="unsupported_application_response",
        )
        return None

    _emit_serializer_used(
        source_kind="application_response",
        response_type=type(response).__name__,
        projected=serialized,
    )
    return serialized


def response_to_dict(response: Any) -> dict[str, Any] | None:
    """将 ApplicationResponse 投影为 legacy bridge dict。"""
    return serialize_application_response(response)


__all__ = [
    "serialize_status_message",
    "serialize_thinking_message",
    "serialize_content_message",
    "serialize_tokens_message",
    "serialize_error_message",
    "serialize_canonical_event",
    "serialize_runtime_event_response",
    "serialize_application_response",
    "response_to_dict",
]
