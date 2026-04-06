"""
生命周期服务

管理应用的启动、运行和关闭生命周期。
"""

import logging
import time
from pathlib import Path
from uuid import uuid4

from backend.alice.domain.execution.executors.base import ExecutionBackend
from backend.alice.infrastructure.docker.config import DockerConfig
from backend.alice.infrastructure.docker.container_manager import DockerExecutionBackend

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
        docker_config: DockerConfig | None = None,
        project_root: Path | None = None,
        backend: ExecutionBackend | None = None,
    ):
        self.docker_config = self._resolve_docker_config(
            docker_config=docker_config,
            project_root=project_root,
            backend=backend,
        )
        self.project_root = self.docker_config.project_root
        self.backend = backend or DockerExecutionBackend(self.docker_config)
        self._initialized = False
        self._container_running = False

    @staticmethod
    def _resolve_docker_config(
        *,
        docker_config: DockerConfig | None,
        project_root: Path | None,
        backend: ExecutionBackend | None,
    ) -> DockerConfig:
        if docker_config is not None:
            return docker_config

        backend_config = getattr(backend, "config", None)
        if isinstance(backend_config, DockerConfig):
            return backend_config

        if project_root is not None:
            return DockerConfig(project_root=project_root)

        return DockerConfig()

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
        data: dict | None = None,
        error: dict | None = None,
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

    def _log_build_progress(self, line: str) -> None:
        self._log_event(
            event_type="system.start",
            message="Lifecycle docker build progress",
            phase="build_docker_image",
            data={
                "docker_image": self.docker_config.image_name,
                "progress_line": line,
            },
        )

    def initialize(self) -> None:
        """初始化应用生命周期，确保 Docker 环境就绪。"""
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
            status = self.backend.ensure_ready(on_build_progress=self._log_build_progress)
            self._initialized = True
            self._container_running = status.container_running
            self._log_event(
                event_type="system.start",
                message="Lifecycle initialization completed",
                phase="initialize",
                data={
                    "docker_image": self.docker_config.image_name,
                    "container_name": self.docker_config.container.name,
                    "engine_ready": status.engine_ready,
                    "image_ready": status.image_ready,
                    "container_exists": status.container_exists,
                    "container_running": status.container_running,
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

    def stop_container(self) -> None:
        """停止容器。"""
        if self.backend.cleanup(remove=False):
            self._container_running = False

    def remove_container(self) -> None:
        """删除容器。"""
        self.backend.cleanup(remove=False)
        if self.backend.cleanup(remove=True):
            self._container_running = False

    def shutdown(self) -> None:
        """关闭应用，清理资源。"""
        shutdown_started_at = time.monotonic()
        self._log_event(
            event_type="system.shutdown",
            message="Lifecycle shutdown started",
            phase="shutdown",
        )

        self._initialized = False
        self._container_running = self.backend.status().container_running
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
        """是否已初始化。"""
        return self._initialized

    @property
    def is_container_running(self) -> bool:
        """容器是否在运行。"""
        return self._container_running

    def get_container_info(self) -> dict:
        """获取容器信息。"""
        status = self.backend.status()
        return {
            "name": self.docker_config.container.name,
            "image": self.docker_config.image_name,
            "exists": status.container_exists,
            "running": status.container_running,
            "status_raw": status.status_raw,
        }


__all__ = ["LifecycleService"]
