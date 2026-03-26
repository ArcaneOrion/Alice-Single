"""
执行结果模型

定义命令执行后的结果数据结构
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ExecutionStatus(Enum):
    """执行状态枚举"""
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    INTERRUPTED = "interrupted"
    BLOCKED = "blocked"  # 被安全规则拦截


@dataclass
class ExecutionResult:
    """命令执行结果

    统一的执行结果返回格式，包含状态、输出、错误等信息
    """

    success: bool
    output: str
    status: ExecutionStatus = field(default=ExecutionStatus.SUCCESS)
    error: str = field(default="")
    exit_code: int = field(default=0)
    execution_time: float = field(default=0.0)
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_subprocess(
        cls,
        stdout: str,
        stderr: str,
        returncode: int,
        execution_time: float = 0.0
    ) -> "ExecutionResult":
        """从 subprocess 结果创建 ExecutionResult"""
        output = stdout or ""
        if stderr:
            output += f"\n[标准错误输出]:\n{stderr}"

        success = returncode == 0
        status = ExecutionStatus.SUCCESS if success else ExecutionStatus.FAILURE

        return cls(
            success=success,
            output=output or "[命令执行成功，无回显内容]",
            status=status,
            error=stderr or "",
            exit_code=returncode,
            execution_time=execution_time
        )

    @classmethod
    def success_result(cls, output: str, execution_time: float = 0.0) -> "ExecutionResult":
        """创建成功结果"""
        return cls(
            success=True,
            output=output,
            status=ExecutionStatus.SUCCESS,
            execution_time=execution_time
        )

    @classmethod
    def error_result(cls, error: str, status: ExecutionStatus = ExecutionStatus.FAILURE) -> "ExecutionResult":
        """创建错误结果"""
        return cls(
            success=False,
            output="",
            status=status,
            error=error
        )

    @classmethod
    def blocked_result(cls, reason: str) -> "ExecutionResult":
        """创建被拦截结果"""
        return cls(
            success=False,
            output=reason,
            status=ExecutionStatus.BLOCKED,
            error=reason
        )

    @classmethod
    def timeout_result(cls, timeout_seconds: int = 120) -> "ExecutionResult":
        """创建超时结果"""
        return cls(
            success=False,
            output=f"错误: 执行超时 ({timeout_seconds}秒)。",
            status=ExecutionStatus.TIMEOUT,
            error=f"Command execution timeout after {timeout_seconds} seconds"
        )

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式"""
        return {
            "success": self.success,
            "output": self.output,
            "status": self.status.value,
            "error": self.error,
            "exit_code": self.exit_code,
            "execution_time": self.execution_time,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }


__all__ = [
    "ExecutionResult",
    "ExecutionStatus",
]
