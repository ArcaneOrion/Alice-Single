"""
生命周期服务

管理应用的启动、运行和关闭生命周期。
"""

import logging
import subprocess
import time
from pathlib import Path
from typing import Optional
from uuid import uuid4

from backend.alice.infrastructure.docker.config import DockerConfig, ContainerStatus


logger = logging.getLogger(__name__)


class LifecycleService:
    """生命周期服务

    负责：
    - Docker 环境初始化
    - 容器管理
    - 资源清理
    """

    def __init__(
        self,
        docker_config: Optional[DockerConfig] = None,
        project_root: Optional[Path] = None,
    ):
        """初始化生命周期服务

        Args:
            docker_config: Docker 配置
            project_root: 项目根目录
        """
        self.docker_config = docker_config or DockerConfig()
        self.project_root = project_root or Path.cwd()
        self._initialized = False
        self._container_running = False

    def _build_log_context(self, phase: str) -> dict:
        return {
            "trace_id": "",
            "request_id": "",
            "task_id": "",
            "session_id": "",
            "span_id": f"lifecycle.{phase}.{uuid4().hex[:8]}",
            "component": "lifecycle_service",
            "phase": phase,
        }

    def _log_event(
        self,
        *,
        event_type: str,
        message: str,
        phase: str,
        data: Optional[dict] = None,
        error: Optional[dict] = None,
        level: str = "info",
        log_category: str = "system",
    ) -> None:
        context = self._build_log_context(phase=phase)
        payload_data = dict(data or {})
        payload_data.setdefault("timing", {"duration_ms": 0})
        extra = {
            "event_type": event_type,
            "log_category": log_category,
            "task_id": context["task_id"],
            "context": context,
            "data": payload_data,
        }
        if error is not None:
            extra["error"] = error

        if level == "warning":
            logger.warning(message, extra=extra)
        elif level == "error":
            logger.error(message, extra=extra)
        else:
            logger.info(message, extra=extra)

    def _log_command_prepared(self, phase: str, command: list[str]) -> None:
        self._log_event(
            event_type="executor.command_prepared",
            message="Lifecycle prepared docker command",
            phase=phase,
            log_category="system",
            data={
                "command": command,
                "command_preview": " ".join(command),
                "execution_environment": "host",
            },
        )

    def _log_command_result(
        self,
        phase: str,
        command: list[str],
        *,
        returncode: int,
        stdout: str = "",
        stderr: str = "",
        duration_ms: int,
        level: str = "info",
        error: Optional[dict] = None,
    ) -> None:
        self._log_event(
            event_type="executor.command_result",
            message="Lifecycle docker command completed",
            phase=phase,
            level=level,
            log_category="system",
            data={
                "command": command,
                "command_preview": " ".join(command),
                "execution_environment": "host",
                "status": "success" if returncode == 0 else "failure",
                "success": returncode == 0,
                "exit_code": returncode,
                "stdout_length": len(stdout or ""),
                "stderr_length": len(stderr or ""),
                "timing": {"duration_ms": duration_ms},
            },
            error=error,
        )

    def initialize(self) -> None:
        """初始化应用生命周期

        确保 Docker 环境就绪。
        """
        if self._initialized:
            logger.debug("生命周期服务已初始化")
            return

        init_started_at = time.monotonic()
        self._log_event(
            event_type="system.start",
            message="Lifecycle initialization started",
            phase="initialize",
            data={
                "docker_image": self.docker_config.image_name,
                "container_name": self.docker_config.container.name,
                "project_root": str(self.project_root),
            },
        )

        try:
            # 1. 检查 Docker 引擎
            self._check_docker_engine()

            # 2. 检查并构建镜像
            self._ensure_docker_image()

            # 3. 启动常驻容器
            self._ensure_container_running()

            self._initialized = True
            self._log_event(
                event_type="system.start",
                message="Lifecycle initialization completed",
                phase="initialize",
                data={
                    "docker_image": self.docker_config.image_name,
                    "container_name": self.docker_config.container.name,
                    "timing": {
                        "duration_ms": int((time.monotonic() - init_started_at) * 1000)
                    },
                },
            )
        except Exception as e:
            self._log_event(
                event_type="system.alert",
                message="Lifecycle initialization failed",
                phase="initialize",
                level="error",
                data={
                    "docker_image": self.docker_config.image_name,
                    "container_name": self.docker_config.container.name,
                    "timing": {
                        "duration_ms": int((time.monotonic() - init_started_at) * 1000)
                    },
                },
                error={
                    "type": type(e).__name__,
                    "message": str(e),
                },
            )
            raise

    def _check_docker_engine(self) -> None:
        """检查 Docker 引擎是否可用"""
        command = ["docker", "--version"]
        started_at = time.monotonic()
        self._log_command_prepared("check_docker_engine", command)
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True,
            )
            self._log_command_result(
                "check_docker_engine",
                command,
                returncode=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                duration_ms=int((time.monotonic() - started_at) * 1000),
            )
        except subprocess.CalledProcessError:
            self._log_command_result(
                "check_docker_engine",
                command,
                returncode=1,
                duration_ms=int((time.monotonic() - started_at) * 1000),
                level="warning",
                error={
                    "type": "CalledProcessError",
                    "message": "Docker engine not available",
                },
            )
            raise RuntimeError(
                "Docker 引擎未检测到。Alice 需要 Docker 环境来确保执行安全与持久化。"
            )
        except FileNotFoundError:
            self._log_event(
                event_type="system.alert",
                message="Docker command not found",
                phase="check_docker_engine",
                level="error",
                error={
                    "type": "FileNotFoundError",
                    "message": "Docker 命令未找到，请确保 Docker 已安装。",
                },
            )
            raise RuntimeError("Docker 命令未找到，请确保 Docker 已安装。")

    def _ensure_docker_image(self) -> None:
        """确保 Docker 镜像存在"""
        command = [
            "docker",
            "image",
            "inspect",
            self.docker_config.image_name,
        ]
        started_at = time.monotonic()
        self._log_command_prepared("check_docker_image", command)
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
        )
        self._log_command_result(
            "check_docker_image",
            command,
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            duration_ms=int((time.monotonic() - started_at) * 1000),
            level="info" if result.returncode == 0 else "warning",
        )

        if result.returncode != 0:
            self._build_docker_image()

    def _build_docker_image(self) -> None:
        """构建 Docker 镜像"""
        dockerfile_path = self.docker_config.dockerfile_full_path

        if not dockerfile_path.exists():
            self._log_event(
                event_type="system.alert",
                message="Dockerfile missing for lifecycle build",
                phase="build_docker_image",
                level="error",
                error={
                    "type": "DOCKERFILE_MISSING",
                    "message": f"Dockerfile 不存在: {dockerfile_path}",
                },
            )
            raise RuntimeError(f"Dockerfile 不存在: {dockerfile_path}")

        build_cmd = [
            "docker",
            "build",
            "-t",
            self.docker_config.image_name,
            "-f",
            str(dockerfile_path),
            str(self.project_root),
        ]

        build_started_at = time.monotonic()
        self._log_command_prepared("build_docker_image", build_cmd)

        process = subprocess.Popen(
            build_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=str(self.project_root),
        )

        # 实时输出构建日志
        log_lines = 0
        log_chars = 0
        for line in process.stdout:
            log_lines += 1
            log_chars += len(line)
            logger.debug(f"[Docker Build] {line.strip()}")

        process.wait()

        if process.returncode != 0:
            self._log_command_result(
                "build_docker_image",
                build_cmd,
                returncode=process.returncode,
                duration_ms=int((time.monotonic() - build_started_at) * 1000),
                level="error",
                error={
                    "type": "DOCKER_BUILD_FAILED",
                    "message": f"Docker 镜像构建失败，退出码: {process.returncode}",
                },
            )
            raise RuntimeError(f"Docker 镜像构建失败，退出码: {process.returncode}")

        self._log_command_result(
            "build_docker_image",
            build_cmd,
            returncode=process.returncode,
            duration_ms=int((time.monotonic() - build_started_at) * 1000),
            stdout=f"build_log_lines={log_lines};build_log_chars={log_chars}",
        )

    def _ensure_container_running(self) -> None:
        """确保容器正在运行"""
        check_started_at = time.monotonic()
        status = self._get_container_status()
        self._log_event(
            event_type="executor.command_result",
            message="Lifecycle resolved container status",
            phase="check_container_status",
            data={
                "container_name": self.docker_config.container.name,
                "container_exists": status.exists,
                "container_running": status.running,
                "status_raw": status.status_raw,
                "timing": {"duration_ms": int((time.monotonic() - check_started_at) * 1000)},
            },
            log_category="system",
        )

        if not status.exists:
            # 创建并启动新容器
            self._create_and_start_container()
        elif not status.running:
            # 启动已存在的容器
            self._start_container()
        else:
            self._container_running = True

    def _get_container_status(self) -> ContainerStatus:
        """获取容器状态"""
        command = [
            "docker",
            "ps",
            "-a",
            "--filter",
            f"name={self.docker_config.container.name}",
            "--format",
            "{{.Status}}",
        ]
        started_at = time.monotonic()
        self._log_command_prepared("inspect_container_status", command)
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
        )
        self._log_command_result(
            "inspect_container_status",
            command,
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            duration_ms=int((time.monotonic() - started_at) * 1000),
        )

        return ContainerStatus.from_docker_output(result.stdout)

    def _create_and_start_container(self) -> None:
        """创建并启动新容器"""
        # 确保挂载目录存在
        for mount in self.docker_config.default_mounts:
            mount.host_path.mkdir(parents=True, exist_ok=True)

        cmd = [
            "docker",
            "run",
            "-d",
            "--name",
            self.docker_config.container.name,
            self.docker_config.container.restart_policy_spec,
        ]

        # 添加挂载
        for mount in self.docker_config.default_mounts:
            cmd.extend(["-v", mount.mount_spec])

        # 添加工作目录和镜像
        cmd.extend(["-w", self.docker_config.container.work_dir])
        cmd.append(self.docker_config.image_name)
        cmd.extend(self.docker_config.container.keep_alive_command)

        started_at = time.monotonic()
        self._log_command_prepared("create_and_start_container", cmd)
        subprocess.run(cmd, check=True)
        self._log_command_result(
            "create_and_start_container",
            cmd,
            returncode=0,
            duration_ms=int((time.monotonic() - started_at) * 1000),
        )

        self._container_running = True

    def _start_container(self) -> None:
        """启动已存在的容器"""
        command = ["docker", "start", self.docker_config.container.name]
        started_at = time.monotonic()
        self._log_command_prepared("start_container", command)

        subprocess.run(
            command,
            check=True,
        )
        self._log_command_result(
            "start_container",
            command,
            returncode=0,
            duration_ms=int((time.monotonic() - started_at) * 1000),
        )

        self._container_running = True

    def stop_container(self) -> None:
        """停止容器"""
        if not self._container_running:
            return

        command = ["docker", "stop", self.docker_config.container.name]
        started_at = time.monotonic()
        self._log_command_prepared("stop_container", command)

        result = subprocess.run(command, capture_output=True, text=True)
        self._log_command_result(
            "stop_container",
            command,
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            duration_ms=int((time.monotonic() - started_at) * 1000),
            level="info" if result.returncode == 0 else "warning",
        )

        self._container_running = False

    def remove_container(self) -> None:
        """删除容器"""
        status = self._get_container_status()
        if not status.exists:
            return

        if status.running:
            self.stop_container()

        command = ["docker", "rm", self.docker_config.container.name]
        started_at = time.monotonic()
        self._log_command_prepared("remove_container", command)
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
        )
        self._log_command_result(
            "remove_container",
            command,
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            duration_ms=int((time.monotonic() - started_at) * 1000),
            level="info" if result.returncode == 0 else "warning",
        )

    def shutdown(self) -> None:
        """关闭应用，清理资源"""
        shutdown_started_at = time.monotonic()
        self._log_event(
            event_type="system.shutdown",
            message="Lifecycle shutdown started",
            phase="shutdown",
        )

        # 注意：我们不删除容器，保持容器持久化
        # 只是在需要时停止

        self._initialized = False
        self._log_event(
            event_type="system.shutdown",
            message="Lifecycle shutdown completed",
            phase="shutdown",
            data={
                "container_running": self._container_running,
                "timing": {"duration_ms": int((time.monotonic() - shutdown_started_at) * 1000)},
            },
        )

    @property
    def is_initialized(self) -> bool:
        """是否已初始化"""
        return self._initialized

    @property
    def is_container_running(self) -> bool:
        """容器是否在运行"""
        return self._container_running

    def get_container_info(self) -> dict:
        """获取容器信息

        Returns:
            容器信息字典
        """
        status = self._get_container_status()

        return {
            "name": self.docker_config.container.name,
            "image": self.docker_config.image_name,
            "exists": status.exists,
            "running": status.running,
            "status_raw": status.status_raw,
        }


__all__ = ["LifecycleService"]
