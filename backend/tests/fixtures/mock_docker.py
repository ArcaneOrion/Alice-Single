"""
Mock Docker 执行器

用于测试时模拟 Docker 容器执行
"""

import subprocess
from typing import Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime

from backend.alice.core.interfaces.command_executor import ExecutionResult, SecurityRule


@dataclass
class DockerMockConfig:
    """Docker Mock 配置"""
    container_name: str = "alice-sandbox-instance"
    image_name: str = "alice-sandbox:latest"
    is_running: bool = True
    image_exists: bool = True
    command_responses: dict[str, ExecutionResult] = field(default_factory=dict)
    default_response: Optional[ExecutionResult] = None
    delay_ms: int = 0


class MockDockerExecutor:
    """Mock Docker 执行器

    模拟 Docker 容器执行，支持：
    - 命令执行响应配置
    - 安全规则验证
    - 容器状态模拟
    - 延迟模拟
    """

    def __init__(self, config: DockerMockConfig | None = None):
        """初始化 Mock Docker 执行器"""
        self.config = config or DockerMockConfig()
        self.execute_count = 0
        self.execute_history: list[dict] = []
        self.security_rules: list[SecurityRule] = []
        self.interrupted = False

        # 设置默认响应
        if self.config.default_response is None:
            self.config.default_response = ExecutionResult(
                success=True,
                output="",
                error="",
                exit_code=0,
                execution_time=0.1
            )

    def execute(self, command: str, is_python_code: bool = False) -> ExecutionResult:
        """执行命令"""
        self.execute_count += 1
        self._record_execute(command, is_python_code)

        if self.interrupted:
            return ExecutionResult(
                success=False,
                output="",
                error="Command interrupted",
                exit_code=130,
                execution_time=0.0
            )

        # 检查是否有预配置的响应
        key = f"{'python' if is_python_code else 'bash'}:{command}"
        if key in self.config.command_responses:
            return self.config.command_responses[key]

        # 检查命令前缀匹配
        for prefix_key, response in self.config.command_responses.items():
            if command.startswith(prefix_key):
                return response

        # 返回默认响应或模拟执行
        return self._simulate_execution(command, is_python_code)

    def validate(self, command: str) -> tuple[bool, str]:
        """验证命令安全性"""
        for rule in self.security_rules:
            if rule.pattern.lower() in command.lower():
                if rule.action == "block":
                    return False, f"Blocked by security rule: {rule.name} - {rule.reason}"
                elif rule.action == "warn":
                    return True, f"Warning: {rule.reason}"
        return True, ""

    def add_security_rule(self, rule: SecurityRule) -> None:
        """添加安全规则"""
        self.security_rules.append(rule)

    def interrupt(self) -> bool:
        """中断当前执行"""
        self.interrupted = True
        return True

    def reset_interrupt(self) -> None:
        """重置中断状态"""
        self.interrupted = False

    def set_command_response(
        self,
        command: str,
        response: ExecutionResult | None = None,
        is_python: bool = False
    ) -> None:
        """设置命令响应"""
        key = f"{'python' if is_python else 'bash'}:{command}"
        if response is None:
            response = ExecutionResult(
                success=True,
                output=f"Mocked output for: {command}",
                error="",
                exit_code=0
            )
        self.config.command_responses[key] = response

    def _simulate_execution(self, command: str, is_python_code: bool) -> ExecutionResult:
        """模拟执行"""
        import time

        start_time = time.time()

        # 特殊命令模拟
        if command == "echo test":
            output = "test\n"
        elif command.startswith("echo "):
            output = command[5:] + "\n"
        elif "ls" in command:
            output = "file1.txt\nfile2.py\ndir/\n"
        elif "pwd" in command:
            output = "/app\n"
        elif command.strip() == "error":
            return ExecutionResult(
                success=False,
                output="",
                error="Simulated error",
                exit_code=1,
                execution_time=0.1
            )
        elif is_python_code:
            # Python 代码执行模拟
            if "print(" in command:
                # 提取 print 内容
                import re
                match = re.search(r'print\(["\'](.+?)["\']\)', command)
                if match:
                    output = match.group(1) + "\n"
                else:
                    output = ""
            else:
                output = ""
        else:
            output = f"Executed: {command}\n"

        execution_time = time.time() - start_time

        return ExecutionResult(
            success=True,
            output=output,
            error="",
            exit_code=0,
            execution_time=execution_time
        )

    def _record_execute(self, command: str, is_python_code: bool) -> None:
        """记录执行历史"""
        self.execute_history.append({
            "command": command,
            "is_python": is_python_code,
            "timestamp": datetime.now().isoformat()
        })

    def get_execute_history(self) -> list[dict]:
        """获取执行历史"""
        return self.execute_history

    def was_executed(self, command: str) -> bool:
        """检查命令是否执行过"""
        return any(h["command"] == command for h in self.execute_history)

    def reset(self) -> None:
        """重置状态"""
        self.execute_count = 0
        self.execute_history.clear()
        self.interrupted = False


class MockSubprocessResult:
    """Mock subprocess.run 结果"""

    def __init__(
        self,
        stdout: str = "",
        stderr: str = "",
        returncode: int = 0
    ):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def mock_subprocess_run(
    stdout: str = "",
    stderr: str = "",
    returncode: int = 0,
    side_effect: Optional[Callable] = None
) -> Callable:
    """创建 mock subprocess.run 函数"""

    def mock_func(*args, **kwargs):
        if side_effect:
            return side_effect(*args, **kwargs)
        return MockSubprocessResult(stdout, stderr, returncode)

    return mock_func


def mock_docker_check_output(
    container_name: str = "alice-sandbox-instance",
    is_running: bool = True
) -> Callable:
    """创建 mock subprocess.check_output 用于 Docker 检查"""

    def mock_func(*args, **kwargs):
        cmd = " ".join(args[0]) if args else str(kwargs.get("cmd", ""))

        if "docker --version" in cmd:
            return b"Docker version 24.0.0"
        elif "docker ps" in cmd:
            if is_running:
                return b"Up"
            return b""
        elif "docker inspect" in cmd:
            if is_running:
                return b'{"State":{"Running":true}}'
            return b'{"State":{"Running":false}}'
        return b""

    return mock_func


__all__ = [
    "MockDockerExecutor",
    "DockerMockConfig",
    "MockSubprocessResult",
    "mock_subprocess_run",
    "mock_docker_check_output",
]
