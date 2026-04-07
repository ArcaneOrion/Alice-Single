"""
Docker 配置数据类

定义 Docker 沙盒环境所需的所有配置参数。
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass(frozen=True)
class MountConfig:
    """容器挂载配置

    Args:
        host_path: 宿主机路径
        container_path: 容器内路径
        read_only: 是否只读挂载
    """

    host_path: Path
    container_path: str
    read_only: bool = False

    @property
    def mount_spec(self) -> str:
        """生成 Docker 挂载参数格式字符串"""
        ro_flag = ":ro" if self.read_only else ""
        return f"{self.host_path}:{self.container_path}{ro_flag}"


@dataclass(frozen=True)
class ContainerConfig:
    """容器运行配置

    Args:
        name: 容器名称
        work_dir: 容器内工作目录
        restart_policy: 重启策略 (always, on-failure, unless-stopped)
        keep_alive_command: 保持容器运行的命令
    """

    name: str = "alice-sandbox-instance"
    work_dir: str = "/app"
    restart_policy: str = "always"
    keep_alive_command: List[str] = field(default_factory=lambda: ["tail", "-f", "/dev/null"])

    @property
    def restart_policy_spec(self) -> str:
        """生成 Docker 重启策略参数"""
        return f"--restart={self.restart_policy}"


@dataclass(frozen=True)
class DockerConfig:
    """Docker 沙盒环境配置

    整合镜像、容器、挂载等所有配置参数。

    Args:
        image_name: Docker 镜像名称与标签
        dockerfile_path: Dockerfile 路径（用于构建）
        project_root: 项目根目录（用于解析相对路径）
        container: 容器配置
        skills_path: 技能库路径（将被挂载）
        output_path: 输出目录路径（将被挂载）
    """

    image_name: str = "alice-sandbox:latest"
    dockerfile_path: str = "Dockerfile.sandbox"
    project_root: Path = field(default_factory=lambda: Path.cwd())
    container: ContainerConfig = field(default_factory=ContainerConfig)

    @property
    def dockerfile_full_path(self) -> Path:
        """获取 Dockerfile 的完整路径"""
        return self.project_root / self.dockerfile_path

    @property
    def default_mounts(self) -> List[MountConfig]:
        """获取默认挂载配置

        同步技能库、.alice 运行时目录和输出目录。
        """
        skills_path = self.project_root / "skills"
        runtime_path = self.project_root / ".alice"
        output_path = self.project_root / ".alice" / "workspace"

        return [
            MountConfig(
                host_path=skills_path,
                container_path="/app/skills",
                read_only=False,
            ),
            MountConfig(
                host_path=runtime_path,
                container_path="/app/.alice",
                read_only=False,
            ),
            MountConfig(
                host_path=output_path,
                container_path="/workspace",
                read_only=False,
            ),
        ]

    def with_custom_project_root(self, project_root: Path) -> "DockerConfig":
        """创建使用自定义项目根目录的配置副本"""
        return DockerConfig(
            image_name=self.image_name,
            dockerfile_path=self.dockerfile_path,
            project_root=project_root,
            container=self.container,
        )


@dataclass
class ContainerStatus:
    """容器运行状态

    Args:
        exists: 容器是否存在
        running: 容器是否正在运行
        status_raw: 原始状态字符串
    """

    exists: bool
    running: bool
    status_raw: str = ""

    @classmethod
    def from_docker_output(cls, output: str) -> "ContainerStatus":
        """从 Docker ps 命令输出解析状态

        Args:
            output: docker ps --format '{{.Status}}' 的输出
        """
        if not output or not output.strip():
            return cls(exists=False, running=False, status_raw="")

        status_lower = output.lower()
        running = "up" in status_lower

        return cls(
            exists=True,
            running=running,
            status_raw=output.strip(),
        )


__all__ = [
    "MountConfig",
    "ContainerConfig",
    "DockerConfig",
    "ContainerStatus",
]
