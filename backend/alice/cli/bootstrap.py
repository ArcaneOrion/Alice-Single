from __future__ import annotations

import json
import logging
from pathlib import Path

from backend.alice.application.agent import AliceAgent
from backend.alice.application.services import LifecycleService, OrchestrationService
from backend.alice.application.workflow import ChatWorkflow, WorkflowChain
from backend.alice.core.config.loader import load_config
from backend.alice.core.logging import configure_logging
from backend.alice.core.registry import get_llm_registry
from backend.alice.domain.llm.providers.base import ProviderCapability

logger = logging.getLogger(__name__)


def parse_request_header_profiles(profiles_str: str) -> list[dict]:
    """解析环境变量中的请求头轮询配置。"""
    if not profiles_str.strip():
        return []

    try:
        parsed = json.loads(profiles_str)
    except json.JSONDecodeError:
        import ast

        parsed = ast.literal_eval(profiles_str)

    if not isinstance(parsed, list) or not all(isinstance(item, dict) for item in parsed):
        raise ValueError("REQUEST_HEADER_PROFILES 必须是对象数组")

    return parsed


def configure_runtime_logging(*, console_level: str = "ERROR") -> None:
    """初始化后端日志配置。"""
    from dotenv import load_dotenv

    load_dotenv()
    settings = load_config()
    settings.logging.console_level = console_level
    configure_logging(settings.logging)


def create_agent_from_env(
    *,
    project_root: Path,
    harness_name: str | None = None,
    skill_source_name: str | None = None,
) -> AliceAgent:
    """基于配置创建 AliceAgent。"""
    from dotenv import load_dotenv

    load_dotenv()
    settings = load_config()
    settings.project_root = project_root

    if harness_name is not None:
        settings.harness.name = harness_name
    if skill_source_name is not None:
        settings.harness.skill_source_name = skill_source_name

    settings.llm.request_header_profiles = get_llm_registry().resolve_request_header_profiles(
        settings.llm.provider_name,
        settings.llm.base_url,
        settings.llm.request_header_profiles,
    )

    capabilities = None
    if not settings.llm.supports_tool_calling:
        capabilities = ProviderCapability(supports_tool_calling=False)

    if not settings.llm.api_key:
        raise ValueError("LLM 配置缺少 api_key")
    if not settings.llm.model_name:
        raise ValueError("LLM 配置缺少 model_name")

    orchestration = OrchestrationService.create_from_settings(settings, capabilities=capabilities)

    lifecycle = LifecycleService(
        project_root=project_root,
        backend=(orchestration.harness_bundle.backend if orchestration.harness_bundle else None),
    )

    workflow_chain = WorkflowChain()
    workflow_chain.add_workflow(
        ChatWorkflow(
            chat_service=orchestration.chat_service,
            execution_service=orchestration.execution_service,
            tool_registry=orchestration.tool_registry,
            function_calling_orchestrator=orchestration.function_calling_orchestrator,
            max_iterations=settings.workflow.max_iterations,
        )
    )

    return AliceAgent(
        orchestration_service=orchestration,
        lifecycle_service=lifecycle,
        workflow_chain=workflow_chain,
    )


__all__ = [
    "configure_runtime_logging",
    "create_agent_from_env",
    "parse_request_header_profiles",
]
