"""
依赖注入容器单元测试

测试 Container 类的服务注册、解析和生命周期管理
"""

import pytest

from backend.alice.core.container import (
    Container,
    ServiceDescriptor,
    get_container,
    reset_container,
)


# ============================================================================
# 测试类定义
# ============================================================================

class TestService:
    """测试服务类"""
    def __init__(self):
        self.value = "test"

    def greet(self) -> str:
        return "hello"


class AnotherTestService:
    """另一个测试服务类"""
    def __init__(self):
        self.name = "another"


class ServiceWithDependency:
    """带依赖的服务类"""
    def __init__(self, test_service: TestService):
        self.test_service = test_service


class FactoryService:
    """工厂服务类"""
    def __init__(self, value: str):
        self.value = value


# ============================================================================
# 容器基础功能测试
# ============================================================================

class TestContainerBasics:
    """容器基础功能测试"""

    def test_container_creation(self):
        """测试容器创建"""
        container = Container()
        assert container is not None
        assert len(container._services) == 0
        assert len(container._singletons) == 0

    def test_register_singleton(self):
        """测试注册单例服务"""
        container = Container()
        container.register_singleton(TestService, TestService)

        assert container.has(TestService)
        assert TestService in container._services

    def test_register_factory(self):
        """测试注册工厂服务"""
        container = Container()
        factory = lambda: FactoryService("factory_value")
        container.register_factory(FactoryService, factory)

        assert container.has(FactoryService)

    def test_register_transient(self):
        """测试注册瞬态服务"""
        container = Container()
        container.register_transient(TestService, TestService)

        assert container.has(TestService)
        descriptor = container._services[TestService]
        assert not descriptor.is_singleton


# ============================================================================
# 单例模式测试
# ============================================================================

class TestSingletonPattern:
    """单例模式测试"""

    def test_get_singleton_returns_same_instance(self):
        """测试单例返回同一实例"""
        container = Container()
        container.register_singleton(TestService, TestService)

        instance1 = container.get(TestService)
        instance2 = container.get(TestService)

        assert instance1 is instance2
        assert id(instance1) == id(instance2)

    def test_singleton_with_pre_created_instance(self):
        """测试使用预创建实例的单例"""
        container = Container()
        pre_created = TestService()
        pre_created.value = "pre_created"

        container.register_singleton(TestService, TestService, instance=pre_created)

        instance = container.get(TestService)
        assert instance is pre_created
        assert instance.value == "pre_created"

    def test_singleton_stored_in_cache(self):
        """测试单例存储在缓存中"""
        container = Container()
        container.register_singleton(TestService, TestService)

        container.get(TestService)

        assert TestService in container._singletons
        assert len(container._singletons) == 1


# ============================================================================
# 瞬态模式测试
# ============================================================================

class TestTransientPattern:
    """瞬态模式测试"""

    def test_transient_returns_new_instance(self):
        """测试瞬态返回新实例"""
        container = Container()
        container.register_transient(TestService, TestService)

        instance1 = container.get(TestService)
        instance2 = container.get(TestService)

        assert instance1 is not instance2
        assert id(instance1) != id(instance2)

    def test_transient_not_cached(self):
        """测试瞬态不缓存"""
        container = Container()
        container.register_transient(TestService, TestService)

        container.get(TestService)
        container.get(TestService)

        assert TestService not in container._singletons


# ============================================================================
# 工厂模式测试
# ============================================================================

class TestFactoryPattern:
    """工厂模式测试"""

    def test_factory_creates_instance(self):
        """测试工厂创建实例"""
        container = Container()
        factory = lambda: FactoryService("custom_value")
        container.register_factory(FactoryService, factory)

        instance = container.get(FactoryService)

        assert isinstance(instance, FactoryService)
        assert instance.value == "custom_value"

    def test_factory_called_each_time(self):
        """测试工厂每次调用"""
        container = Container()
        call_count = [0]

        def counting_factory():
            call_count[0] += 1
            return FactoryService(f"value_{call_count[0]}")

        container.register_factory(FactoryService, counting_factory)

        instance1 = container.get(FactoryService)
        instance2 = container.get(FactoryService)

        assert call_count[0] == 2
        assert instance1.value == "value_1"
        assert instance2.value == "value_2"


# ============================================================================
# 错误处理测试
# ============================================================================

class TestErrorHandling:
    """错误处理测试"""

    def test_get_unregistered_service_raises_error(self):
        """测试获取未注册服务抛出错误"""
        container = Container()

        with pytest.raises(ValueError, match="Service .* is not registered"):
            container.get(TestService)

    def test_clear_removes_all_services(self):
        """测试清除所有服务"""
        container = Container()
        container.register_singleton(TestService, TestService)
        container.register_singleton(AnotherTestService, AnotherTestService)
        container.get(TestService)

        container.clear()

        assert len(container._services) == 0
        assert len(container._singletons) == 0
        assert not container.has(TestService)


# ============================================================================
# 全局容器测试
# ============================================================================

class TestGlobalContainer:
    """全局容器测试"""

    def test_get_container_returns_same_instance(self):
        """测试获取全局容器返回同一实例"""
        reset_container()
        container1 = get_container()
        container2 = get_container()

        assert container1 is container2

    def test_reset_container_creates_new_instance(self):
        """测试重置容器创建新实例"""
        reset_container()
        container1 = get_container()
        container1.register_singleton(TestService, TestService)

        reset_container()
        container2 = get_container()

        assert container1 is not container2
        assert not container2.has(TestService)


# ============================================================================
# 服务描述符测试
# ============================================================================

class TestServiceDescriptor:
    """服务描述符测试"""

    def test_service_descriptor_defaults(self):
        """测试服务描述符默认值"""
        descriptor = ServiceDescriptor(
            interface=TestService,
            implementation=TestService
        )

        assert descriptor.interface == TestService
        assert descriptor.implementation == TestService
        assert descriptor.is_singleton is True
        assert descriptor.instance is None
        assert descriptor.factory is None

    def test_service_descriptor_with_factory(self):
        """测试带工厂的服务描述符"""
        factory = lambda: FactoryService("test")
        descriptor = ServiceDescriptor(
            interface=FactoryService,
            implementation=factory,
            is_singleton=False,
            factory=factory
        )

        assert descriptor.is_singleton is False
        assert descriptor.factory is factory
        assert descriptor.implementation is factory


__all__ = []
