"""
内存相关异常

定义内存操作相关的异常
"""

from .base import AliceError


class MemoryError(AliceError):
    """内存基础异常"""
    pass


class MemoryNotFoundError(MemoryError):
    """内存未找到错误"""
    pass


class MemoryStoreError(MemoryError):
    """内存存储错误"""
    pass


class MemoryValidationError(MemoryError):
    """内存验证错误"""
    pass


class MemoryDistillationError(MemoryError):
    """内存提炼错误"""
    pass
