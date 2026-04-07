from __future__ import annotations

import logging
from pathlib import Path

from backend.alice.application.services.lifecycle_service import LifecycleService
from backend.alice.domain.execution.executors.base import ExecutionBackendStatus


class _RecordingBackend:
    def __init__(self) -> None:
        self.calls: list[tuple[bool, bool]] = []
        self._status = ExecutionBackendStatus(
            engine_ready=True,
            image_ready=True,
            container_exists=True,
            container_running=True,
            status_raw="running",
        )

    def ensure_ready(self, *, force_rebuild: bool = False, on_build_progress=None) -> ExecutionBackendStatus:
        del force_rebuild, on_build_progress
        return self._status

    def exec(self, command, *, log_context=None):
        raise NotImplementedError

    def status(self) -> ExecutionBackendStatus:
        return self._status

    def interrupt(self) -> bool:
        return True

    def cleanup(self, *, remove: bool = False, force: bool = False) -> bool:
        self.calls.append((remove, force))
        if not remove:
            self._status = ExecutionBackendStatus(
                engine_ready=True,
                image_ready=True,
                container_exists=True,
                container_running=False,
                status_raw="exited",
            )
            return True

        self._status = ExecutionBackendStatus(
            engine_ready=True,
            image_ready=True,
            container_exists=False,
            container_running=False,
            status_raw="",
        )
        return True


def test_remove_container_stops_running_container_before_removing() -> None:
    backend = _RecordingBackend()
    service = LifecycleService(backend=backend)

    service.remove_container()

    assert backend.calls == [(False, False), (True, False)]
    assert service.is_container_running is False


class _StdoutLeakingBuildBackend:
    def __init__(self) -> None:
        self._status = ExecutionBackendStatus(
            engine_ready=True,
            image_ready=True,
            container_exists=True,
            container_running=True,
            status_raw="running",
        )

    def ensure_ready(self, *, force_rebuild: bool = False, on_build_progress=None) -> ExecutionBackendStatus:
        del force_rebuild
        if on_build_progress is None:
            print("  [Docker Build]: building layer")
        else:
            on_build_progress("building layer")
        return self._status

    def exec(self, command, *, log_context=None):
        raise NotImplementedError

    def status(self) -> ExecutionBackendStatus:
        return self._status

    def interrupt(self) -> bool:
        return True

    def cleanup(self, *, remove: bool = False, force: bool = False) -> bool:
        del remove, force
        return True


def test_initialize_routes_build_progress_to_logger_instead_of_stdout(
    capsys, caplog
) -> None:
    backend = _StdoutLeakingBuildBackend()
    service = LifecycleService(backend=backend)

    with caplog.at_level(logging.INFO):
        service.initialize()

    captured = capsys.readouterr()
    progress_record = next(
        record for record in caplog.records if record.message == "Lifecycle runtime build progress"
    )

    assert captured.out == ""
    assert "Lifecycle runtime build progress" in caplog.text
    assert progress_record.data["progress_line"] == "building layer"


def test_lifecycle_service_defaults_to_local_process_backend(tmp_path: Path) -> None:
    service = LifecycleService(project_root=tmp_path)

    assert service.backend.__class__.__name__ == "LocalProcessExecutionBackend"
