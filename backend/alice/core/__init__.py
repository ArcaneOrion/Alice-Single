"""
Alice Core - 核心基础设施包

提供接口定义、依赖注入容器、事件总线、注册表、配置系统、异常体系和日志系统
"""

# 接口定义
from . import interfaces

# 依赖注入
from . import container

# 事件总线
from . import event_bus

# 注册表
from . import registry

# 配置系统
from . import config

# 异常体系
from . import exceptions

# 日志系统
from . import logging

__all__ = [
    "interfaces",
    "container",
    "event_bus",
    "registry",
    "config",
    "exceptions",
    "logging",
]
