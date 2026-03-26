"""
LLM 相关异常

定义 LLM 调用相关的异常
"""

from .base import AliceError


class LLMError(AliceError):
    """LLM 基础异常"""
    pass


class LLMConnectionError(LLMError):
    """LLM 连接错误"""
    pass


class LLMTimeoutError(LLMError):
    """LLM 超时错误"""
    pass


class LLMRateLimitError(LLMError):
    """LLM 速率限制错误"""
    pass


class LLMTokenLimitError(LLMError):
    """Token 超限错误"""
    pass


class LLMResponseError(LLMError):
    """LLM 响应解析错误"""
    pass


class LLMProviderNotFoundError(LLMError):
    """LLM 提供商未找到错误"""
    pass
