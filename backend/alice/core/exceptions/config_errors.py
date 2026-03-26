"""
配置相关异常

定义配置加载和验证相关的异常
"""

from .base import AliceError, ConfigurationError, ValidationError


class ConfigFileNotFoundError(ConfigurationError):
    """配置文件未找到错误"""
    pass


class ConfigParseError(ConfigurationError):
    """配置解析错误"""
    pass


class ConfigValidationError(ValidationError):
    """配置验证错误"""
    pass


class EnvVarNotFoundError(ConfigurationError):
    """环境变量未找到错误"""
    pass
