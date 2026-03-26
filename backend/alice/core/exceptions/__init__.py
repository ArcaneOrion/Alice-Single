"""
异常体系包

提供项目中所有自定义异常类
"""

from .base import (
    AliceError,
    ConfigurationError,
    ValidationError,
    InitializationError,
)
from .llm_errors import (
    LLMError,
    LLMConnectionError,
    LLMTimeoutError,
    LLMRateLimitError,
    LLMTokenLimitError,
    LLMResponseError,
    LLMProviderNotFoundError,
)
from .memory_errors import (
    MemoryError,
    MemoryNotFoundError,
    MemoryStoreError,
    MemoryValidationError,
    MemoryDistillationError,
)
from .execution_errors import (
    ExecutionError,
    CommandNotAllowedError,
    CommandTimeoutError,
    CommandInterruptError,
    DockerError,
    ContainerNotFoundError,
    ImageNotFoundError,
)
from .config_errors import (
    ConfigFileNotFoundError,
    ConfigParseError,
    ConfigValidationError,
    EnvVarNotFoundError,
)

__all__ = [
    # 基础异常
    "AliceError",
    "ConfigurationError",
    "ValidationError",
    "InitializationError",
    # LLM 异常
    "LLMError",
    "LLMConnectionError",
    "LLMTimeoutError",
    "LLMRateLimitError",
    "LLMTokenLimitError",
    "LLMResponseError",
    "LLMProviderNotFoundError",
    # 内存异常
    "MemoryError",
    "MemoryNotFoundError",
    "MemoryStoreError",
    "MemoryValidationError",
    "MemoryDistillationError",
    # 执行异常
    "ExecutionError",
    "CommandNotAllowedError",
    "CommandTimeoutError",
    "CommandInterruptError",
    "DockerError",
    "ContainerNotFoundError",
    "ImageNotFoundError",
    # 配置异常
    "ConfigFileNotFoundError",
    "ConfigParseError",
    "ConfigValidationError",
    "EnvVarNotFoundError",
]
