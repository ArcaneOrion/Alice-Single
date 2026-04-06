from __future__ import annotations

from typing import Any

from backend.alice.application.dto.responses import ErrorResponse, RuntimeEventResponse

from .models import make_frame


def _runtime_output_to_dict(runtime_output: Any) -> dict[str, Any] | None:
    if runtime_output is None:
        return None
    to_dict = getattr(runtime_output, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    return dict(runtime_output)


def project_application_response(
    response: Any,
    *,
    protocol_version: str,
    session_id: str,
    request_id: str,
) -> dict[str, Any]:
    if isinstance(response, RuntimeEventResponse):
        payload = {
            "response_type": response.response_type.value,
            "event_type": response.event_type.value,
            "payload": dict(response.payload or {}),
            "runtime_output": _runtime_output_to_dict(response.runtime_output),
        }
        return make_frame(
            "runtime.event",
            protocol_version=protocol_version,
            session_id=session_id,
            request_id=request_id,
            payload=payload,
        )

    if isinstance(response, ErrorResponse):
        return make_frame(
            "error",
            protocol_version=protocol_version,
            session_id=session_id,
            request_id=request_id,
            payload={
                "code": response.code or "APPLICATION_ERROR",
                "message": response.content,
                "details": dict(response.details or {}),
            },
        )

    return make_frame(
        "error",
        protocol_version=protocol_version,
        session_id=session_id,
        request_id=request_id,
        payload={
            "code": "UNSUPPORTED_RESPONSE",
            "message": f"Unsupported response type: {type(response).__name__}",
        },
    )


__all__ = ["project_application_response"]
