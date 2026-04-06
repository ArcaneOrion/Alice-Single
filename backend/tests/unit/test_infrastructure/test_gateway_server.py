from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator
from typing import Any

import pytest
from backend.alice.infrastructure.gateway import GatewayConfig, GatewayServer


class _DummyAgent:
    def chat(self, user_input: str, **kwargs: Any):
        _ = user_input, kwargs
        yield from ()

    def interrupt(self) -> None:
        return None

    def shutdown(self) -> None:
        return None


class _CloseInput:
    pass


_CLOSE_INPUT = _CloseInput()


class _FakeWebSocket:
    def __init__(self) -> None:
        self._incoming: asyncio.Queue[str | _CloseInput] = asyncio.Queue()
        self._sent: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    def push_raw(self, raw_message: str) -> None:
        self._incoming.put_nowait(raw_message)

    def push_frame(self, frame: dict[str, Any]) -> None:
        self.push_raw(json.dumps(frame))

    def close_input(self) -> None:
        self._incoming.put_nowait(_CLOSE_INPUT)

    def __aiter__(self) -> AsyncIterator[str]:
        return self

    async def __anext__(self) -> str:
        message = await self._incoming.get()
        if message is _CLOSE_INPUT:
            raise StopAsyncIteration
        return message

    async def send(self, payload: str) -> None:
        await self._sent.put(json.loads(payload))

    async def next_sent(self, timeout: float = 0.2) -> dict[str, Any]:
        return await asyncio.wait_for(self._sent.get(), timeout=timeout)

    async def maybe_next_sent(self, timeout: float = 0.05) -> dict[str, Any] | None:
        try:
            return await self.next_sent(timeout=timeout)
        except TimeoutError:
            return None


def _build_server() -> GatewayServer:
    return GatewayServer(
        config=GatewayConfig(
            protocol_version="1",
            outbound_queue_limit=8,
            replay_limit=8,
            session_ttl_seconds=60,
        ),
        agent_factory=_DummyAgent,
    )


async def _close_runtime(server: GatewayServer, session_id: str) -> None:
    runtime = server.registry.get(session_id)
    if runtime is not None:
        await runtime.close()


async def _shutdown_connection(task: asyncio.Task[None], websocket: _FakeWebSocket) -> None:
    websocket.close_input()
    with contextlib.suppress(Exception):
        await task


async def _bind_connection(
    server: GatewayServer,
    websocket: _FakeWebSocket,
    *,
    session_id: str = "session-1",
    resume_from_event_index: int | None = None,
) -> asyncio.Task[None]:
    task = asyncio.create_task(server._handle_connection(websocket))
    payload = {}
    if resume_from_event_index is not None:
        payload["resume_from_event_index"] = resume_from_event_index
    websocket.push_frame(
        {
            "type": "session.bind",
            "session_id": session_id,
            "payload": payload,
        }
    )
    bound = await websocket.next_sent()
    assert bound["type"] == "session.bound"
    return task


def test_invalid_json_frame_returns_invalid_frame_and_keeps_connection_open() -> None:
    async def _scenario() -> None:
        server = _build_server()
        websocket = _FakeWebSocket()
        task = asyncio.create_task(server._handle_connection(websocket))

        try:
            websocket.push_raw("{bad json")
            error_frame = await websocket.next_sent()
            assert error_frame["type"] == "error"
            assert error_frame["payload"]["code"] == "INVALID_FRAME"

            websocket.push_frame({"type": "ping", "request_id": "req-1"})
            pong_frame = await websocket.next_sent()
            assert pong_frame["type"] == "pong"
            assert pong_frame["request_id"] == "req-1"
        finally:
            await _shutdown_connection(task, websocket)

    asyncio.run(_scenario())


def test_rebind_only_delivers_live_frames_to_latest_websocket() -> None:
    async def _scenario() -> None:
        server = _build_server()
        websocket_one = _FakeWebSocket()
        websocket_two = _FakeWebSocket()

        task_one = await _bind_connection(server, websocket_one)
        await asyncio.sleep(0)
        task_two = await _bind_connection(server, websocket_two)
        await asyncio.sleep(0)

        runtime = server.registry.get("session-1")
        assert runtime is not None
        live_frame = {
            "type": "runtime.event",
            "protocol_version": "1",
            "session_id": "session-1",
            "request_id": "req-live",
            "event_index": 99,
            "payload": {"runtime_output": {"content": "live"}},
        }

        try:
            await runtime.outbound_queue.put(live_frame)
            old_connection_frame = await websocket_one.maybe_next_sent(timeout=0.1)
            new_connection_frame = await websocket_two.maybe_next_sent(timeout=0.1)

            assert old_connection_frame is None
            assert new_connection_frame is not None
            assert new_connection_frame["request_id"] == "req-live"
        finally:
            await _shutdown_connection(task_one, websocket_one)
            await _shutdown_connection(task_two, websocket_two)
            await _close_runtime(server, "session-1")

    asyncio.run(_scenario())


def test_bind_replays_buffered_frames_without_sending_duplicates() -> None:
    async def _scenario() -> None:
        server = _build_server()
        server.registry.bind("session-1")
        runtime = server.registry.get("session-1")
        assert runtime is not None

        buffered_frame = {
            "type": "runtime.event",
            "protocol_version": "1",
            "session_id": "session-1",
            "request_id": "req-replay",
            "event_index": None,
            "payload": {"runtime_output": {"content": "buffered"}},
        }
        await runtime._publish_control(buffered_frame)

        websocket = _FakeWebSocket()
        task = asyncio.create_task(server._handle_connection(websocket))

        try:
            websocket.push_frame(
                {
                    "type": "session.bind",
                    "session_id": "session-1",
                    "payload": {"resume_from_event_index": 0},
                }
            )
            first_frame = await websocket.next_sent()
            second_frame = await websocket.next_sent()
            third_frame = await websocket.maybe_next_sent(timeout=0.1)

            assert first_frame["type"] == "session.bound"
            assert second_frame["type"] == "runtime.event"
            assert second_frame["request_id"] == "req-replay"
            assert third_frame is None
        finally:
            await _shutdown_connection(task, websocket)
            await _close_runtime(server, "session-1")

    asyncio.run(_scenario())


pytestmark = pytest.mark.unit
