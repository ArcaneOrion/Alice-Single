"""LangChain tool calling 适配层占位实现。

当前仓库未安装 LangChain 依赖，本模块仅提供受限边界：
- 把 registry schema 转成 provider 可消费的 tools 参数
- 保持 LangChain 仅停留在 adapter 层，后续依赖补齐后再接入 bind_tools
"""

from __future__ import annotations

from backend.alice.domain.execution.services.tool_registry import ToolRegistry


class LangChainToolCallingAdapter:
    """受限 adapter：当前只负责输出标准 tools schema。"""

    def __init__(self, tool_registry: ToolRegistry):
        self.tool_registry = tool_registry

    def build_tools_payload(self) -> list[dict]:
        return self.tool_registry.list_openai_tools()
