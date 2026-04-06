from __future__ import annotations

import asyncio
from typing import Any

import pytest
from backend.alice.infrastructure.gateway.session_runtime import GatewaySessionRuntime


class _DummyAgent:
    def chat(self, user_input: str, **kwargs: Any):
        _ = user_input, kwargs
        yield from ()

    def interrupt(self) -> None:
        return None

    def shutdown(self) -> None:
        return None


@pytest.mark.unit
def test_publish_control_does_not_block_when_queue_is_full_without_writer() -> None:
    async def _scenario() -> None:
        runtime = GatewaySessionRuntime(
            session_id="session-1",
            protocol_version="1",
            replay_limit=8,
            outbound_queue_limit=1,
            agent_factory=_DummyAgent,
        )

        first_frame = {
            "type": "request.accepted",
            "protocol_version": "1",
            "session_id": "session-1",
            "request_id": "req-1",
            "event_index": None,
            "payload": {"duplicate": False},
        }
        second_frame = {
            "type": "request.completed",
            "protocol_version": "1",
            "session_id": "session-1",
            "request_id": "req-1",
            "event_index": None,
            "payload": {"final_state": "done", "error": None},
        }

        try:
            await runtime._publish_control(first_frame)
            await asyncio.wait_for(runtime._publish_control(second_frame), timeout=0.05)

            replay_frames, replay_gap = runtime.replay_from(None)
            assert replay_gap is False
            assert [frame["type"] for frame in replay_frames] == [
                "request.accepted",
                "request.completed",
            ]
        finally:
            await runtime.close()

    asyncio.run(_scenario())
