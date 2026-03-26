"""
LLM 提供商注册表

管理 LLM 提供商的注册
"""

from typing import Dict, Type, Optional, List, Callable
from dataclasses import dataclass
from abc import ABC, abstractmethod

from ..interfaces.llm_provider import LLMProvider


@dataclass
class LLMProviderSpec:
    """LLM 提供商规范"""
    name: str
    provider_class: Type[LLMProvider]
    description: str = ""
    base_url: str = ""
    models: List[str] = None

    def __post_init__(self):
        if self.models is None:
            self.models = []


@dataclass
class ModelConfig:
    """模型配置"""
    name: str
    provider: str
    api_key: str = ""
    base_url: str = ""
    max_tokens: int = 4096
    temperature: float = 0.7


class LLMRegistry(ABC):
    """LLM 注册表接口"""

    @abstractmethod
    def register_provider(self, spec: LLMProviderSpec) -> None:
        """注册 LLM 提供商"""
        ...

    @abstractmethod
    def unregister_provider(self, name: str) -> None:
        """注销 LLM 提供商"""
        ...

    @abstractmethod
    def get_provider(self, name: str) -> Optional[LLMProviderSpec]:
        """获取 LLM 提供商规范"""
        ...

    @abstractmethod
    def register_model(self, config: ModelConfig) -> None:
        """注册模型配置"""
        ...

    @abstractmethod
    def get_model(self, name: str) -> Optional[ModelConfig]:
        """获取模型配置"""
        ...

    @abstractmethod
    def list_providers(self) -> List[str]:
        """列出所有提供商"""
        ...

    @abstractmethod
    def list_models(self) -> List[str]:
        """列出所有模型"""
        ...


class InMemoryLLMRegistry(LLMRegistry):
    """内存 LLM 注册表实现"""

    # 预定义的提供商
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    AZURE = "azure"

    def __init__(self):
        self._providers: Dict[str, LLMProviderSpec] = {}
        self._models: Dict[str, ModelConfig] = {}

    def register_provider(self, spec: LLMProviderSpec) -> None:
        """注册 LLM 提供商"""
        self._providers[spec.name] = spec

    def unregister_provider(self, name: str) -> None:
        """注销 LLM 提供商"""
        if name in self._providers:
            del self._providers[name]

    def get_provider(self, name: str) -> Optional[LLMProviderSpec]:
        """获取 LLM 提供商规范"""
        return self._providers.get(name)

    def register_model(self, config: ModelConfig) -> None:
        """注册模型配置"""
        self._models[config.name] = config

    def get_model(self, name: str) -> Optional[ModelConfig]:
        """获取模型配置"""
        return self._models.get(name)

    def list_providers(self) -> List[str]:
        """列出所有提供商"""
        return list(self._providers.keys())

    def list_models(self) -> List[str]:
        """列出所有模型"""
        return list(self._models.keys())

    def get_models_by_provider(self, provider_name: str) -> List[ModelConfig]:
        """按提供商列出模型"""
        return [
            config for config in self._models.values()
            if config.provider == provider_name
        ]

    def clear(self) -> None:
        """清空所有注册"""
        self._providers.clear()
        self._models.clear()


# 全局 LLM 注册表实例
_global_llm_registry: Optional[InMemoryLLMRegistry] = None


def get_llm_registry() -> InMemoryLLMRegistry:
    """获取全局 LLM 注册表实例"""
    global _global_llm_registry
    if _global_llm_registry is None:
        _global_llm_registry = InMemoryLLMRegistry()
    return _global_llm_registry
