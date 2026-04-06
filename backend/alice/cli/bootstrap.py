from __future__ import annotations

import json
import logging
import os
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
    """基于当前环境变量创建与 execution 主链共享 backend owner 的 AliceAgent。"""
    from dotenv import load_dotenv

    load_dotenv()
    api_key = os.getenv("API_KEY", "")
    base_url = os.getenv("API_BASE_URL", "https://api-inference.modelscope.cn/v1/")
    model_name = os.getenv("MODEL_NAME", "")
    provider_name = os.getenv("PROVIDER_NAME", "openai")
    skill_source_name = skill_source_name or os.getenv("SKILL_SOURCE_NAME", "default")
    harness_name = harness_name or os.getenv("HARNESS_NAME", "docker")

    if not api_key:
        raise ValueError("API_KEY 环境变量未设置")
    if not model_name:
        raise ValueError("MODEL_NAME 环境变量未设置")

    request_header_profiles: list[dict] = []
    profiles_str = os.getenv("REQUEST_HEADER_PROFILES", "")
    if profiles_str:
        try:
            request_header_profiles = parse_request_header_profiles(profiles_str)
        except Exception:
            logger.warning("解析 REQUEST_HEADER_PROFILES 失败")

    request_header_profiles = get_llm_registry().resolve_request_header_profiles(
        provider_name,
        base_url,
        request_header_profiles,
    )

    capabilities = None
    if os.getenv("PROVIDER_SUPPORTS_TOOL_CALLING", "").lower() in ("false", "0", "no"):
        capabilities = ProviderCapability(supports_tool_calling=False)

    orchestration = OrchestrationService.create_from_config(
        api_key=api_key,
        base_url=base_url,
        model_name=model_name,
        project_root=project_root,
        extra_headers={},
        request_header_profiles=request_header_profiles,
        capabilities=capabilities,
        provider_name=provider_name,
        skill_source_name=skill_source_name,
        harness_name=harness_name,
    )

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
