"""
Docker 执行器

实现在 Docker 容器中执行命令的逻辑
"""

import logging
import os
import subprocess
import time
import traceback
from typing import Optional
from uuid import uuid4

from .base import BaseExecutor
from ..models.command import Command, ExecutionEnvironment
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

    在常驻 Docker 容器中执行命令，提供安全隔离环境
    """

    def __init__(
        self,
        container_name: str = "alice-sandbox-instance",
        docker_image: str = "alice-sandbox:latest",
        work_dir: str = "/app",
        default_timeout: int = 120
    ):
        super().__init__()
        self.container_name = container_name
        self.docker_image = docker_image
        self.work_dir = work_dir
        self.default_timeout = default_timeout
        self._docker_environment_ready = False
        self._active_log_context: dict | None = None

        # 加载默认安全规则
        for rule in DEFAULT_SECURITY_RULES:
            self.add_security_rule(rule)

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
            return super().execute(command, is_python_code=is_python_code)
        finally:
            self._active_log_context = None

    def _get_environment(self):
        """获取执行环境"""
        return ExecutionEnvironment.DOCKER

    def _do_execute(self, command: Command) -> ExecutionResult:
        """实际执行命令

        Args:
            command: 命令对象

        Returns:
            ExecutionResult: 执行结果
        """
        started_at = time.monotonic()
        preview = _command_preview(command.raw)

        try:
            if not self._docker_environment_ready:
                self._ensure_docker_environment()

            full_command = self._build_docker_command(command)

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
                    "docker_command": full_command,
                    "execution_environment": command.environment.value,
                    "container_name": self.container_name,
                    "work_dir": self.work_dir,
                    "timeout_seconds": self.default_timeout,
                },
            )

            result = subprocess.run(
                full_command,
                shell=False,  # 核心修复：禁用宿主机 Shell 解析
                capture_output=True,
                text=True,
                timeout=self.default_timeout,
                env=os.environ
            )

            execution_time = time.monotonic() - started_at
            execution_result = ExecutionResult.from_subprocess(
                stdout=result.stdout,
                stderr=result.stderr,
                returncode=result.returncode,
                execution_time=execution_time
            )

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
                    "stdout_length": len(result.stdout or ""),
                    "stderr_length": len(result.stderr or ""),
                    "output_length": len(execution_result.output or ""),
                    "error_length": len(execution_result.error or ""),
                    "timing": {"duration_ms": int(execution_time * 1000)},
                },
            )

            return execution_result

        except subprocess.TimeoutExpired:
            self._log_executor_event(
                event_type="executor.command_result",
                phase="command_result",
                message="Docker executor command timed out",
                level="warning",
                legacy_event_type="tool_timeout",
                data={
                    "tool_type": command.type.value,
                    "command": command.raw,
                    "command_preview": preview,
                    "status": "timeout",
                    "success": False,
                    "timeout_seconds": self.default_timeout,
                    "timing": {"duration_ms": int((time.monotonic() - started_at) * 1000)},
                },
                error={
                    "type": "TimeoutExpired",
                    "message": f"Command execution timeout after {self.default_timeout} seconds",
                },
            )
            return ExecutionResult.timeout_result(self.default_timeout)

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
                execution_time=execution_time
            )

    def _build_docker_command(self, command: Command) -> list[str]:
        """构建 Docker exec 命令

        Args:
            command: 命令对象

        Returns:
            list[str]: Docker 命令列表
        """
        full_command = [
            "docker", "exec",
            "-w", self.work_dir,
            self.container_name
        ]

        if command.type.value == "python":
            full_command.extend(["python3", "-c", command.raw])
        else:
            full_command.extend(["bash", "-c", command.raw])

        return full_command

    def _ensure_docker_environment(self) -> None:
        """确保 Docker 环境就绪

        实现 Docker 引擎检查、镜像构建、容器启动的三阶段初始化
        """
        if self._docker_environment_ready:
            return

        started_at = time.monotonic()

        try:
            # 1. 检查 Docker 引擎
            self._check_docker_engine()

            # 2. 检查并构建镜像
            self._ensure_docker_image()

            # 3. 启动常驻容器
            self._ensure_container_running()
            self._docker_environment_ready = True
            self._log_executor_event(
                event_type="executor.command_result",
                phase="environment_ready",
                message="Docker execution environment is ready",
                data={
                    "status": "success",
                    "success": True,
                    "container_name": self.container_name,
                    "docker_image": self.docker_image,
                    "timing": {"duration_ms": int((time.monotonic() - started_at) * 1000)},
                },
            )

        except Exception as e:
            self._log_executor_event(
                event_type="executor.command_result",
                phase="environment_ready",
                message="Docker environment initialization failed",
                level="error",
                with_exc_info=True,
                legacy_event_type="tool_error",
                data={
                    "status": "failure",
                    "success": False,
                    "container_name": self.container_name,
                    "docker_image": self.docker_image,
                    "timing": {"duration_ms": int((time.monotonic() - started_at) * 1000)},
                },
                error={
                    "type": type(e).__name__,
                    "message": str(e),
                    "traceback": traceback.format_exc(),
                },
            )
            raise

    def _check_docker_engine(self) -> None:
        """检查 Docker 引擎是否可用"""
        command = "docker --version"
        started_at = time.monotonic()
        self._log_executor_event(
            event_type="executor.command_prepared",
            phase="check_docker_engine",
            message="Checking docker engine",
            data={
                "command": command,
                "execution_environment": "host",
            },
        )
        res = subprocess.run(
            command,
            shell=True,
            capture_output=True
        )
        duration_ms = int((time.monotonic() - started_at) * 1000)
        if res.returncode == 0:
            self._log_executor_event(
                event_type="executor.command_result",
                phase="check_docker_engine",
                message="Docker engine check succeeded",
                data={
                    "command": command,
                    "status": "success",
                    "success": True,
                    "exit_code": res.returncode,
                    "stdout_length": len(res.stdout or b""),
                    "stderr_length": len(res.stderr or b""),
                    "timing": {"duration_ms": duration_ms},
                },
            )
        else:
            self._log_executor_event(
                event_type="executor.command_result",
                phase="check_docker_engine",
                message="Docker engine check failed",
                level="warning",
                data={
                    "command": command,
                    "status": "failure",
                    "success": False,
                    "exit_code": res.returncode,
                    "stdout_length": len(res.stdout or b""),
                    "stderr_length": len(res.stderr or b""),
                    "timing": {"duration_ms": duration_ms},
                },
            )
        if res.returncode != 0:
            raise RuntimeError("系统未检测到 Docker。Alice 需要 Docker 环境来确保执行安全与持久化。")

    def _ensure_docker_image(self) -> None:
        """确保 Docker 镜像存在"""
        command = f"docker image inspect {self.docker_image}"
        started_at = time.monotonic()
        self._log_executor_event(
            event_type="executor.command_prepared",
            phase="check_docker_image",
            message="Checking docker image",
            data={
                "command": command,
                "docker_image": self.docker_image,
                "execution_environment": "host",
            },
        )
        res = subprocess.run(
            command,
            shell=True,
            capture_output=True
        )
        duration_ms = int((time.monotonic() - started_at) * 1000)
        self._log_executor_event(
            event_type="executor.command_result",
            phase="check_docker_image",
            message="Docker image check completed",
            level="info" if res.returncode == 0 else "warning",
            data={
                "command": command,
                "docker_image": self.docker_image,
                "status": "success" if res.returncode == 0 else "failure",
                "success": res.returncode == 0,
                "exit_code": res.returncode,
                "stdout_length": len(res.stdout or b""),
                "stderr_length": len(res.stderr or b""),
                "timing": {"duration_ms": duration_ms},
            },
        )

        if res.returncode != 0:
            raise RuntimeError(
                f"Docker 镜像 {self.docker_image} 不存在。"
                f"请先运行: docker build -t {self.docker_image} -f Dockerfile.sandbox ."
            )

    def _ensure_container_running(self) -> None:
        """确保容器正在运行"""
        status_command = (
            f"docker ps -a --filter name={self.container_name} --format '{{{{.Status}}}}'"
        )
        started_at = time.monotonic()
        self._log_executor_event(
            event_type="executor.command_prepared",
            phase="check_container_status",
            message="Checking docker container status",
            data={
                "command": status_command,
                "container_name": self.container_name,
                "execution_environment": "host",
            },
        )
        res = subprocess.run(
            status_command,
            shell=True,
            capture_output=True,
            text=True
        )
        status = res.stdout.lower()
        self._log_executor_event(
            event_type="executor.command_result",
            phase="check_container_status",
            message="Docker container status resolved",
            data={
                "command": status_command,
                "container_name": self.container_name,
                "status_text": status.strip(),
                "success": res.returncode == 0,
                "exit_code": res.returncode,
                "stdout_length": len(res.stdout or ""),
                "stderr_length": len(res.stderr or ""),
                "timing": {"duration_ms": int((time.monotonic() - started_at) * 1000)},
            },
        )

        if not status:
            # 容器不存在，需要启动
            print(f"[系统]: 正在初始化 Alice 常驻实验室容器...")
            start_cmd = [
                "docker", "run", "-d",
                "--name", self.container_name,
                "--restart", "always",
                "-w", "/app",
                self.docker_image,
                "tail", "-f", "/dev/null"
            ]
            start_command = " ".join(start_cmd)
            start_started_at = time.monotonic()
            self._log_executor_event(
                event_type="executor.command_prepared",
                phase="start_container",
                message="Creating and starting persistent container",
                data={
                    "command": start_command,
                    "container_name": self.container_name,
                    "docker_image": self.docker_image,
                    "execution_environment": "host",
                },
            )
            subprocess.run(start_command, shell=True, check=True)
            self._log_executor_event(
                event_type="executor.command_result",
                phase="start_container",
                message="Persistent container created and started",
                data={
                    "command": start_command,
                    "container_name": self.container_name,
                    "status": "success",
                    "success": True,
                    "timing": {"duration_ms": int((time.monotonic() - start_started_at) * 1000)},
                },
            )
            print(f"[系统]: 容器已成功初始化。")

        elif "up" not in status:
            # 容器存在但未运行
            print(f"[系统]: 正在唤醒 Alice 常驻实验室容器...")
            wake_command = f"docker start {self.container_name}"
            wake_started_at = time.monotonic()
            self._log_executor_event(
                event_type="executor.command_prepared",
                phase="start_container",
                message="Starting existing persistent container",
                data={
                    "command": wake_command,
                    "container_name": self.container_name,
                    "execution_environment": "host",
                },
            )
            subprocess.run(wake_command, shell=True, check=True)
            self._log_executor_event(
                event_type="executor.command_result",
                phase="start_container",
                message="Persistent container started",
                data={
                    "command": wake_command,
                    "container_name": self.container_name,
                    "status": "success",
                    "success": True,
                    "timing": {"duration_ms": int((time.monotonic() - wake_started_at) * 1000)},
                },
            )

    def is_container_ready(self) -> bool:
        """检查容器是否就绪"""
        try:
            res = subprocess.run(
                f"docker inspect -f '{{{{.State.Running}}}}' {self.container_name}",
                shell=True,
                capture_output=True,
                text=True
            )
            return res.stdout.strip() == "true"
        except Exception:
            return False


__all__ = [
    "DockerExecutor",
]
