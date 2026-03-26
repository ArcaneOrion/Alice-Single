"""
Docker 客户端封装

提供 Docker 命令执行的基础功能，封装 subprocess 调用。
"""

import logging
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from .config import ContainerStatus, DockerConfig

logger = logging.getLogger(__name__)


@dataclass
class CommandResult:
    """命令执行结果

    Args:
        returncode: 退出码
        stdout: 标准输出
        stderr: 标准错误输出
        success: 是否成功
    """

    returncode: int
    stdout: str
    stderr: str = ""

    @property
    def success(self) -> bool:
        """命令是否执行成功"""
        return self.returncode == 0

    @property
    def output(self) -> str:
        """组合输出（stdout + stderr）"""
        output = self.stdout
        if self.stderr:
            output += f"\n[标准错误输出]:\n{self.stderr}"
        return output


class DockerClientError(Exception):
    """Docker 客户端异常"""

    pass


class DockerEngineNotFoundError(DockerClientError):
    """Docker 引擎未找到异常"""

    pass


class DockerCommand:
    """Docker 命令构建器

    提供类型安全的 Docker 命令构建。
    """

    @staticmethod
    def version() -> List[str]:
        """构建 docker --version 命令"""
        return ["docker", "--version"]

    @staticmethod
    def image_inspect(image_name: str) -> List[str]:
        """构建 docker image inspect 命令"""
        return ["docker", "image", "inspect", image_name]

    @staticmethod
    def image_build(
        dockerfile_path: Path,
        image_name: str,
        build_context: str = ".",
    ) -> List[str]:
        """构建 docker build 命令"""
        return [
            "docker",
            "build",
            "-t",
            image_name,
            "-f",
            str(dockerfile_path),
            build_context,
        ]

    @staticmethod
    def container_list_all(
        name_filter: Optional[str] = None,
        format_str: str = "{{.Status}}",
    ) -> List[str]:
        """构建 docker ps -a 命令"""
        cmd = ["docker", "ps", "-a"]
        if name_filter:
            cmd.extend(["--filter", f"name={name_filter}"])
        cmd.extend(["--format", format_str])
        return cmd

    @staticmethod
    def container_run(
        image_name: str,
        container_name: str,
        work_dir: str,
        restart_policy: str,
        mounts: List[Tuple[str, str, bool]],  # (host_path, container_path, read_only)
        keep_alive_cmd: List[str],
    ) -> List[str]:
        """构建 docker run 命令"""
        cmd = [
            "docker",
            "run",
            "-d",
            "--name",
            container_name,
            f"--restart={restart_policy}",
        ]

        # 添加挂载
        for host_path, container_path, read_only in mounts:
            mount_spec = f"{host_path}:{container_path}"
            if read_only:
                mount_spec += ":ro"
            cmd.extend(["-v", mount_spec])

        # 添加工作目录
        cmd.extend(["-w", work_dir])

        # 镜像和启动命令
        cmd.extend([image_name] + keep_alive_cmd)
        return cmd

    @staticmethod
    def container_start(container_name: str) -> List[str]:
        """构建 docker start 命令"""
        return ["docker", "start", container_name]

    @staticmethod
    def container_stop(container_name: str) -> List[str]:
        """构建 docker stop 命令"""
        return ["docker", "stop", container_name]

    @staticmethod
    def container_remove(container_name: str, force: bool = False) -> List[str]:
        """构建 docker rm 命令"""
        cmd = ["docker", "rm"]
        if force:
            cmd.append("-f")
        cmd.append(container_name)
        return cmd

    @staticmethod
    def container_exec(
        container_name: str,
        work_dir: str,
        command: List[str],
    ) -> List[str]:
        """构建 docker exec 命令"""
        cmd = [
            "docker",
            "exec",
            "-w",
            work_dir,
            container_name,
        ]
        cmd.extend(command)
        return cmd


class DockerClient:
    """Docker 客户端

    封装 Docker CLI 调用，提供类型安全的接口。

    Args:
        config: Docker 配置
        timeout: 命令执行超时时间（秒）
    """

    def __init__(self, config: DockerConfig, timeout: int = 120):
        self.config = config
        self.timeout = timeout

    def _run(self, cmd: List[str], capture: bool = True) -> CommandResult:
        """执行命令

        Args:
            cmd: 命令及其参数
            capture: 是否捕获输出

        Returns:
            CommandResult: 命令执行结果
        """
        logger.debug(f"执行命令: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                shell=False,
                capture_output=capture,
                text=True,
                timeout=self.timeout,
            )
            return CommandResult(
                returncode=result.returncode,
                stdout=result.stdout if capture else "",
                stderr=result.stderr if capture else "",
            )
        except subprocess.TimeoutExpired:
            logger.error(f"命令执行超时: {' '.join(cmd)}")
            raise DockerClientError(f"命令执行超时: {' '.join(cmd)}")
        except FileNotFoundError:
            logger.error("Docker 未安装或不在 PATH 中")
            raise DockerEngineNotFoundError("Docker 未安装或不在 PATH 中")

    def check_engine(self) -> bool:
        """检查 Docker 引擎是否可用

        Returns:
            bool: Docker 引擎是否可用

        Raises:
            DockerEngineNotFoundError: Docker 引擎未找到
        """
        result = self._run(DockerCommand.version())
        if not result.success:
            raise DockerEngineNotFoundError(
                "系统未检测到 Docker。Alice 需要 Docker 环境来确保执行安全与持久化。"
            )
        logger.info(f"Docker 引擎检测成功: {result.stdout.strip()}")
        return True

    def check_image_exists(self) -> bool:
        """检查镜像是否存在

        Returns:
            bool: 镜像是否存在
        """
        result = self._run(DockerCommand.image_inspect(self.config.image_name))
        return result.success

    def get_container_status(self) -> ContainerStatus:
        """获取容器状态

        Returns:
            ContainerStatus: 容器状态
        """
        result = self._run(
            DockerCommand.container_list_all(
                name_filter=self.config.container.name,
                format_str="{{.Status}}",
            )
        )
        return ContainerStatus.from_docker_output(result.stdout)

    def build_image(
        self,
        on_output: Optional[callable] = None,
    ) -> CommandResult:
        """构建 Docker 镜像

        Args:
            on_output: 输出回调函数，接收每行输出

        Returns:
            CommandResult: 构建结果
        """
        logger.info(f"开始构建镜像: {self.config.image_name}")

        cmd = DockerCommand.image_build(
            dockerfile_path=self.config.dockerfile_full_path,
            image_name=self.config.image_name,
            build_context=".",
        )

        # 使用 Popen 以支持实时输出
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            for line in process.stdout:
                line = line.rstrip("\n\r")
                if on_output:
                    on_output(line)
                logger.debug(f"[Docker Build]: {line}")

            process.wait()
            return CommandResult(
                returncode=process.returncode,
                stdout="",
            )
        except Exception as e:
            raise DockerClientError(f"镜像构建失败: {e}")

    def run_container(self) -> CommandResult:
        """创建并启动容器

        Returns:
            CommandResult: 运行结果
        """
        # 准备挂载配置
        mounts = [
            (str(m.host_path), m.container_path, m.read_only)
            for m in self.config.default_mounts
        ]

        cmd = DockerCommand.container_run(
            image_name=self.config.image_name,
            container_name=self.config.container.name,
            work_dir=self.config.container.work_dir,
            restart_policy=self.config.container.restart_policy,
            mounts=mounts,
            keep_alive_cmd=self.config.container.keep_alive_command,
        )

        return self._run(cmd)

    def start_container(self) -> CommandResult:
        """启动已存在的容器

        Returns:
            CommandResult: 启动结果
        """
        cmd = DockerCommand.container_start(self.config.container.name)
        return self._run(cmd)

    def stop_container(self) -> CommandResult:
        """停止容器

        Returns:
            CommandResult: 停止结果
        """
        cmd = DockerCommand.container_stop(self.config.container.name)
        return self._run(cmd)

    def remove_container(self, force: bool = False) -> CommandResult:
        """删除容器

        Args:
            force: 是否强制删除

        Returns:
            CommandResult: 删除结果
        """
        cmd = DockerCommand.container_remove(self.config.container.name, force=force)
        return self._run(cmd)

    def exec_command(
        self,
        command: List[str],
        timeout: Optional[int] = None,
    ) -> CommandResult:
        """在容器中执行命令

        Args:
            command: 要执行的命令（列表形式）
            timeout: 超时时间（覆盖默认值）

        Returns:
            CommandResult: 执行结果
        """
        cmd = DockerCommand.container_exec(
            container_name=self.config.container.name,
            work_dir=self.config.container.work_dir,
            command=command,
        )

        try:
            result = subprocess.run(
                cmd,
                shell=False,
                capture_output=True,
                text=True,
                timeout=timeout or self.timeout,
            )
            return CommandResult(
                returncode=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
            )
        except subprocess.TimeoutExpired:
            logger.error(f"容器命令执行超时: {' '.join(command)}")
            raise DockerClientError(f"容器命令执行超时")


__all__ = [
    "DockerClient",
    "DockerClientError",
    "DockerEngineNotFoundError",
    "CommandResult",
    "DockerCommand",
]
