"""
依赖注入容器

实现轻量级依赖注入容器，支持单例和工厂模式
"""

from typing import Type, TypeVar, Callable, Dict, Any, Optional
from dataclasses import dataclass
from abc import ABC


T = TypeVar("T")


@dataclass
class ServiceDescriptor:
    """服务描述符"""
    interface: Type
    implementation: Type | Callable
    is_singleton: bool = True
    instance: Any = None
    factory: Callable | None = None


class Container:
    """
    依赖注入容器

    使用示例:
        container = Container()

        # 注册单例
        container.register_singleton(ILogger, FileLogger)

        # 注册工厂
        container.register_factory(IDatabase, lambda: Database("localhost"))

        # 解析服务
        logger = container.get(ILogger)
    """

    def __init__(self):
        self._services: Dict[Type, ServiceDescriptor] = {}
        self._singletons: Dict[Type, Any] = {}

    def register_singleton(
        self,
        interface: Type[T],
        implementation: Type[T] | Callable[[], T],
        instance: Optional[T] = None
    ) -> None:
        """
        注册单例服务

        Args:
            interface: 接口类型
            implementation: 实现类型或工厂函数
            instance: 预创建的实例（可选）
        """
        descriptor = ServiceDescriptor(
            interface=interface,
            implementation=implementation,
            is_singleton=True,
            instance=instance
        )
        self._services[interface] = descriptor

        if instance is not None:
            self._singletons[interface] = instance

    def register_factory(
        self,
        interface: Type[T],
        factory: Callable[[], T]
    ) -> None:
        """
        注册工厂服务

        Args:
            interface: 接口类型
            factory: 工厂函数
        """
        descriptor = ServiceDescriptor(
            interface=interface,
            implementation=factory,
            is_singleton=False,
            factory=factory
        )
        self._services[interface] = descriptor

    def register_transient(
        self,
        interface: Type[T],
        implementation: Type[T]
    ) -> None:
        """
        注册瞬态服务（每次解析创建新实例）

        Args:
            interface: 接口类型
            implementation: 实现类型
        """
        descriptor = ServiceDescriptor(
            interface=interface,
            implementation=implementation,
            is_singleton=False
        )
        self._services[interface] = descriptor

    def get(self, interface: Type[T]) -> T:
        """
        解析服务

        Args:
            interface: 接口类型

        Returns:
            服务实例

        Raises:
            ValueError: 如果服务未注册
        """
        if interface not in self._services:
            raise ValueError(f"Service {interface.__name__} is not registered")

        descriptor = self._services[interface]

        # 单例模式
        if descriptor.is_singleton:
            if interface in self._singletons:
                return self._singletons[interface]

            # 如果已有预创建实例
            if descriptor.instance is not None:
                return descriptor.instance

            # 创建新实例
            instance = self._create_instance(descriptor)
            self._singletons[interface] = instance
            return instance

        # 工厂模式
        if descriptor.factory is not None:
            return descriptor.factory()

        # 瞬态模式 - 每次创建新实例
        return self._create_instance(descriptor)

    def _create_instance(self, descriptor: ServiceDescriptor) -> Any:
        """创建服务实例"""
        implementation = descriptor.implementation

        # 如果是可调用对象（类或函数），直接调用
        if callable(implementation):
            # 尝试从容器注入构造函数参数
            try:
                return implementation()
            except TypeError:
                # 如果需要参数，尝试从容器解析
                import inspect
                sig = inspect.signature(implementation)
                kwargs = {}
                for param_name, param in sig.parameters.items():
                    if param.annotation != inspect.Parameter.empty:
                        # 尝试从容器获取依赖
                        try:
                            kwargs[param_name] = self.get(param.annotation)
                        except ValueError:
                            pass

                return implementation(**kwargs)

        raise TypeError(f"Cannot create instance of {implementation}")

    def has(self, interface: Type) -> bool:
        """检查服务是否已注册"""
        return interface in self._services

    def clear(self) -> None:
        """清空所有注册的服务"""
        self._services.clear()
        self._singletons.clear()


# 全局容器实例
_global_container: Optional[Container] = None


def get_container() -> Container:
    """获取全局容器实例"""
    global _global_container
    if _global_container is None:
        _global_container = Container()
    return _global_container


def reset_container() -> None:
    """重置全局容器"""
    global _global_container
    _global_container = None
