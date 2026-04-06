from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from .models import SessionBindResult, SessionRequestState
from .session_runtime import AgentRuntime, GatewaySessionRuntime


class GatewaySessionRegistry:
    def __init__(
        self,
        *,
        protocol_version: str,
        replay_limit: int,
        outbound_queue_limit: int,
        session_ttl_seconds: int,
        agent_factory: Callable[[], AgentRuntime],
    ) -> None:
        self._protocol_version = protocol_version
        self._replay_limit = replay_limit
        self._outbound_queue_limit = outbound_queue_limit
        self._session_ttl = timedelta(seconds=session_ttl_seconds)
        self._agent_factory = agent_factory
        self._sessions: dict[str, GatewaySessionRuntime] = {}

    def bind(self, session_id: str, *, resume_from_event_index: int | None = None) -> SessionBindResult:
        runtime = self._sessions.get(session_id)
        if runtime is None:
            runtime = GatewaySessionRuntime(
                session_id=session_id,
                protocol_version=self._protocol_version,
                replay_limit=self._replay_limit,
                outbound_queue_limit=self._outbound_queue_limit,
                agent_factory=self._agent_factory,
            )
            self._sessions[session_id] = runtime
        _, live_from_event_index, frames, replay_gap = runtime.prepare_bind(
            resume_from_event_index
        )
        request_state = runtime.request_state()
        active_request = (
            SessionRequestState(request_id=request_state["request_id"], state=request_state["state"])
            if request_state is not None
            else None
        )
        return SessionBindResult(
            session_id=session_id,
            binding_generation=runtime.binding_generation,
            live_from_event_index=live_from_event_index,
            replay_frames=frames,
            replay_gap=replay_gap,
            active_request=active_request,
        )

    def get(self, session_id: str) -> GatewaySessionRuntime | None:
        runtime = self._sessions.get(session_id)
        if runtime is not None:
            runtime.touch()
        return runtime

    def evict_expired(self) -> list[str]:
        cutoff = datetime.now(UTC) - self._session_ttl
        expired = [session_id for session_id, runtime in self._sessions.items() if runtime.last_touch < cutoff]
        for session_id in expired:
            self._sessions.pop(session_id, None)
        return expired


__all__ = ["GatewaySessionRegistry"]
