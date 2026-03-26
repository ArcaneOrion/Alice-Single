"""
生命周期服务

管理应用的启动、运行和关闭生命周期。
"""

import logging
import subprocess
from pathlib import Path
from typing import Optional

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

    def initialize(self) -> None:
        """初始化应用生命周期

        确保 Docker 环境就绪。
        """
        if self._initialized:
            logger.debug("生命周期服务已初始化")
            return

        logger.info("正在初始化生命周期...")

        # 1. 检查 Docker 引擎
        self._check_docker_engine()

        # 2. 检查并构建镜像
        self._ensure_docker_image()

        # 3. 启动常驻容器
        self._ensure_container_running()

        self._initialized = True
        logger.info("生命周期初始化完成")

    def _check_docker_engine(self) -> None:
        """检查 Docker 引擎是否可用"""
        try:
            result = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                text=True,
                check=True,
            )
            logger.info(f"Docker 引擎检测成功: {result.stdout.strip()}")
        except subprocess.CalledProcessError:
            raise RuntimeError(
                "Docker 引擎未检测到。Alice 需要 Docker 环境来确保执行安全与持久化。"
            )
        except FileNotFoundError:
            raise RuntimeError("Docker 命令未找到，请确保 Docker 已安装。")

    def _ensure_docker_image(self) -> None:
        """确保 Docker 镜像存在"""
        result = subprocess.run(
            [
                "docker",
                "image",
                "inspect",
                self.docker_config.image_name,
            ],
            capture_output=True,
        )

        if result.returncode != 0:
            logger.info(f"Docker 镜像 {self.docker_config.image_name} 不存在，开始构建...")
            self._build_docker_image()
        else:
            logger.info(f"Docker 镜像 {self.docker_config.image_name} 已存在")

    def _build_docker_image(self) -> None:
        """构建 Docker 镜像"""
        dockerfile_path = self.docker_config.dockerfile_full_path

        if not dockerfile_path.exists():
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

        logger.info(f"执行构建命令: {' '.join(build_cmd)}")

        process = subprocess.Popen(
            build_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=str(self.project_root),
        )

        # 实时输出构建日志
        for line in process.stdout:
            logger.debug(f"[Docker Build] {line.strip()}")

        process.wait()

        if process.returncode != 0:
            raise RuntimeError(f"Docker 镜像构建失败，退出码: {process.returncode}")

        logger.info(f"Docker 镜像 {self.docker_config.image_name} 构建成功")

    def _ensure_container_running(self) -> None:
        """确保容器正在运行"""
        status = self._get_container_status()

        if not status.exists:
            # 创建并启动新容器
            self._create_and_start_container()
        elif not status.running:
            # 启动已存在的容器
            self._start_container()
        else:
            logger.info(f"容器 {self.docker_config.container.name} 已在运行")
            self._container_running = True

    def _get_container_status(self) -> ContainerStatus:
        """获取容器状态"""
        result = subprocess.run(
            [
                "docker",
                "ps",
                "-a",
                "--filter",
                f"name={self.docker_config.container.name}",
                "--format",
                "{{.Status}}",
            ],
            capture_output=True,
            text=True,
        )

        return ContainerStatus.from_docker_output(result.stdout)

    def _create_and_start_container(self) -> None:
        """创建并启动新容器"""
        logger.info(f"正在创建容器 {self.docker_config.container.name}...")

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

        logger.debug(f"执行命令: {' '.join(cmd)}")

        subprocess.run(cmd, check=True)

        self._container_running = True
        logger.info(f"容器 {self.docker_config.container.name} 创建成功")

    def _start_container(self) -> None:
        """启动已存在的容器"""
        logger.info(f"正在启动容器 {self.docker_config.container.name}...")

        subprocess.run(
            ["docker", "start", self.docker_config.container.name],
            check=True,
        )

        self._container_running = True
        logger.info(f"容器 {self.docker_config.container.name} 启动成功")

    def stop_container(self) -> None:
        """停止容器"""
        if not self._container_running:
            return

        logger.info(f"正在停止容器 {self.docker_config.container.name}...")

        subprocess.run(
            ["docker", "stop", self.docker_config.container.name],
            capture_output=True,
        )

        self._container_running = False
        logger.info(f"容器 {self.docker_config.container.name} 已停止")

    def remove_container(self) -> None:
        """删除容器"""
        status = self._get_container_status()
        if not status.exists:
            return

        if status.running:
            self.stop_container()

        logger.info(f"正在删除容器 {self.docker_config.container.name}...")

        subprocess.run(
            ["docker", "rm", self.docker_config.container.name],
            capture_output=True,
        )

        logger.info(f"容器 {self.docker_config.container.name} 已删除")

    def shutdown(self) -> None:
        """关闭应用，清理资源"""
        logger.info("正在关闭生命周期服务...")

        # 注意：我们不删除容器，保持容器持久化
        # 只是在需要时停止

        self._initialized = False
        logger.info("生命周期服务已关闭")

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
