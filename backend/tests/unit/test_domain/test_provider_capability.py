"""Provider Capability 单元测试"""

import pytest

# 先导入 application 层避免循环导入
from backend.alice.application.dto.requests import RequestContext  # noqa: F401
from backend.alice.domain.llm.providers.base import (
    BaseLLMProvider,
    ProviderCapability,
)
from backend.alice.domain.llm.services.stream_service import (
    build_tool_kwargs,
    supports_structured_tool_calling,
)


class _StubProvider(BaseLLMProvider):
    """用于测试的最小 provider stub。"""

    def _make_chat_request(self, messages, stream=False, **kwargs):
        return None

    def _extract_stream_chunks(self, response):
        yield from ()


class TestProviderCapabilityDefaults:
    def test_default_capabilities(self):
        cap = ProviderCapability()
        assert cap.supports_tool_calling is True
        assert cap.supports_streaming is True
        assert cap.supports_usage_in_stream is True
        assert cap.supports_thinking is False
        assert cap.supports_tool_call_delta is True
        assert cap.supports_extra_headers is True

    def test_frozen(self):
        cap = ProviderCapability()
        with pytest.raises(AttributeError):
            cap.supports_tool_calling = False


class TestProviderCapabilityOnProvider:
    def test_provider_default_capabilities(self):
        provider = _StubProvider("test-model")
        assert provider.capabilities.supports_tool_calling is True

    def test_provider_custom_capabilities(self):
        cap = ProviderCapability(supports_tool_calling=False, supports_thinking=True)
        provider = _StubProvider("test-model", capabilities=cap)
        assert provider.capabilities.supports_tool_calling is False
        assert provider.capabilities.supports_thinking is True

    def test_provider_none_capabilities_uses_default(self):
        provider = _StubProvider("test-model", capabilities=None)
        assert provider.capabilities.supports_tool_calling is True


class TestCapabilityGating:
    def test_supports_tool_calling_true(self):
        provider = _StubProvider("gpt-4")
        assert supports_structured_tool_calling(provider) is True

    def test_supports_tool_calling_false(self):
        cap = ProviderCapability(supports_tool_calling=False)
        provider = _StubProvider("deepseek-reasoner", capabilities=cap)
        assert supports_structured_tool_calling(provider) is False

    def test_build_tool_kwargs_no_tools_passes(self):
        """无工具时，即使不支持 tool calling 也不报错。"""
        cap = ProviderCapability(supports_tool_calling=False)
        provider = _StubProvider("no-tools-model", capabilities=cap)
        result = build_tool_kwargs(provider, tools=[])
        assert result == {}

    def test_build_tool_kwargs_with_tools_unsupported_raises(self):
        """有工具但不支持 tool calling 时应报错。"""
        cap = ProviderCapability(supports_tool_calling=False)
        provider = _StubProvider("no-tools-model", capabilities=cap)
        with pytest.raises(ValueError, match="不支持结构化 tool calling"):
            build_tool_kwargs(provider, tools=[{"type": "function", "function": {"name": "test"}}])

    def test_build_tool_kwargs_with_tools_supported(self):
        """有工具且支持 tool calling 时正常构建。"""
        provider = _StubProvider("gpt-4")
        result = build_tool_kwargs(
            provider,
            tools=[{"type": "function", "function": {"name": "test"}}],
        )
        assert result["tools"] == [{"type": "function", "function": {"name": "test"}}]
        assert result["tool_choice"] == "auto"
