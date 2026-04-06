import pytest

from backend.alice.application.dto.responses import RuntimeEventResponse, RuntimeEventType, StructuredRuntimeOutput
from backend.alice.infrastructure.gateway.projector import project_application_response


@pytest.mark.unit
def test_projector_wraps_runtime_event_response() -> None:
    response = RuntimeEventResponse(
        event_type=RuntimeEventType.CONTENT_DELTA,
        payload={"content": "hello"},
        runtime_output=StructuredRuntimeOutput(
            message_id="req-1.iter1",
            status="streaming",
            content="hello",
            metadata={"session_id": "session-1", "request_id": "req-1"},
        ),
    )

    frame = project_application_response(
        response,
        protocol_version="1",
        session_id="session-1",
        request_id="req-1",
    )

    assert frame["type"] == "runtime.event"
    assert frame["payload"]["event_type"] == RuntimeEventType.CONTENT_DELTA.value
    assert frame["payload"]["payload"] == {"content": "hello"}
    assert frame["payload"]["runtime_output"]["message_id"] == "req-1.iter1"
    assert frame["session_id"] == "session-1"
    assert frame["request_id"] == "req-1"
