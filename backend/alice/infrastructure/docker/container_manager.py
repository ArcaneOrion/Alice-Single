"""
Docker 容器管理模块

负责容器的创建、启动、停止和状态管理。
"""

import logging
import time
from typing import Any, Callable, List, Optional

from backend.alice.domain.execution.executors.base import ExecutionBackendStatus
from backend.alice.domain.execution.models.command import Command, CommandType
from backend.alice.domain.execution.models.execution_result import ExecutionResult, ExecutionStatus

from .client import DockerClient, DockerClientError
from .config import ContainerStatus, DockerConfig
from .image_builder import ImageBuilder

logger = logging.getLogger(__name__)


class ContainerManagerError(DockerClientError):
    """容器管理异常"""

    pass


class ContainerManager:
    """Docker 容器管理器

    负责容器的全生命周期管理，包括创建、启动、停止等。
    实现常驻容器模式，容器通过 `tail -f /dev/null` 保持运行。
    """

    def __init__(
        self,
        config: DockerConfig,
        client: Optional[DockerClient] = None,
        image_builder: Optional[ImageBuilder] = None,
    ):
        self.config = config
        self.client = client or DockerClient(config)
        self.image_builder = image_builder or ImageBuilder(config, self.client)

    def get_status(self) -> ContainerStatus:
        """获取容器当前状态。"""
        return self.client.get_container_status()

    def is_running(self) -> bool:
        """检查容器是否正在运行。"""
        return self.get_status().running

    def ensure_running(
        self,
        on_build_progress: Optional[Callable[[str], None]] = None,
        force_rebuild: bool = False,
    ) -> bool:
        """确保容器正在运行。"""
        try:
            self.client.check_engine()
        except DockerClientError as e:
            raise ContainerManagerError(f"Docker 引擎检查失败: {e}") from e

        try:
            self.image_builder.ensure_image(
                force_rebuild=force_rebuild,
                on_progress=on_build_progress,
            )
        except DockerClientError as e:
            raise ContainerManagerError(f"镜像准备失败: {e}") from e

        status = self.get_status()
        if not status.exists:
            return self._create_and_start()
        if not status.running:
            return self._start_existing()

        logger.info("容器已在运行中")
        return True

    def _ensure_mount_directories(self) -> None:
        """确保挂载点目录存在。"""
        for mount in self.config.default_mounts:
            if not mount.host_path.exists():
                logger.info(f"创建挂载目录: {mount.host_path}")
                mount.host_path.mkdir(parents=True, exist_ok=True)

    def _ensure_workspace_permissions(self) -> None:
        """确保 workspace 目录权限为 777，使容器内 alice 用户可写。"""
        workspace_host = self.config.project_root / ".alice" / "workspace"
        if workspace_host.exists():
            import os
            os.chmod(workspace_host, 0o777)
            logger.info("已设置 workspace 目录权限为 777")

    def _create_and_start(self) -> bool:
        """创建并启动新容器。"""
        logger.info("正在初始化 Alice 常驻实验室容器...")
        self._ensure_mount_directories()
        self._ensure_workspace_permissions()
        result = self.client.run_container()

        if not result.success:
            raise ContainerManagerError(
                f"容器创建失败: {result.stderr or result.stdout}"
            )

        logger.info(
            f"容器 {self.config.container.name} 已成功初始化。"
        )
        return True

    def _start_existing(self) -> bool:
        """启动已存在的容器。"""
        logger.info("正在唤醒 Alice 常驻实验室容器...")
        self._ensure_workspace_permissions()
        result = self.client.start_container()

        if not result.success:
            raise ContainerManagerError(
                f"容器启动失败: {result.stderr or result.stdout}"
            )

        logger.info(f"容器 {self.config.container.name} 已成功启动")
        return True

    def start(self) -> bool:
        """启动容器。"""
        status = self.get_status()
        if not status.exists:
            raise ContainerManagerError(
                f"容器 {self.config.container.name} 不存在，请先创建容器"
            )
        if status.running:
            logger.info("容器已在运行中")
            return True
        return self._start_existing()

    def stop(self, timeout: int = 10) -> bool:
        """停止容器。"""
        del timeout
        status = self.get_status()
        if not status.exists or not status.running:
            return True

        logger.info(f"正在停止容器 {self.config.container.name}...")
        result = self.client.stop_container()
        if not result.success:
            logger.warning(f"容器停止失败: {result.stderr or result.stdout}")
            return False

        logger.info(f"容器 {self.config.container.name} 已停止")
        return True

    def restart(self) -> bool:
        """重启容器。"""
        self.stop()
        return self.start()

    def remove(self, force: bool = False) -> bool:
        """删除容器。"""
        status = self.get_status()
        if not status.exists:
            return True

        logger.info(f"正在删除容器 {self.config.container.name}...")
        result = self.client.remove_container(force=force)
        if not result.success:
            logger.warning(f"容器删除失败: {result.stderr or result.stdout}")
            return False

        logger.info(f"容器 {self.config.container.name} 已删除")
        return True

    def exec(self, command: List[str], timeout: Optional[int] = None) -> str:
        """在容器中执行命令。"""
        result = self.client.exec_command(command, timeout=timeout)

        output = result.stdout
        if result.stderr:
            logger.error(f"命令执行产生标准错误: {result.stderr}")
            output += f"\n[标准错误输出]:\n{result.stderr}"

        if result.returncode != 0:
            logger.error(f"命令执行失败，返回码: {result.returncode}")
            output += f"\n[执行失败，退出状态码: {result.returncode}]"

        return output if output else "[命令执行成功，无回显内容]"

    def exec_bash(self, command: str, timeout: Optional[int] = None) -> str:
        """在容器中执行 Bash 命令。"""
        return self.exec(["bash", "-c", command], timeout=timeout)

    def exec_python(self, code: str, timeout: Optional[int] = None) -> str:
        """在容器中执行 Python 代码。"""
        return self.exec(["python3", "-c", code], timeout=timeout)


class DockerExecutionBackend:
    """统一 Docker execution backend。"""

    def __init__(
        self,
        config: DockerConfig,
        client: Optional[DockerClient] = None,
        image_builder: Optional[ImageBuilder] = None,
        container_manager: Optional[ContainerManager] = None,
    ):
        self.config = config
        self.client = client or DockerClient(config)
        self.image_builder = image_builder or ImageBuilder(config, self.client)
        self.container_manager = container_manager or ContainerManager(
            config,
            client=self.client,
            image_builder=self.image_builder,
        )
        self._interrupted = False

    def ensure_ready(
        self,
        *,
        force_rebuild: bool = False,
        on_build_progress: Optional[Callable[[str], None]] = None,
    ) -> ExecutionBackendStatus:
        self.container_manager.ensure_running(
            on_build_progress=on_build_progress,
            force_rebuild=force_rebuild,
        )
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

        self.ensure_ready()
        started_at = time.monotonic()

        try:
            result = self.client.exec_command(
                self._to_exec_command(command),
                timeout=command.timeout,
            )
        except DockerClientError as e:
            message = str(e)
            if "超时" in message or "timeout" in message.lower():
                return ExecutionResult.timeout_result(command.timeout)
            return ExecutionResult.error_result(message, status=ExecutionStatus.FAILURE)

        return ExecutionResult.from_subprocess(
            stdout=result.stdout,
            stderr=result.stderr,
            returncode=result.returncode,
            execution_time=time.monotonic() - started_at,
        )

    def status(self) -> ExecutionBackendStatus:
        try:
            engine_ready = self.client.check_engine()
        except DockerClientError:
            return ExecutionBackendStatus(
                engine_ready=False,
                image_ready=False,
                container_exists=False,
                container_running=False,
                status_raw="",
            )

        try:
            image_ready = self.client.check_image_exists()
        except DockerClientError:
            image_ready = False

        try:
            container_status = self.container_manager.get_status()
        except DockerClientError:
            container_status = ContainerStatus(exists=False, running=False, status_raw="")

        return ExecutionBackendStatus(
            engine_ready=engine_ready,
            image_ready=image_ready,
            container_exists=container_status.exists,
            container_running=container_status.running,
            status_raw=container_status.status_raw,
        )

    def interrupt(self) -> bool:
        self._interrupted = True
        return True

    def cleanup(self, *, remove: bool = False, force: bool = False) -> bool:
        if remove:
            return self.container_manager.remove(force=force)
        return self.container_manager.stop()

    @staticmethod
    def _to_exec_command(command: Command) -> List[str]:
        if command.type == CommandType.PYTHON:
            return ["python3", "-c", command.raw]
        return ["bash", "-c", command.raw]


__all__ = [
    "ContainerManager",
    "ContainerManagerError",
    "DockerExecutionBackend",
]
