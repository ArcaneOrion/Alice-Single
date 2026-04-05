"""
LLM 提供商注册表

管理 LLM 提供商的注册与实例构建。
"""

from __future__ import annotations

from typing import Dict, Optional, List, Callable, Any
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

from backend.alice.domain.llm.providers.base import BaseLLMProvider, ProviderCapability
from backend.alice.domain.llm.providers.openai_provider import (
    OpenAIConfig,
    OpenAIProvider,
    resolve_request_header_profiles as resolve_openai_request_header_profiles,
)


@dataclass(frozen=True)
class ProviderCreateOptions:
    """Provider 构建参数。"""

    api_key: str
    base_url: str
    model_name: str
    extra_headers: dict[str, Any] = field(default_factory=dict)
    request_header_profiles: list[dict[str, Any]] = field(default_factory=list)
    capabilities: ProviderCapability | None = None


@dataclass
class LLMProviderSpec:
    """LLM 提供商规范。"""

    name: str
    factory: Callable[[ProviderCreateOptions], BaseLLMProvider]
    description: str = ""
    base_url: str = ""
    models: list[str] = field(default_factory=list)
    resolve_request_header_profiles: Callable[[str, list[dict[str, Any]] | None], list[dict[str, Any]]] | None = None


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
    """LLM 注册表接口。"""

    @abstractmethod
    def register_provider(self, spec: LLMProviderSpec) -> None:
        """注册 LLM 提供商。"""
        ...

    @abstractmethod
    def unregister_provider(self, name: str) -> None:
        """注销 LLM 提供商。"""
        ...

    @abstractmethod
    def get_provider(self, name: str) -> Optional[LLMProviderSpec]:
        """获取 LLM 提供商规范。"""
        ...

    @abstractmethod
    def create_provider(self, name: str, options: ProviderCreateOptions) -> BaseLLMProvider:
        """创建 provider 实例。"""
        ...

    @abstractmethod
    def resolve_request_header_profiles(
        self,
        provider_name: str,
        base_url: str,
        configured_profiles: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """解析 provider 最终生效的请求头配置。"""
        ...

    @abstractmethod
    def register_model(self, config: ModelConfig) -> None:
        """注册模型配置。"""
        ...

    @abstractmethod
    def get_model(self, name: str) -> Optional[ModelConfig]:
        """获取模型配置。"""
        ...

    @abstractmethod
    def list_providers(self) -> List[str]:
        """列出所有提供商。"""
        ...

    @abstractmethod
    def list_models(self) -> List[str]:
        """列出所有模型。"""
        ...


def _create_openai_provider(options: ProviderCreateOptions) -> BaseLLMProvider:
    config = OpenAIConfig(
        api_key=options.api_key,
        base_url=options.base_url,
        model_name=options.model_name,
        extra_headers=options.extra_headers,
        request_header_profiles=options.request_header_profiles,
        capabilities=options.capabilities,
    )
    return OpenAIProvider(config=config)


class InMemoryLLMRegistry(LLMRegistry):
    """内存 LLM 注册表实现。"""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    AZURE = "azure"

    def __init__(self):
        self._providers: Dict[str, LLMProviderSpec] = {}
        self._models: Dict[str, ModelConfig] = {}
        self._register_default_providers()

    def _register_default_providers(self) -> None:
        if self.OPENAI not in self._providers:
            self.register_provider(
                LLMProviderSpec(
                    name=self.OPENAI,
                    factory=_create_openai_provider,
                    description="OpenAI 兼容 provider",
                    resolve_request_header_profiles=resolve_openai_request_header_profiles,
                )
            )

    def register_provider(self, spec: LLMProviderSpec) -> None:
        """注册 LLM 提供商。"""
        self._providers[spec.name] = spec

    def unregister_provider(self, name: str) -> None:
        """注销 LLM 提供商。"""
        if name in self._providers:
            del self._providers[name]

    def get_provider(self, name: str) -> Optional[LLMProviderSpec]:
        """获取 LLM 提供商规范。"""
        return self._providers.get(name)

    def create_provider(self, name: str, options: ProviderCreateOptions) -> BaseLLMProvider:
        """创建 provider 实例。"""
        spec = self.get_provider(name)
        if spec is None:
            raise ValueError(f"未注册的 LLM provider: {name}")
        return spec.factory(options)

    def resolve_request_header_profiles(
        self,
        provider_name: str,
        base_url: str,
        configured_profiles: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """解析 provider 最终生效的请求头配置。"""
        spec = self.get_provider(provider_name)
        if spec is None:
            raise ValueError(f"未注册的 LLM provider: {provider_name}")
        if spec.resolve_request_header_profiles is None:
            return [dict(profile) for profile in (configured_profiles or [])]
        return spec.resolve_request_header_profiles(base_url, configured_profiles)

    def register_model(self, config: ModelConfig) -> None:
        """注册模型配置。"""
        self._models[config.name] = config

    def get_model(self, name: str) -> Optional[ModelConfig]:
        """获取模型配置。"""
        return self._models.get(name)

    def list_providers(self) -> List[str]:
        """列出所有提供商。"""
        return list(self._providers.keys())

    def list_models(self) -> List[str]:
        """列出所有模型。"""
        return list(self._models.keys())

    def get_models_by_provider(self, provider_name: str) -> List[ModelConfig]:
        """按提供商列出模型。"""
        return [
            config for config in self._models.values()
            if config.provider == provider_name
        ]

    def clear(self) -> None:
        """清空所有注册。"""
        self._providers.clear()
        self._models.clear()
        self._register_default_providers()


_global_llm_registry: Optional[InMemoryLLMRegistry] = None


def get_llm_registry() -> InMemoryLLMRegistry:
    """获取全局 LLM 注册表实例。"""
    global _global_llm_registry
    if _global_llm_registry is None:
        _global_llm_registry = InMemoryLLMRegistry()
    return _global_llm_registry


__all__ = [
    "ProviderCreateOptions",
    "LLMProviderSpec",
    "ModelConfig",
    "LLMRegistry",
    "InMemoryLLMRegistry",
    "get_llm_registry",
]
