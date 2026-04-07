from __future__ import annotations

from backend.alice.domain.execution.executors.local_process_executor import (
    LocalProcessExecutionBackend,
    LocalProcessExecutor,
)
from backend.alice.domain.execution.models.command import ExecutionEnvironment


def test_local_process_backend_is_immediately_ready(tmp_path) -> None:
    backend = LocalProcessExecutionBackend(work_dir=str(tmp_path))

    status = backend.ensure_ready()

    assert status.ready is True
    assert status.container_running is True
    assert status.status_raw == "running"


def test_local_process_executor_runs_bash_and_python_commands(tmp_path) -> None:
    backend = LocalProcessExecutionBackend(work_dir=str(tmp_path))
    executor = LocalProcessExecutor(work_dir=str(tmp_path), backend=backend)

    bash_result = executor.execute("echo hello")
    python_result = executor.execute("print('world')", is_python_code=True)

    assert bash_result.success is True
    assert bash_result.output.strip() == "hello"
    assert python_result.success is True
    assert python_result.output.strip() == "world"
    assert executor._get_environment() == ExecutionEnvironment.CONTAINER
