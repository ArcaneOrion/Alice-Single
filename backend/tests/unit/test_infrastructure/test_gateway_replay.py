import pytest

from backend.alice.infrastructure.gateway.replay import ReplayBuffer


@pytest.mark.unit
def test_replay_buffer_assigns_monotonic_event_index() -> None:
    buffer = ReplayBuffer(limit=4)

    first = buffer.append({"type": "runtime.event", "payload": {}})
    second = buffer.append({"type": "request.completed", "payload": {}})

    assert first["event_index"] == 1
    assert second["event_index"] == 2


@pytest.mark.unit
def test_replay_buffer_replays_after_resume_index() -> None:
    buffer = ReplayBuffer(limit=4)
    buffer.append({"type": "runtime.event", "payload": {"runtime_output": {"content": "a"}}})
    buffer.append({"type": "runtime.event", "payload": {"runtime_output": {"content": "b"}}})

    frames, replay_gap = buffer.replay_from(1)

    assert replay_gap is False
    assert [frame["event_index"] for frame in frames] == [2]


@pytest.mark.unit
def test_replay_buffer_returns_gap_recovery_when_resume_too_old() -> None:
    buffer = ReplayBuffer(limit=2)
    buffer.append({"type": "runtime.event", "payload": {"runtime_output": {"content": "a"}}})
    buffer.append({"type": "runtime.event", "payload": {"runtime_output": {"content": "b"}}})
    buffer.append({"type": "request.completed", "payload": {"final_state": "done"}})

    frames, replay_gap = buffer.replay_from(0)

    assert replay_gap is True
    assert len(frames) == 1
    assert frames[0]["type"] in {"runtime.event", "request.completed"}
