from __future__ import annotations

import asyncio

import pytest

from backend.alice.infrastructure.gateway.session_registry import GatewaySessionRegistry


class _DummyAgent:
    def chat(self, user_input: str, **kwargs):
        _ = user_input, kwargs
        yield from ()

    def interrupt(self) -> None:
        return None

    def shutdown(self) -> None:
        return None


class _BlockingAgent:
    def __init__(self, release_event) -> None:
        self._release_event = release_event

    def chat(self, user_input: str, **kwargs):
        _ = user_input, kwargs
        self._release_event.wait(timeout=1)
        yield from ()

    def interrupt(self) -> None:
        return None

    def shutdown(self) -> None:
        return None


def _run(coro):
    return asyncio.run(coro)


async def _start_two_requests(runtime):
    accepted = await runtime.start_request(request_id="req-1", user_input="hello", metadata={})
    conflict = await runtime.start_request(request_id="req-2", user_input="world", metadata={})
    return accepted, conflict


async def _start_duplicate_requests(runtime):
    accepted = await runtime.start_request(request_id="req-1", user_input="hello", metadata={})
    duplicate = await runtime.start_request(request_id="req-1", user_input="hello", metadata={})
    return accepted, duplicate


async def _close_runtime(runtime) -> None:
    await runtime.close()


async def _drain_runtime_tick() -> None:
    await asyncio.sleep(0)


async def _allow_background_completion() -> None:
    await asyncio.sleep(0.01)


async def _wait_for_request_completion(runtime) -> None:
    for _ in range(50):
        if runtime.active_request_id == "":
            return
        await asyncio.sleep(0.01)


async def _start_conflict_scenario(runtime, release_event) -> tuple[str, str]:
    accepted = await runtime.start_request(request_id="req-1", user_input="hello", metadata={})
    conflict = await runtime.start_request(request_id="req-2", user_input="world", metadata={})
    release_event.set()
    await _wait_for_request_completion(runtime)
    return accepted, conflict


async def _start_duplicate_after_completion(runtime) -> tuple[str, str]:
    accepted = await runtime.start_request(request_id="req-1", user_input="hello", metadata={})
    await _wait_for_request_completion(runtime)
    duplicate = await runtime.start_request(request_id="req-1", user_input="hello", metadata={})
    await _allow_background_completion()
    return accepted, duplicate


def _blocking_agent_factory(release_event):
    return lambda: _BlockingAgent(release_event)


def _dummy_agent_factory():
    return _DummyAgent()


def _build_registry(agent_factory):
    return GatewaySessionRegistry(
        protocol_version="1",
        replay_limit=8,
        outbound_queue_limit=8,
        session_ttl_seconds=60,
        agent_factory=agent_factory,
    )


def _bind_runtime(registry):
    registry.bind("session-1")
    runtime = registry.get("session-1")
    assert runtime is not None
    return runtime


def _thread_event():
    import threading

    return threading.Event()


def _cleanup_runtime(runtime):
    _run(_close_runtime(runtime))


def _run_conflict_case(runtime, release_event):
    return _run(_start_conflict_scenario(runtime, release_event))


def _run_duplicate_case(runtime):
    return _run(_start_duplicate_after_completion(runtime))


def _build_blocking_runtime():
    release_event = _thread_event()
    registry = _build_registry(_blocking_agent_factory(release_event))
    runtime = _bind_runtime(registry)
    return runtime, release_event


def _build_dummy_runtime():
    registry = _build_registry(_dummy_agent_factory)
    return _bind_runtime(registry)


class _RuntimeCleanup:
    def __init__(self, runtime) -> None:
        self.runtime = runtime

    def __enter__(self):
        return self.runtime

    def __exit__(self, exc_type, exc, tb) -> None:
        _cleanup_runtime(self.runtime)
        return False


def _managed_runtime(runtime):
    return _RuntimeCleanup(runtime)


def _managed_blocking_runtime():
    runtime, release_event = _build_blocking_runtime()
    return _managed_runtime(runtime), release_event


def _managed_dummy_runtime():
    return _managed_runtime(_build_dummy_runtime())


def _assert_pair(result, expected_left, expected_right):
    left, right = result
    assert left == expected_left
    assert right == expected_right


def _run_conflict_assertion():
    runtime_cm, release_event = _managed_blocking_runtime()
    with runtime_cm as runtime:
        _assert_pair(_run_conflict_case(runtime, release_event), "accepted", "conflict")


def _run_duplicate_assertion():
    with _managed_dummy_runtime() as runtime:
        _assert_pair(_run_duplicate_case(runtime), "accepted", "duplicate")


def _run_registry_reuse_assertion() -> GatewaySessionRegistry:
    return _build_registry(_dummy_agent_factory)


def _bind_same_session_twice(registry):
    first = registry.bind("session-1")
    second = registry.bind("session-1")
    return first, second


def _assert_same_session_binding(first, second, registry) -> None:
    assert first.session_id == "session-1"
    assert second.session_id == "session-1"
    assert registry.get("session-1") is not None


def _run_binding_assertion() -> None:
    registry = _run_registry_reuse_assertion()
    first, second = _bind_same_session_twice(registry)
    _assert_same_session_binding(first, second, registry)


def _noop() -> None:
    return None


_noop()


class _DummyAgentFactory:
    def __call__(self):
        return _DummyAgent()


class _BlockingAgentFactory:
    def __init__(self, release_event) -> None:
        self.release_event = release_event

    def __call__(self):
        return _BlockingAgent(self.release_event)


def _build_registry_with_factory(agent_factory):
    return GatewaySessionRegistry(
        protocol_version="1",
        replay_limit=8,
        outbound_queue_limit=8,
        session_ttl_seconds=60,
        agent_factory=agent_factory,
    )


def _build_dummy_registry():
    return _build_registry_with_factory(_DummyAgentFactory())


def _build_blocking_registry(release_event):
    return _build_registry_with_factory(_BlockingAgentFactory(release_event))


def _get_bound_runtime(registry):
    registry.bind("session-1")
    runtime = registry.get("session-1")
    assert runtime is not None
    return runtime


def _managed_runtime_from_registry(registry):
    return _managed_runtime(_get_bound_runtime(registry))


def _run_single_flight_assertion() -> None:
    release_event = _thread_event()
    with _managed_runtime_from_registry(_build_blocking_registry(release_event)) as runtime:
        _assert_pair(_run_conflict_case(runtime, release_event), "accepted", "conflict")


def _run_duplicate_request_assertion() -> None:
    with _managed_runtime_from_registry(_build_dummy_registry()) as runtime:
        _assert_pair(_run_duplicate_case(runtime), "accepted", "duplicate")


_run_registry_reuse_assertion


@pytest.mark.unit
def test_session_registry_returns_same_runtime_for_same_session() -> None:
    registry = GatewaySessionRegistry(
        protocol_version="1",
        replay_limit=8,
        outbound_queue_limit=8,
        session_ttl_seconds=60,
        agent_factory=_DummyAgent,
    )

    first = registry.bind("session-1")
    second = registry.bind("session-1")
    runtime = registry.get("session-1")

    try:
        assert first.session_id == "session-1"
        assert second.session_id == "session-1"
        assert runtime is not None
    finally:
        if runtime is not None:
            _cleanup_runtime(runtime)


@pytest.mark.unit
def test_session_runtime_enforces_single_flight() -> None:
    async def _scenario() -> None:
        release_event = _thread_event()
        registry = GatewaySessionRegistry(
            protocol_version="1",
            replay_limit=8,
            outbound_queue_limit=8,
            session_ttl_seconds=60,
            agent_factory=_BlockingAgentFactory(release_event),
        )
        registry.bind("session-1")
        runtime = registry.get("session-1")
        assert runtime is not None

        try:
            accepted = await runtime.start_request(request_id="req-1", user_input="hello", metadata={})
            conflict = await runtime.start_request(request_id="req-2", user_input="world", metadata={})

            assert accepted == "accepted"
            assert conflict == "conflict"

            release_event.set()
            await _wait_for_request_completion(runtime)
        finally:
            release_event.set()
            await runtime.close()

    asyncio.run(_scenario())


@pytest.mark.unit
def test_session_runtime_marks_duplicate_request_id() -> None:
    registry = GatewaySessionRegistry(
        protocol_version="1",
        replay_limit=8,
        outbound_queue_limit=8,
        session_ttl_seconds=60,
        agent_factory=_DummyAgent,
    )
    registry.bind("session-1")
    runtime = registry.get("session-1")
    assert runtime is not None

    try:
        accepted = asyncio.run(runtime.start_request(request_id="req-1", user_input="hello", metadata={}))
        asyncio.run(asyncio.sleep(0))
        duplicate = asyncio.run(runtime.start_request(request_id="req-1", user_input="hello", metadata={}))

        assert accepted == "accepted"
        assert duplicate == "duplicate"
    finally:
        _cleanup_runtime(runtime)


@pytest.mark.unit
def test_publish_control_does_not_block_when_queue_is_full_without_writer() -> None:
    async def _scenario() -> None:
        registry = GatewaySessionRegistry(
            protocol_version="1",
            replay_limit=8,
            outbound_queue_limit=1,
            session_ttl_seconds=60,
            agent_factory=_DummyAgent,
        )
        registry.bind("session-1")
        runtime = registry.get("session-1")
        assert runtime is not None

        await runtime.outbound_queue.put(
            {
                "type": "runtime.event",
                "protocol_version": "1",
                "session_id": "session-1",
                "request_id": "req-queued",
                "event_index": 1,
                "payload": {"runtime_output": {"content": "queued"}},
            }
        )

        try:
            await asyncio.wait_for(
                runtime._publish_control(
                    {
                        "type": "request.completed",
                        "protocol_version": "1",
                        "session_id": "session-1",
                        "request_id": "req-1",
                        "event_index": None,
                        "payload": {"final_state": "done", "error": None},
                    }
                ),
                timeout=0.1,
            )
            frames, replay_gap = runtime.replay_from(None)
            assert replay_gap is False
            assert any(frame["type"] == "request.completed" for frame in frames)
        finally:
            await runtime.close()

    asyncio.run(_scenario())
