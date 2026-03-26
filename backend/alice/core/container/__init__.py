"""
依赖注入容器包

提供轻量级依赖注入容器和相关装饰器
"""

from .container import Container, get_container, reset_container
from .decorators import inject, singleton, register_service

__all__ = [
    "Container",
    "get_container",
    "reset_container",
    "inject",
    "singleton",
    "register_service",
]
