"""
Docker 执行器

实现在 Docker 容器中执行命令的逻辑
"""

import logging
import os
import subprocess
import time
from typing import Optional

from .base import BaseExecutor
from ..models.command import Command, ExecutionEnvironment
from ..models.execution_result import ExecutionResult, ExecutionStatus
from ..models.security_rule import SecurityRule, DEFAULT_SECURITY_RULES

logger = logging.getLogger(__name__)


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

        # 加载默认安全规则
        for rule in DEFAULT_SECURITY_RULES:
            self.add_security_rule(rule)

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
        start_time = time.time()

        try:
            if not self._docker_environment_ready:
                self._ensure_docker_environment()

            full_command = self._build_docker_command(command)

            logger.info(f"执行指令 ({'Python' if command.type.value == 'python' else 'Bash'}): {command.raw[:200]}...")

            result = subprocess.run(
                full_command,
                shell=False,  # 核心修复：禁用宿主机 Shell 解析
                capture_output=True,
                text=True,
                timeout=self.default_timeout,
                env=os.environ
            )

            execution_time = time.time() - start_time

            return ExecutionResult.from_subprocess(
                stdout=result.stdout,
                stderr=result.stderr,
                returncode=result.returncode,
                execution_time=execution_time
            )

        except subprocess.TimeoutExpired:
            logger.error(f"命令执行超时: {command.raw[:100]}")
            return ExecutionResult.timeout_result(self.default_timeout)

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"命令执行异常: {e}")
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

        try:
            # 1. 检查 Docker 引擎
            self._check_docker_engine()

            # 2. 检查并构建镜像
            self._ensure_docker_image()

            # 3. 启动常驻容器
            self._ensure_container_running()
            self._docker_environment_ready = True

        except Exception as e:
            logger.error(f"初始化 Docker 环境失败: {e}")
            raise

    def _check_docker_engine(self) -> None:
        """检查 Docker 引擎是否可用"""
        res = subprocess.run(
            "docker --version",
            shell=True,
            capture_output=True
        )
        if res.returncode != 0:
            raise RuntimeError("系统未检测到 Docker。Alice 需要 Docker 环境来确保执行安全与持久化。")

    def _ensure_docker_image(self) -> None:
        """确保 Docker 镜像存在"""
        res = subprocess.run(
            f"docker image inspect {self.docker_image}",
            shell=True,
            capture_output=True
        )

        if res.returncode != 0:
            logger.info(f"未找到 Docker 镜像 {self.docker_image}，需要构建。")
            raise RuntimeError(
                f"Docker 镜像 {self.docker_image} 不存在。"
                f"请先运行: docker build -t {self.docker_image} -f Dockerfile.sandbox ."
            )

    def _ensure_container_running(self) -> None:
        """确保容器正在运行"""
        import sys

        res = subprocess.run(
            f"docker ps -a --filter name={self.container_name} --format '{{{{.Status}}}}'",
            shell=True,
            capture_output=True,
            text=True
        )
        status = res.stdout.lower()

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
            subprocess.run(" ".join(start_cmd), shell=True, check=True)
            print(f"[系统]: 容器已成功初始化。")

        elif "up" not in status:
            # 容器存在但未运行
            print(f"[系统]: 正在唤醒 Alice 常驻实验室容器...")
            subprocess.run(f"docker start {self.container_name}", shell=True, check=True)

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
