"""
Docker 容器管理模块

负责容器的创建、启动、停止和状态管理。
"""

import logging
import sys
from pathlib import Path
from typing import Optional, List

from .client import DockerClient, DockerClientError
from .config import DockerConfig, ContainerStatus
from .image_builder import ImageBuilder

logger = logging.getLogger(__name__)


class ContainerManagerError(DockerClientError):
    """容器管理异常"""

    pass


class ContainerManager:
    """Docker 容器管理器

    负责容器的全生命周期管理，包括创建、启动、停止等。
    实现常驻容器模式，容器通过 `tail -f /dev/null` 保持运行。

    Args:
        config: Docker 配置
        client: Docker 客户端实例
        image_builder: 镜像构建器实例
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
        """获取容器当前状态

        Returns:
            ContainerStatus: 容器状态
        """
        return self.client.get_container_status()

    def is_running(self) -> bool:
        """检查容器是否正在运行

        Returns:
            bool: 容器是否运行中
        """
        status = self.get_status()
        return status.running

    def ensure_running(
        self,
        on_build_progress: Optional[callable] = None,
    ) -> bool:
        """确保容器正在运行

        这是三阶段初始化的完整流程：
        1. 检查 Docker 引擎
        2. 检查/构建镜像
        3. 检查/启动容器

        Args:
            on_build_progress: 镜像构建进度回调

        Returns:
            bool: 容器是否成功运行

        Raises:
            ContainerManagerError: 容器管理失败
        """
        # 阶段1: 检查 Docker 引擎
        try:
            self.client.check_engine()
        except DockerClientError as e:
            raise ContainerManagerError(f"Docker 引擎检查失败: {e}")

        # 阶段2: 检查/构建镜像
        try:
            self.image_builder.ensure_image(on_progress=on_build_progress)
        except DockerClientError as e:
            raise ContainerManagerError(f"镜像准备失败: {e}")

        # 阶段3: 检查/启动容器
        status = self.get_status()

        if not status.exists:
            return self._create_and_start()
        elif not status.running:
            return self._start_existing()
        else:
            logger.info("容器已在运行中")
            return True

    def _ensure_mount_directories(self) -> None:
        """确保挂载点目录存在

        在创建容器前，确保宿主机的挂载目录都已存在。
        """
        for mount in self.config.default_mounts:
            host_path = mount.host_path
            if not host_path.exists():
                logger.info(f"创建挂载目录: {host_path}")
                host_path.mkdir(parents=True, exist_ok=True)

    def _create_and_start(self) -> bool:
        """创建并启动新容器

        Returns:
            bool: 是否成功
        """
        logger.info(f"正在初始化 Alice 常驻实验室容器 (最小权限隔离模式)...")

        # 确保挂载目录存在
        self._ensure_mount_directories()

        # 创建并启动容器
        result = self.client.run_container()

        if not result.success:
            raise ContainerManagerError(
                f"容器创建失败: {result.stderr or result.stdout}"
            )

        logger.info(
            f"容器 {self.config.container.name} 已成功初始化。"
            "记忆与人设文件已实现物理隔离保护。"
        )
        return True

    def _start_existing(self) -> bool:
        """启动已存在的容器

        Returns:
            bool: 是否成功
        """
        logger.info(f"正在唤醒 Alice 常驻实验室容器...")
        result = self.client.start_container()

        if not result.success:
            raise ContainerManagerError(
                f"容器启动失败: {result.stderr or result.stdout}"
            )

        logger.info(f"容器 {self.config.container.name} 已成功启动")
        return True

    def start(self) -> bool:
        """启动容器

        Returns:
            bool: 是否成功
        """
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
        """停止容器

        Args:
            timeout: 等待容器停止的超时时间（秒）

        Returns:
            bool: 是否成功
        """
        logger.info(f"正在停止容器 {self.config.container.name}...")
        result = self.client.stop_container()

        if not result.success:
            logger.warning(f"容器停止失败: {result.stderr or result.stdout}")
            return False

        logger.info(f"容器 {self.config.container.name} 已停止")
        return True

    def restart(self) -> bool:
        """重启容器

        Returns:
            bool: 是否成功
        """
        self.stop()
        return self.start()

    def remove(self, force: bool = False) -> bool:
        """删除容器

        Args:
            force: 是否强制删除运行中的容器

        Returns:
            bool: 是否成功
        """
        logger.info(f"正在删除容器 {self.config.container.name}...")
        result = self.client.remove_container(force=force)

        if not result.success:
            logger.warning(f"容器删除失败: {result.stderr or result.stdout}")
            return False

        logger.info(f"容器 {self.config.container.name} 已删除")
        return True

    def exec(
        self,
        command: List[str],
        timeout: Optional[int] = None,
    ) -> str:
        """在容器中执行命令

        Args:
            command: 要执行的命令（列表形式）
            timeout: 超时时间（秒）

        Returns:
            str: 命令执行结果
        """
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
        """在容器中执行 Bash 命令

        Args:
            command: 要执行的命令字符串
            timeout: 超时时间（秒）

        Returns:
            str: 命令执行结果
        """
        return self.exec(["bash", "-c", command], timeout=timeout)

    def exec_python(self, code: str, timeout: Optional[int] = None) -> str:
        """在容器中执行 Python 代码

        Args:
            code: Python 代码字符串
            timeout: 超时时间（秒）

        Returns:
            str: 执行结果
        """
        return self.exec(["python3", "-c", code], timeout=timeout)


__all__ = [
    "ContainerManager",
    "ContainerManagerError",
]
