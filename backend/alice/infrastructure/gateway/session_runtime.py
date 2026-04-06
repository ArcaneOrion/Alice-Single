from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any, Protocol

from backend.alice.application.dto.responses import ApplicationResponse, RuntimeEventType

from .models import DROPPABLE_RUNTIME_EVENT_TYPES
from .projector import project_application_response
from .replay import ReplayBuffer

logger = logging.getLogger(__name__)


class AgentRuntime(Protocol):
    def chat(self, user_input: str, **kwargs: Any) -> Iterable[ApplicationResponse]: ...
    def interrupt(self) -> None: ...
    def shutdown(self) -> None: ...


class GatewaySessionRuntime:

    def __init__(
        self,
        *,
        session_id: str,
        protocol_version: str,
        replay_limit: int,
        outbound_queue_limit: int,
        agent_factory: Callable[[], AgentRuntime],
    ) -> None:
        self.session_id = session_id
        self.protocol_version = protocol_version
        self.outbound_queue_limit = outbound_queue_limit
        self._agent_factory = agent_factory
        self._agent: AgentRuntime | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"gateway-session-{session_id}")
        self._lock = asyncio.Lock()
        self._active_request_id = ""
        self._completed_requests: dict[str, str] = {}
        self._binding_generation = 0
        self._replay = ReplayBuffer(replay_limit)
        self._outbound_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=outbound_queue_limit)
        self._writer_task: asyncio.Task[None] | None = None
        self._dropped_delta_count = 0
        self._last_touch = datetime.now(UTC)

    @property
    def outbound_queue(self) -> asyncio.Queue[dict[str, Any]]:
        return self._outbound_queue

    @property
    def active_request_id(self) -> str:
        return self._active_request_id

    @property
    def binding_generation(self) -> int:
        return self._binding_generation

    @property
    def live_from_event_index(self) -> int:
        return self._replay.next_event_index

    @property
    def last_touch(self) -> datetime:
        return self._last_touch

    def touch(self) -> None:
        self._last_touch = datetime.now(UTC)

    def request_state(self) -> dict[str, str] | None:
        if not self._active_request_id:
            return None
        return {"request_id": self._active_request_id, "state": "running"}

    def replay_from(self, resume_from_event_index: int | None) -> tuple[list[dict[str, Any]], bool]:
        return self._replay.replay_from(resume_from_event_index)

    def prepare_bind(
        self, resume_from_event_index: int | None
    ) -> tuple[int, int, list[dict[str, Any]], bool]:
        self.touch()
        self._binding_generation += 1
        replay_frames, replay_gap = self._replay.replay_from(resume_from_event_index)
        return self._binding_generation, self.live_from_event_index, replay_frames, replay_gap

    def replace_writer_task(
        self, writer_task: asyncio.Task[None] | None
    ) -> asyncio.Task[None] | None:
        previous = self._writer_task
        self._writer_task = writer_task
        return previous

    def detach_writer(self, writer_task: asyncio.Task[None] | None = None) -> None:
        if writer_task is None or self._writer_task is writer_task:
            self._writer_task = None

    def cancel_writer(self) -> None:
        writer_task = self.replace_writer_task(None)
        if writer_task is not None:
            writer_task.cancel()

    def _active_writer_task(self) -> asyncio.Task[None] | None:
        writer_task = self._writer_task
        if writer_task is not None and writer_task.done():
            self.detach_writer(writer_task)
            return None
        return writer_task

    def has_request(self, request_id: str) -> bool:
        return request_id in self._completed_requests or request_id == self._active_request_id

    async def start_request(self, *, request_id: str, user_input: str, metadata: dict[str, Any]) -> str:
        self.touch()
        async with self._lock:
            if self._active_request_id and self._active_request_id != request_id:
                return "conflict"
            if request_id in self._completed_requests:
                return "duplicate"
            if self._active_request_id == request_id:
                return "duplicate"

            self._active_request_id = request_id
            self._loop = asyncio.get_running_loop()
            self._ensure_agent()
            await self._publish_control(
                {
                    "type": "request.accepted",
                    "protocol_version": self.protocol_version,
                    "session_id": self.session_id,
                    "request_id": request_id,
                    "event_index": None,
                    "payload": {"duplicate": False},
                }
            )
            self._loop.create_task(self._run_request(request_id=request_id, user_input=user_input, metadata=metadata))
            return "accepted"

    async def interrupt(self, request_id: str) -> bool:
        self.touch()
        if not self._active_request_id or self._active_request_id != request_id:
            return False
        agent = self._ensure_agent()
        await asyncio.get_running_loop().run_in_executor(self._executor, agent.interrupt)
        return True

    async def close(self) -> None:
        self.cancel_writer()
        agent = self._agent
        if agent is not None:
            await asyncio.to_thread(agent.shutdown)
        self._executor.shutdown(wait=True, cancel_futures=False)

    def _ensure_agent(self) -> AgentRuntime:
        if self._agent is None:
            self._agent = self._agent_factory()
        return self._agent

    async def _run_request(self, *, request_id: str, user_input: str, metadata: dict[str, Any]) -> None:
        final_state = "done"
        error_payload: dict[str, Any] | None = None
        try:
            agent = self._ensure_agent()
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                self._executor,
                self._drain_agent_responses,
                agent,
                request_id,
                user_input,
                dict(metadata),
            )
            if self._completed_requests.get(request_id) == "interrupted":
                final_state = "interrupted"
        except Exception as exc:
            final_state = "error"
            error_payload = {"code": "REQUEST_FAILED", "message": str(exc)}
            logger.error("Gateway request execution failed", exc_info=True)
            await self._publish_control(
                {
                    "type": "error",
                    "protocol_version": self.protocol_version,
                    "session_id": self.session_id,
                    "request_id": request_id,
                    "event_index": None,
                    "payload": error_payload,
                }
            )
        finally:
            async with self._lock:
                if self._active_request_id == request_id:
                    self._active_request_id = ""
                self._completed_requests[request_id] = final_state
            await self._publish_control(
                {
                    "type": "request.completed",
                    "protocol_version": self.protocol_version,
                    "session_id": self.session_id,
                    "request_id": request_id,
                    "event_index": None,
                    "payload": {"final_state": final_state, "error": error_payload},
                }
            )

    def _drain_agent_responses(
        self,
        agent: AgentRuntime,
        request_id: str,
        user_input: str,
        metadata: dict[str, Any],
    ) -> None:
        loop = self._loop
        if loop is None:
            raise RuntimeError("Session loop not ready")

        runtime_metadata = dict(metadata)
        runtime_metadata.setdefault("session_id", self.session_id)
        runtime_metadata.setdefault("request_id", request_id)
        runtime_metadata.setdefault("trace_id", request_id)
        runtime_metadata.setdefault("task_id", request_id)

        for response in agent.chat(user_input, metadata=runtime_metadata):
            frame = project_application_response(
                response,
                protocol_version=self.protocol_version,
                session_id=self.session_id,
                request_id=request_id,
            )
            event_type = ((frame.get("payload") or {}).get("event_type"))
            if event_type == RuntimeEventType.INTERRUPT_ACK.value:
                self._completed_requests[request_id] = "interrupted"
            future = asyncio.run_coroutine_threadsafe(
                self._publish_runtime_frame(frame, event_type=event_type),
                loop,
            )
            future.result()

    async def _publish_runtime_frame(self, frame: dict[str, Any], *, event_type: str | None) -> None:
        stored = self._replay.append(frame)
        try:
            self._outbound_queue.put_nowait(stored)
        except asyncio.QueueFull:
            if self._active_writer_task() is None:
                return
            if event_type in DROPPABLE_RUNTIME_EVENT_TYPES:
                self._dropped_delta_count += 1
                return
            await self._emit_backpressure_notice()
            await self._enqueue_blocking_if_writer_alive(stored)

    async def _publish_control(self, frame: dict[str, Any]) -> None:
        stored = self._replay.append(frame)
        try:
            self._outbound_queue.put_nowait(stored)
        except asyncio.QueueFull:
            await self._enqueue_blocking_if_writer_alive(stored)

    async def _emit_backpressure_notice(self) -> None:
        notice = {
            "type": "backpressure.notice",
            "protocol_version": self.protocol_version,
            "session_id": self.session_id,
            "request_id": self._active_request_id or None,
            "event_index": None,
            "payload": {"dropped_delta_count": self._dropped_delta_count + 1},
        }
        self._dropped_delta_count = 0
        stored = self._replay.append(notice)
        try:
            self._outbound_queue.put_nowait(stored)
        except asyncio.QueueFull:
            await self._enqueue_blocking_if_writer_alive(stored)

    async def _enqueue_blocking_if_writer_alive(self, stored: dict[str, Any]) -> bool:
        writer_task = self._active_writer_task()
        if writer_task is None:
            return False

        put_task = asyncio.create_task(self._outbound_queue.put(stored))
        try:
            done, _ = await asyncio.wait(
                {put_task, writer_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if put_task in done:
                await put_task
                return True

            put_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await put_task
            self.detach_writer(writer_task)
            return False
        finally:
            if writer_task.done():
                self.detach_writer(writer_task)


__all__ = ["GatewaySessionRuntime"]
