"""
依赖注入装饰器

提供 @inject 和 @singleton 装饰器用于依赖注入
"""

from functools import wraps
from typing import Type, TypeVar, Callable, Optional
from .container import Container, get_container


T = TypeVar("T")


def inject(**dependencies: Type) -> Callable:
    """
    依赖注入装饰器

    使用示例:
        @inject(logger=ILogger, config=IConfig)
        class MyService:
            def __init__(self, logger: ILogger, config: IConfig):
                self.logger = logger
                self.config = config
    """

    def decorator(cls: Type[T]) -> Type[T]:
        original_init = cls.__init__

        @wraps(original_init)
        def new_init(self, *args, **kwargs):
            container = get_container()

            # 从容器解析依赖
            for name, dependency_type in dependencies.items():
                if name not in kwargs:
                    try:
                        kwargs[name] = container.get(dependency_type)
                    except ValueError:
                        pass  # 依赖未注册，使用默认值

            original_init(self, *args, **kwargs)

        cls.__init__ = new_init
        return cls

    return decorator


def singleton(cls: Type[T]) -> Type[T]:
    """
    单例装饰器

    使用示例:
        @singleton
        class Config:
            pass
    """
    instances = {}

    @wraps(cls)
    def get_instance(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]

    # 添加获取实例的方法
    cls.get_instance = get_instance
    return cls


def register_service(interface: Type, implementation: Optional[Type] = None):
    """
    服务注册装饰器

    使用示例:
        @register_service(ILogger)
        class FileLogger:
            pass

        # 或者
        @register_service()
        class Database:
            pass
    """

    def decorator(cls: Type[T]) -> Type[T]:
        container = get_container()

        if interface is not None:
            container.register_singleton(interface, cls)
        else:
            # 注册自身
            container.register_singleton(cls, cls)

        return cls

    if implementation is None:
        # @register_service(ILogger) 的形式
        return decorator

    # @register_service() 的形式
    return decorator(implementation)
