from __future__ import annotations

import asyncio
import contextlib
import json
import logging

from websockets.asyncio.server import ServerConnection, serve

from .auth import build_process_request
from .config import GatewayConfig
from .models import GatewayErrorCode, make_frame
from .session_registry import GatewaySessionRegistry

logger = logging.getLogger(__name__)


class GatewayServer:
    def __init__(self, *, config: GatewayConfig, agent_factory) -> None:
        self.config = config
        self.registry = GatewaySessionRegistry(
            protocol_version=config.protocol_version,
            replay_limit=config.replay_limit,
            outbound_queue_limit=config.outbound_queue_limit,
            session_ttl_seconds=config.session_ttl_seconds,
            agent_factory=agent_factory,
        )
        self._server = None

    async def start(self):
        self._server = await serve(
            self._handle_connection,
            self.config.host,
            self.config.port,
            process_request=build_process_request(self.config),
        )
        return self._server

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()

    async def _handle_connection(self, websocket: ServerConnection) -> None:
        writer_task: asyncio.Task[None] | None = None
        runtime = None
        session_id = ""
        try:
            async for raw_message in websocket:
                try:
                    frame = json.loads(raw_message)
                except json.JSONDecodeError:
                    await self._send_error(websocket, GatewayErrorCode.INVALID_FRAME, "invalid json frame", session_id=session_id)
                    continue
                frame_type = str(frame.get("type") or "")
                if frame_type == "ping":
                    await websocket.send(json.dumps(make_frame(
                        "pong",
                        protocol_version=self.config.protocol_version,
                        session_id=session_id,
                        request_id=frame.get("request_id"),
                        payload={},
                    )))
                    continue

                if frame_type == "session.bind":
                    next_session_id = str(frame.get("session_id") or "")
                    if not next_session_id:
                        await self._send_error(websocket, GatewayErrorCode.SESSION_REQUIRED, "session_id is required")
                        continue
                    if writer_task is not None:
                        await self._cancel_writer_task(runtime, writer_task)
                        writer_task = None
                    resume_index = frame.get("payload", {}).get("resume_from_event_index")
                    bind_result = self.registry.bind(next_session_id, resume_from_event_index=resume_index)
                    runtime = self.registry.get(next_session_id)
                    assert runtime is not None
                    session_id = next_session_id
                    previous_writer_task = runtime.replace_writer_task(None)
                    if previous_writer_task is not None:
                        await self._cancel_writer_task(runtime, previous_writer_task)
                    bound_frame = make_frame(
                        "session.bound",
                        protocol_version=self.config.protocol_version,
                        session_id=session_id,
                        payload={
                            "replay_gap": bind_result.replay_gap,
                            "active_request": bind_result.active_request.to_dict() if bind_result.active_request else None,
                            "replayed_count": len(bind_result.replay_frames),
                        },
                    )
                    await websocket.send(json.dumps(bound_frame))
                    for replay_frame in bind_result.replay_frames:
                        await websocket.send(json.dumps(replay_frame))
                    writer_task = asyncio.create_task(
                        self._writer_loop(
                            websocket,
                            runtime,
                            binding_generation=bind_result.binding_generation,
                            live_from_event_index=bind_result.live_from_event_index,
                        )
                    )
                    runtime.replace_writer_task(writer_task)
                    continue

                if not session_id:
                    await self._send_error(websocket, GatewayErrorCode.SESSION_REQUIRED, "bind session first")
                    continue

                runtime = self.registry.get(session_id)
                if runtime is None:
                    await self._send_error(websocket, GatewayErrorCode.SESSION_REQUIRED, "session not found")
                    continue

                if frame_type == "request.start":
                    request_id = str(frame.get("request_id") or "")
                    payload = dict(frame.get("payload") or {})
                    user_input = str(payload.get("input") or "")
                    metadata = dict(payload.get("metadata") or {})
                    if not request_id:
                        await self._send_error(websocket, GatewayErrorCode.INVALID_FRAME, "request_id is required", session_id=session_id)
                        continue
                    status = await runtime.start_request(
                        request_id=request_id,
                        user_input=user_input,
                        metadata=metadata,
                    )
                    if status == "conflict":
                        await self._send_error(websocket, GatewayErrorCode.REQUEST_CONFLICT, "session already has active request", session_id=session_id, request_id=request_id)
                    elif status == "duplicate":
                        await websocket.send(json.dumps(make_frame(
                            "request.accepted",
                            protocol_version=self.config.protocol_version,
                            session_id=session_id,
                            request_id=request_id,
                            payload={"duplicate": True},
                        )))
                    continue

                if frame_type == "request.interrupt":
                    request_id = str(frame.get("request_id") or "")
                    if not request_id:
                        await self._send_error(websocket, GatewayErrorCode.INVALID_FRAME, "request_id is required", session_id=session_id)
                        continue
                    interrupted = await runtime.interrupt(request_id)
                    if not interrupted:
                        await self._send_error(websocket, GatewayErrorCode.REQUEST_NOT_ACTIVE, "request is not active", session_id=session_id, request_id=request_id)
                    continue

                await self._send_error(websocket, GatewayErrorCode.INVALID_FRAME, f"unsupported frame type: {frame_type}", session_id=session_id)
        finally:
            if writer_task is not None:
                await self._cancel_writer_task(runtime, writer_task)

    async def _writer_loop(
        self,
        websocket: ServerConnection,
        runtime,
        *,
        binding_generation: int,
        live_from_event_index: int,
    ) -> None:
        while True:
            frame = await runtime.outbound_queue.get()
            if runtime.binding_generation != binding_generation:
                return
            event_index = int(frame.get("event_index") or 0)
            if event_index and event_index < live_from_event_index:
                continue
            await websocket.send(json.dumps(frame))

    async def _cancel_writer_task(self, runtime, writer_task: asyncio.Task[None]) -> None:
        if runtime is not None:
            runtime.detach_writer(writer_task)
        writer_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await writer_task

    async def _send_error(
        self,
        websocket: ServerConnection,
        code: GatewayErrorCode,
        message: str,
        *,
        session_id: str = "",
        request_id: str | None = None,
    ) -> None:
        await websocket.send(json.dumps(make_frame(
            "error",
            protocol_version=self.config.protocol_version,
            session_id=session_id,
            request_id=request_id,
            payload={"code": code.value, "message": message},
        )))


__all__ = ["GatewayServer"]
