"""
命令模型

定义命令执行相关的数据结构
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class CommandType(Enum):
    """命令类型枚举"""
    BASH = "bash"
    PYTHON = "python"
    BUILTIN = "builtin"
    UNKNOWN = "unknown"


class ExecutionEnvironment(Enum):
    """执行环境枚举"""
    HOST = "host"           # 宿主机执行
    DOCKER = "docker"       # Docker 容器执行
    SANDBOX = "sandbox"     # 沙盒执行


@dataclass(frozen=True)
class Command:
    """命令数据模型"""

    raw: str  # 原始命令字符串
    type: CommandType = field(default=CommandType.UNKNOWN)
    environment: ExecutionEnvironment = field(default=ExecutionEnvironment.DOCKER)
    working_dir: Optional[str] = field(default="/app")
    timeout: int = field(default=120)

    def __post_init__(self):
        """命令后处理，自动推断命令类型"""
        if self.type == CommandType.UNKNOWN:
            object.__setattr__(self, 'type', self._infer_type())

    def _infer_type(self) -> CommandType:
        """推断命令类型"""
        stripped = self.raw.strip().lower()

        # 内置命令检测
        builtin_prefixes = ["toolkit", "update_prompt", "todo", "memory"]
        for prefix in builtin_prefixes:
            if stripped.startswith(prefix):
                return CommandType.BUILTIN

        return CommandType.BASH

    def is_safe(self) -> bool:
        """基本安全检查（仅做基础验证）"""
        dangerous = ["rm -rf /", "rm -rf /*", "mkfs", "dd if=/dev/zero"]
        return not any(d in self.raw.lower() for d in dangerous)

    def to_docker_command(self) -> list[str]:
        """转换为 Docker exec 命令列表"""
        cmd = [
            "docker", "exec",
            "-w", self.working_dir or "/app",
        ]

        if self.type == CommandType.PYTHON:
            cmd.extend(["python3", "-c", self.raw])
        else:
            cmd.extend(["bash", "-c", self.raw])

        return cmd


__all__ = [
    "Command",
    "CommandType",
    "ExecutionEnvironment",
]
