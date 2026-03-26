"""
异常体系定义

定义项目中所有自定义异常的基类
"""

from typing import Optional, Any


class AliceError(Exception):
    """Alice 基础异常类"""

    def __init__(self, message: str, code: Optional[str] = None, details: Optional[dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.code = code or self.__class__.__name__
        self.details = details or {}

    def __str__(self):
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式"""
        return {
            "error_type": self.__class__.__name__,
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }


class ConfigurationError(AliceError):
    """配置错误"""
    pass


class ValidationError(AliceError):
    """验证错误"""
    pass


class InitializationError(AliceError):
    """初始化错误"""
    pass
