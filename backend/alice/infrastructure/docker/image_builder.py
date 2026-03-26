"""
Docker 镜像构建模块

负责 Docker 镜像的检查与构建。
"""

import logging
import sys
from pathlib import Path
from typing import Optional, Callable

from .client import DockerClient, DockerClientError
from .config import DockerConfig

logger = logging.getLogger(__name__)


class ImageBuildError(DockerClientError):
    """镜像构建异常"""

    pass


class ImageBuilder:
    """Docker 镜像构建器

    负责检查镜像是否存在，并在需要时进行构建。

    Args:
        config: Docker 配置
        client: Docker 客户端实例
    """

    def __init__(self, config: DockerConfig, client: Optional[DockerClient] = None):
        self.config = config
        self.client = client or DockerClient(config)

    def check_image_exists(self) -> bool:
        """检查镜像是否已存在

        Returns:
            bool: 镜像是否存在
        """
        return self.client.check_image_exists()

    def ensure_image(
        self,
        force_rebuild: bool = False,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> bool:
        """确保镜像存在，不存在时自动构建

        这是三阶段初始化的第二阶段：镜像构建。

        Args:
            force_rebuild: 是否强制重新构建
            on_progress: 构建进度回调函数

        Returns:
            bool: 镜像是否可用

        Raises:
            ImageBuildError: 镜像构建失败
        """
        # 如果镜像存在且不强制重建，直接返回
        if not force_rebuild and self.check_image_exists():
            logger.info(f"镜像 {self.config.image_name} 已存在，跳过构建")
            return True

        if force_rebuild:
            logger.info(f"强制重建模式：开始构建镜像 {self.config.image_name}")
        else:
            logger.info(f"镜像 {self.config.image_name} 不存在，开始构建")

        return self._build(on_progress=on_progress)

    def _build(
        self,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> bool:
        """执行镜像构建

        Args:
            on_progress: 构建进度回调函数

        Returns:
            bool: 构建是否成功

        Raises:
            ImageBuildError: 构建失败
        """
        # 检查 Dockerfile 是否存在
        dockerfile_path = self.config.dockerfile_full_path
        if not dockerfile_path.exists():
            raise ImageBuildError(
                f"Dockerfile 不存在: {dockerfile_path}\n"
                f"请确保 {self.config.dockerfile_path} 文件存在于项目根目录"
            )

        # 默认进度回调
        if on_progress is None:

            def default_progress(line: str):
                print(f"  [Docker Build]: {line}")

            on_progress = default_progress

        # 执行构建
        try:
            result = self.client.build_image(on_output=on_progress)

            if result.returncode != 0:
                raise ImageBuildError(
                    f"Docker 镜像构建失败。请检查 {self.config.dockerfile_path} 或网络连接。"
                )

            logger.info(f"镜像 {self.config.image_name} 构建成功")
            return True

        except DockerClientError as e:
            raise ImageBuildError(f"镜像构建过程出错: {e}")

    def rebuild(self, on_progress: Optional[Callable[[str], None]] = None) -> bool:
        """强制重新构建镜像

        Args:
            on_progress: 构建进度回调函数

        Returns:
            bool: 构建是否成功
        """
        return self._build(on_progress=on_progress)


__all__ = [
    "ImageBuilder",
    "ImageBuildError",
]
