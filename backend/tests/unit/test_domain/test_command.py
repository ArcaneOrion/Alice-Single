"""
命令模型单元测试

测试 Command、CommandType、ExecutionEnvironment 等模型
"""

import pytest

from backend.alice.domain.execution.models.command import (
    Command,
    CommandType,
    ExecutionEnvironment,
)


# ============================================================================
# Command 类测试
# ============================================================================

class TestCommand:
    """Command 模型测试"""

    def test_create_command(self):
        """测试创建命令"""
        cmd = Command(raw="echo hello")

        assert cmd.raw == "echo hello"
        assert cmd.type == CommandType.BASH
        assert cmd.environment == ExecutionEnvironment.DOCKER
        assert cmd.working_dir == "/app"
        assert cmd.timeout == 120

    def test_create_command_with_custom_params(self):
        """测试创建带自定义参数的命令"""
        cmd = Command(
            raw="print('hello')",
            type=CommandType.PYTHON,
            environment=ExecutionEnvironment.SANDBOX,
            working_dir="/home/user",
            timeout=60
        )

        assert cmd.type == CommandType.PYTHON
        assert cmd.environment == ExecutionEnvironment.SANDBOX
        assert cmd.working_dir == "/home/user"
        assert cmd.timeout == 60

    def test_auto_infer_builtin_command(self):
        """测试自动推断内置命令"""
        cmd = Command(raw="toolkit list")

        assert cmd.type == CommandType.BUILTIN

    def test_auto_infer_todo_command(self):
        """测试自动推断 todo 命令"""
        cmd = Command(raw="todo buy milk")

        assert cmd.type == CommandType.BUILTIN

    def test_auto_infer_memory_command(self):
        """测试自动推断 memory 命令"""
        cmd = Command(raw="memory something important")

        assert cmd.type == CommandType.BUILTIN

    def test_auto_infer_update_prompt_command(self):
        """测试自动推断 update_prompt 命令"""
        cmd = Command(raw="update_prompt new content")

        assert cmd.type == CommandType.BUILTIN

    def test_default_to_bash_for_unknown(self):
        """测试未知命令默认为 BASH"""
        cmd = Command(raw="ls -la")

        assert cmd.type == CommandType.BASH

    def test_is_safe_with_safe_command(self):
        """测试安全命令检查"""
        cmd = Command(raw="ls -la")

        assert cmd.is_safe() is True

    def test_is_safe_with_dangerous_command(self):
        """测试危险命令检查"""
        cmd = Command(raw="rm -rf /")

        assert cmd.is_safe() is False

    def test_is_safe_case_insensitive(self):
        """测试安全检查大小写不敏感"""
        cmd = Command(raw="RM -RF /")

        assert cmd.is_safe() is False

    def test_to_docker_command_bash(self):
        """测试转换为 Docker 命令 (Bash)"""
        cmd = Command(
            raw="echo test",
            type=CommandType.BASH,
            working_dir="/app"
        )

        docker_cmd = cmd.to_docker_command()

        assert docker_cmd[0] == "docker"
        assert docker_cmd[1] == "exec"
        assert "-w" in docker_cmd
        assert "/app" in docker_cmd
        assert "bash" in docker_cmd
        assert "echo test" in docker_cmd

    def test_to_docker_command_python(self):
        """测试转换为 Docker 命令 (Python)"""
        cmd = Command(
            raw="print('hello')",
            type=CommandType.PYTHON,
            working_dir="/workspace"
        )

        docker_cmd = cmd.to_docker_command()

        assert "python3" in docker_cmd
        assert "-c" in docker_cmd
        assert "print('hello')" in docker_cmd

    def test_frozen_command_is_immutable(self):
        """测试 frozen 命令不可变"""
        cmd = Command(raw="test")

        with pytest.raises(Exception):  # FrozenInstanceError
            cmd.raw = "modified"


# ============================================================================
# CommandType 枚举测试
# ============================================================================

class TestCommandType:
    """CommandType 枚举测试"""

    def test_enum_values(self):
        """测试枚举值"""
        assert CommandType.BASH.value == "bash"
        assert CommandType.PYTHON.value == "python"
        assert CommandType.BUILTIN.value == "builtin"
        assert CommandType.UNKNOWN.value == "unknown"

    def test_enum_comparison(self):
        """测试枚举比较"""
        assert CommandType.BASH == CommandType.BASH
        assert CommandType.BASH != CommandType.PYTHON


# ============================================================================
# ExecutionEnvironment 枚举测试
# ============================================================================

class TestExecutionEnvironment:
    """ExecutionEnvironment 枚举测试"""

    def test_enum_values(self):
        """测试枚举值"""
        assert ExecutionEnvironment.HOST.value == "host"
        assert ExecutionEnvironment.DOCKER.value == "docker"
        assert ExecutionEnvironment.SANDBOX.value == "sandbox"

    def test_enum_comparison(self):
        """测试枚举比较"""
        assert ExecutionEnvironment.DOCKER == ExecutionEnvironment.DOCKER
        assert ExecutionEnvironment.HOST != ExecutionEnvironment.DOCKER


# ============================================================================
# 命令解析测试
# ============================================================================

class TestCommandParsing:
    """命令解析测试"""

    def test_builtin_prefix_detection(self):
        """测试内置命令前缀检测"""
        builtin_commands = [
            "toolkit list",
            "toolkit refresh",
            "todo buy milk",
            "memory important",
            "update_prompt new text",
        ]

        for cmd_str in builtin_commands:
            cmd = Command(raw=cmd_str)
            assert cmd.type == CommandType.BUILTIN, f"Failed for: {cmd_str}"

    def test_whitespace_handling(self):
        """测试空白字符处理"""
        cmd1 = Command(raw="  echo hello  ")
        cmd2 = Command(raw="echo hello")

        # 应该推断相同的类型
        assert cmd1.type == cmd2.type

    def test_case_sensitivity_in_builtin_detection(self):
        """测试内置命令检测大小写敏感"""
        cmd_lowercase = Command(raw="toolkit list")
        cmd_uppercase = Command(raw="TOOLKIT list")

        # 小写应该是 builtin
        assert cmd_lowercase.type == CommandType.BUILTIN
        # 大写可能不会被识别为 builtin
        assert cmd_uppercase.type != CommandType.BUILTIN or cmd_uppercase.type == CommandType.BASH


# ============================================================================
# Docker 命令构建测试
# ============================================================================

class TestDockerCommandBuilding:
    """Docker 命令构建测试"""

    def test_container_name_included(self):
        """测试容器名称包含在命令中"""
        cmd = Command(raw="test", working_dir="/app")
        docker_cmd = cmd.to_docker_command()

        # 容器名应该由 DockerExecutor 添加，这里只验证基础结构
        assert "docker" in docker_cmd
        assert "exec" in docker_cmd

    def test_working_directory_included(self):
        """测试工作目录包含在命令中"""
        cmd = Command(raw="test", working_dir="/custom/path")
        docker_cmd = cmd.to_docker_command()

        assert "-w" in docker_cmd
        assert "/custom/path" in docker_cmd

    def test_python_command_structure(self):
        """测试 Python 命令结构"""
        cmd = Command(raw="x = 1", type=CommandType.PYTHON)
        docker_cmd = cmd.to_docker_command()

        assert docker_cmd[-3:] == ["python3", "-c", "x = 1"]

    def test_bash_command_structure(self):
        """测试 Bash 命令结构"""
        cmd = Command(raw="ls -la", type=CommandType.BASH)
        docker_cmd = cmd.to_docker_command()

        assert docker_cmd[-3:] == ["bash", "-c", "ls -la"]


__all__ = []
