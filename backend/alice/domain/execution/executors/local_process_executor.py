"""
本地进程执行器

用于单容器 runtime 内直接执行 bash / python 命令，
避免在容器内再次依赖 docker exec。
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from ..models.command import Command, CommandType, ExecutionEnvironment
from ..models.execution_result import ExecutionResult, ExecutionStatus
from ..models.security_rule import DEFAULT_SECURITY_RULES
from .base import BaseExecutor, ExecutionBackend, ExecutionBackendStatus


class LocalProcessExecutionBackend:
    """在当前运行环境内直接执行命令的 backend。"""

    def __init__(self, work_dir: str | Path, timeout: int = 120) -> None:
        self.work_dir = str(work_dir)
        self.timeout = timeout
        self._interrupted = False

    def ensure_ready(
        self,
        *,
        force_rebuild: bool = False,
        on_build_progress: Any = None,
    ) -> ExecutionBackendStatus:
        del force_rebuild, on_build_progress
        return self.status()

    def exec(
        self,
        command: Command,
        *,
        log_context: dict[str, Any] | None = None,
    ) -> ExecutionResult:
        del log_context
        if self._interrupted:
            self._interrupted = False
            return ExecutionResult.error_result(
                "执行被用户中断",
                status=ExecutionStatus.INTERRUPTED,
            )

        started_at = time.monotonic()
        run_command = self._build_command(command)
        working_dir = command.working_dir or self.work_dir

        try:
            result = subprocess.run(
                run_command,
                shell=False,
                capture_output=True,
                text=True,
                timeout=command.timeout,
                cwd=working_dir,
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult.timeout_result(command.timeout)

        execution_result = ExecutionResult.from_subprocess(
            stdout=result.stdout,
            stderr=result.stderr,
            returncode=result.returncode,
            execution_time=time.monotonic() - started_at,
        )
        execution_result.metadata.update(
            {
                "execution_environment": ExecutionEnvironment.CONTAINER.value,
                "working_dir": working_dir,
            }
        )
        return execution_result

    def status(self) -> ExecutionBackendStatus:
        return ExecutionBackendStatus(
            engine_ready=True,
            image_ready=True,
            container_exists=True,
            container_running=True,
            status_raw="running",
        )

    def interrupt(self) -> bool:
        self._interrupted = True
        return True

    def cleanup(self, *, remove: bool = False, force: bool = False) -> bool:
        del remove, force
        return True

    @staticmethod
    def _build_command(command: Command) -> list[str]:
        if command.type == CommandType.PYTHON:
            return [sys.executable, "-c", command.raw]
        return ["bash", "-lc", command.raw]


class LocalProcessExecutor(BaseExecutor):
    """单容器 runtime 内的本地进程执行器。"""

    environment_name = ExecutionEnvironment.CONTAINER.value
    execution_phase = "container_execute"

    def __init__(
        self,
        work_dir: str | Path = ".",
        default_timeout: int = 120,
        backend: ExecutionBackend | None = None,
    ) -> None:
        super().__init__()
        self.work_dir = str(work_dir)
        self.default_timeout = default_timeout
        self.backend = backend or LocalProcessExecutionBackend(
            work_dir=self.work_dir,
            timeout=default_timeout,
        )

        for rule in DEFAULT_SECURITY_RULES:
            self.add_security_rule(rule)

    def execute(
        self,
        command: str,
        is_python_code: bool = False,
        log_context: dict | None = None,
    ) -> ExecutionResult:
        del log_context
        return super().execute(command, is_python_code=is_python_code)

    def _do_execute(self, command: Command) -> ExecutionResult:
        local_command = Command(
            raw=command.raw,
            type=command.type,
            environment=command.environment,
            working_dir=self.work_dir,
            timeout=self.default_timeout,
        )
        return self.backend.exec(local_command)

    def _get_environment(self) -> ExecutionEnvironment:
        return ExecutionEnvironment.CONTAINER

    def interrupt(self) -> bool:
        super().interrupt()
        return self.backend.interrupt()


__all__ = [
    "LocalProcessExecutionBackend",
    "LocalProcessExecutor",
]
