"""
Docker Infrastructure Module

该模块实现了 Docker 沙盒环境的核心管理功能，包括：
- 三阶段初始化：引擎检查 → 镜像构建 → 容器启动
- 常驻容器模式管理
- 容器执行与状态监控
"""

from .client import DockerClient
from .config import ContainerConfig, DockerConfig, MountConfig
from .container_manager import ContainerManager, DockerExecutionBackend
from .image_builder import ImageBuilder

__all__ = [
    "DockerConfig",
    "ContainerConfig",
    "MountConfig",
    "DockerClient",
    "ImageBuilder",
    "ContainerManager",
    "DockerExecutionBackend",
]
