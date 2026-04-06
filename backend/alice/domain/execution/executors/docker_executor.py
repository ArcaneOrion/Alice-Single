"""
Docker 执行器

实现在 Docker 容器中执行命令的逻辑。
"""

import logging
import time
import traceback
from typing import Optional
from uuid import uuid4

from backend.alice.infrastructure.docker.config import ContainerConfig, DockerConfig
from backend.alice.infrastructure.docker.container_manager import DockerExecutionBackend

from .base import BaseExecutor, ExecutionBackend
from ..models.command import Command, CommandType, ExecutionEnvironment
from ..models.execution_result import ExecutionResult, ExecutionStatus
from ..models.security_rule import DEFAULT_SECURITY_RULES

logger = logging.getLogger(__name__)


def _command_preview(command: str, limit: int = 160) -> str:
    """生成安全的命令预览（单行、限长）"""
    normalized = " ".join(command.split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit]}..."


class DockerExecutor(BaseExecutor):
    """Docker 容器命令执行器

    在常驻 Docker 容器中执行命令，提供安全隔离环境。
    """

    def __init__(
        self,
        container_name: str = "alice-sandbox-instance",
        docker_image: str = "alice-sandbox:latest",
        work_dir: str = "/app",
        default_timeout: int = 120,
        backend: Optional[ExecutionBackend] = None,
        docker_config: Optional[DockerConfig] = None,
    ):
        super().__init__()

        config = self._resolve_docker_config(
            container_name=container_name,
            docker_image=docker_image,
            work_dir=work_dir,
            backend=backend,
            docker_config=docker_config,
        )

        self.backend = backend or DockerExecutionBackend(config)
        self.container_name = config.container.name
        self.docker_image = config.image_name
        self.work_dir = config.container.work_dir
        self.default_timeout = default_timeout
        self._active_log_context: dict | None = None

        for rule in DEFAULT_SECURITY_RULES:
            self.add_security_rule(rule)

    @staticmethod
    def _resolve_docker_config(
        *,
        container_name: str,
        docker_image: str,
        work_dir: str,
        backend: Optional[ExecutionBackend],
        docker_config: Optional[DockerConfig],
    ) -> DockerConfig:
        if docker_config is not None:
            return docker_config

        backend_config = getattr(backend, "config", None)
        if isinstance(backend_config, DockerConfig):
            return backend_config

        return DockerConfig(
            image_name=docker_image,
            container=ContainerConfig(name=container_name, work_dir=work_dir),
        )

    def _build_log_context(self, phase: str) -> dict:
        base = dict(self._active_log_context or {})
        trace_id = str(base.get("trace_id") or base.get("request_id") or "")
        request_id = str(base.get("request_id") or trace_id)
        session_id = str(base.get("session_id") or "")
        task_id = str(base.get("task_id") or request_id or session_id)
        span_root = str(base.get("span_id") or f"executor.{uuid4().hex[:10]}")

        return {
            "trace_id": trace_id,
            "request_id": request_id,
            "task_id": task_id,
            "session_id": session_id,
            "span_id": f"{span_root}.{phase}",
            "component": "docker_executor",
            "phase": phase,
            "executor": "docker",
        }

    def _log_executor_event(
        self,
        *,
        event_type: str,
        phase: str,
        message: str,
        data: Optional[dict] = None,
        error: Optional[dict] = None,
        level: str = "info",
        legacy_event_type: str = "",
        with_exc_info: bool = False,
    ) -> None:
        context = self._build_log_context(phase=phase)
        payload_data = dict(data or {})
        if legacy_event_type:
            payload_data["legacy_event_type"] = legacy_event_type
        payload_data.setdefault("timing", {"duration_ms": 0})

        extra = {
            "event_type": event_type,
            "log_category": "tasks",
            "task_id": context["task_id"],
            "context": context,
            "data": payload_data,
        }
        if error is not None:
            extra["error"] = error

        if level == "warning":
            logger.warning(message, extra=extra)
        elif level == "error":
            logger.error(message, exc_info=with_exc_info, extra=extra)
        else:
            logger.info(message, extra=extra)

    def execute(
        self,
        command: str,
        is_python_code: bool = False,
        log_context: Optional[dict] = None,
    ) -> ExecutionResult:
        self._active_log_context = dict(log_context or {})
        try:
            cmd_type = CommandType.PYTHON if is_python_code else CommandType.BASH
            cmd = Command(
                raw=command,
                type=cmd_type,
                environment=self._get_environment(),
            )

            is_safe, warning = self.validate(command)
            if not is_safe:
                return ExecutionResult.blocked_result(warning)

            return self._do_execute(cmd)
        finally:
            self._active_log_context = None

    def _get_environment(self) -> ExecutionEnvironment:
        return ExecutionEnvironment.DOCKER

    def _do_execute(self, command: Command) -> ExecutionResult:
        started_at = time.monotonic()
        preview = _command_preview(command.raw)

        try:
            backend_command = Command(
                raw=command.raw,
                type=command.type,
                environment=command.environment,
                working_dir=self.work_dir,
                timeout=self.default_timeout,
            )

            self._log_executor_event(
                event_type="executor.command_prepared",
                phase="command_prepared",
                message="Docker executor prepared command",
                legacy_event_type="tool_call",
                data={
                    "tool_type": command.type.value,
                    "command": command.raw,
                    "command_preview": preview,
                    "command_length": len(command.raw),
                    "execution_environment": command.environment.value,
                    "container_name": self.container_name,
                    "work_dir": self.work_dir,
                    "timeout_seconds": self.default_timeout,
                },
            )

            execution_result = self.backend.exec(
                backend_command,
                log_context=self._active_log_context,
            )
            execution_time = time.monotonic() - started_at

            self._log_executor_event(
                event_type="executor.command_result",
                phase="command_result",
                message="Docker executor completed command",
                legacy_event_type="tool_result",
                data={
                    "tool_type": command.type.value,
                    "command": command.raw,
                    "command_preview": preview,
                    "status": execution_result.status.value,
                    "success": execution_result.success,
                    "exit_code": execution_result.exit_code,
                    "output_length": len(execution_result.output or ""),
                    "error_length": len(execution_result.error or ""),
                    "timing": {"duration_ms": int(execution_time * 1000)},
                },
                error=(
                    None
                    if execution_result.success
                    else {
                        "type": execution_result.status.value.upper(),
                        "message": execution_result.error or "Command execution failed",
                    }
                ),
                level="info" if execution_result.success else "warning",
            )

            return execution_result

        except Exception as e:
            execution_time = time.monotonic() - started_at
            error_trace = traceback.format_exc()
            self._log_executor_event(
                event_type="executor.command_result",
                phase="command_result",
                message="Docker executor command failed",
                level="error",
                with_exc_info=True,
                legacy_event_type="tool_error",
                data={
                    "tool_type": command.type.value,
                    "command": command.raw,
                    "command_preview": preview,
                    "status": "failure",
                    "success": False,
                    "timing": {"duration_ms": int(execution_time * 1000)},
                },
                error={
                    "type": type(e).__name__,
                    "message": str(e),
                    "traceback": error_trace,
                },
            )
            return ExecutionResult(
                success=False,
                output=f"执行过程中出错: {str(e)}",
                status=ExecutionStatus.FAILURE,
                error=str(e),
                execution_time=execution_time,
            )

    def _ensure_docker_environment(self):
        return self.backend.ensure_ready()

    def is_container_ready(self) -> bool:
        try:
            return self.backend.status().container_running
        except Exception:
            return False

    def status(self):
        return self.backend.status()

    def cleanup(self, *, remove: bool = False, force: bool = False) -> bool:
        return self.backend.cleanup(remove=remove, force=force)

    def interrupt(self) -> bool:
        return self.backend.interrupt()


__all__ = ["DockerExecutor"]
