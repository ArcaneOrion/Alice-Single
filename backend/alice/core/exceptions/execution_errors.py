"""
执行相关异常

定义命令执行相关的异常
"""

from .base import AliceError


class ExecutionError(AliceError):
    """执行基础异常"""
    pass


class CommandNotAllowedError(ExecutionError):
    """命令不允许执行错误"""
    pass


class CommandTimeoutError(ExecutionError):
    """命令执行超时错误"""
    pass


class CommandInterruptError(ExecutionError):
    """命令执行中断错误"""
    pass


class DockerError(ExecutionError):
    """Docker 相关错误"""
    pass


class ContainerNotFoundError(DockerError):
    """容器未找到错误"""
    pass


class ImageNotFoundError(DockerError):
    """镜像未找到错误"""
    pass
