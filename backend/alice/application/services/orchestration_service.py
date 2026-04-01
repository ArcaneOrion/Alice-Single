"""
编排服务

协调 Domain 层的各个服务，提供统一的应用层接口。
"""

from __future__ import annotations

import logging
from importlib import import_module
from pathlib import Path
from typing import Any, Optional

RuntimeContextBuilder = import_module(
    "backend.alice.application.runtime"
).RuntimeContextBuilder
from backend.alice.domain.memory.services.memory_manager import MemoryManager
from backend.alice.domain.execution.services.execution_service import ExecutionService
from backend.alice.domain.execution.services.tool_registry import ToolRegistry
from backend.alice.domain.llm.services.chat_service import ChatService
from backend.alice.domain.llm.services.stream_service import StreamService
from backend.alice.domain.skills.services.skill_cache import SkillCache
from backend.alice.domain.skills.services.skill_registry import SkillRegistry
from backend.alice.domain.llm.providers.base import ProviderCapability
from backend.alice.domain.llm.providers.openai_provider import OpenAIProvider, OpenAIConfig


logger = logging.getLogger(__name__)


class OrchestrationService:
    """编排服务

    协调 Domain 层服务，提供统一的应用层接口。
    """

    def __init__(
        self,
        memory_manager: Optional[MemoryManager] = None,
        execution_service: Optional[ExecutionService] = None,
        chat_service: Optional[ChatService] = None,
        stream_service: Optional[StreamService] = None,
        skill_registry: Optional[SkillRegistry] = None,
        llm_provider: Optional[OpenAIProvider] = None,
        tool_registry: Optional[ToolRegistry] = None,
        function_calling_orchestrator: Any | None = None,
    ):
        """初始化编排服务

        Args:
            memory_manager: 内存管理器
            execution_service: 执行服务
            chat_service: 聊天服务
            skill_registry: 技能注册表
            llm_provider: LLM 提供商
        """
        self.memory_manager: Optional[MemoryManager] = memory_manager
        self.execution_service: Optional[ExecutionService] = execution_service
        self.chat_service: Optional[ChatService] = chat_service
        self.stream_service: Optional[StreamService] = stream_service
        self.skill_registry: Optional[SkillRegistry] = skill_registry
        self.llm_provider: Optional[OpenAIProvider] = llm_provider
        self.tool_registry: Optional[ToolRegistry] = tool_registry
        self.function_calling_orchestrator: Any | None = function_calling_orchestrator
        self.runtime_context_builder = RuntimeContextBuilder()
        self.runtime_context: dict[str, object] = {}

    @classmethod
    def create_from_config(
        cls,
        api_key: str,
        base_url: str,
        model_name: str,
        project_root: Path,
        prompt_path: str = "prompts/alice.md",
        working_memory_path: str = "memory/working_memory.md",
        stm_path: str = "memory/short_term_memory.md",
        ltm_path: str = "memory/alice_memory.md",
        todo_path: str = "memory/todo.md",
        max_working_rounds: int = 30,
        stm_days_to_keep: int = 7,
        extra_headers: dict | None = None,
        request_header_profiles: list[dict] | None = None,
        capabilities: ProviderCapability | None = None,
        _todo_path: str | None = None,
    ) -> "OrchestrationService":
        """从配置创建编排服务

        Args:
            api_key: API 密钥
            base_url: API 基础 URL
            model_name: 模型名称
            project_root: 项目根目录
            prompt_path: 提示词路径
            working_memory_path: 工作内存路径
            stm_path: 短期记忆路径
            ltm_path: 长期记忆路径
            todo_path: 任务清单路径
            max_working_rounds: 工作内存最大轮数
            stm_days_to_keep: 短期记忆保留天数
            extra_headers: 额外请求头
            request_header_profiles: 请求头轮换配置

        Returns:
            编排服务实例
        """
        _ = todo_path, _todo_path

        # 创建 LLM Provider
        llm_config = OpenAIConfig(
            api_key=api_key,
            base_url=base_url,
            model_name=model_name,
            extra_headers=extra_headers or {},
            request_header_profiles=request_header_profiles or [],
            capabilities=capabilities,
        )
        llm_provider = OpenAIProvider(config=llm_config)

        # 创建技能注册表
        skill_registry = SkillRegistry()
        skill_registry.refresh()

        # 创建内存管理器
        memory_manager = MemoryManager(
            working_memory_path=str(project_root / working_memory_path),
            stm_path=str(project_root / stm_path),
            ltm_path=str(project_root / ltm_path),
            llm_provider=llm_provider,
            max_working_rounds=max_working_rounds,
            stm_days_to_keep=stm_days_to_keep,
        )

        # 创建执行服务
        from backend.alice.domain.execution.executors.docker_executor import DockerExecutor
        from backend.alice.infrastructure.docker.config import DockerConfig

        docker_config = DockerConfig(project_root=project_root)
        docker_executor = DockerExecutor(
            container_name=docker_config.container.name,
            docker_image=docker_config.image_name,
            work_dir=docker_config.container.work_dir,
        )

        tool_registry = ToolRegistry(skill_registry)

        execution_service = ExecutionService(
            executor=docker_executor,
            snapshot_manager=None,  # 将在初始化后设置
            tool_registry=tool_registry,
        )

        # 加载系统提示词
        system_prompt = cls._load_prompt(str(project_root / prompt_path))

        # 创建聊天服务
        chat_service = ChatService(
            provider=llm_provider,
            system_prompt=system_prompt,
            max_history=50,
        )
        stream_service = StreamService(provider=llm_provider)
        function_calling_orchestrator_cls = import_module(
            "backend.alice.application.workflow.function_calling_orchestrator"
        ).FunctionCallingOrchestrator
        function_calling_orchestrator = function_calling_orchestrator_cls(
            execution_service=execution_service,
            tool_registry=tool_registry,
        )

        # 创建编排服务
        orchestration = cls(
            memory_manager=memory_manager,
            execution_service=execution_service,
            chat_service=chat_service,
            stream_service=stream_service,
            skill_registry=skill_registry,
            llm_provider=llm_provider,
            tool_registry=tool_registry,
            function_calling_orchestrator=function_calling_orchestrator,
        )

        execution_service.set_skill_snapshot(skill_registry, SkillCache())

        return orchestration

    @staticmethod
    def _load_prompt(prompt_path: str) -> str:
        """加载提示词文件

        Args:
            prompt_path: 提示词文件路径

        Returns:
            提示词内容
        """
        try:
            if Path(prompt_path).exists():
                with open(prompt_path, "r", encoding="utf-8") as f:
                    return f.read()
        except Exception as e:
            logger.warning(f"加载提示词失败: {e}")
        return "你是一个 AI 助手。"

    def refresh_context(self) -> None:
        """刷新结构化运行时上下文，不污染持久消息历史。"""
        if not self.chat_service:
            return

        runtime_context = self.runtime_context_builder.build(
            system_prompt=self.chat_service.system_prompt,
            current_question="",
            messages=self.chat_service.messages,
            request_metadata={},
            memory_manager=self.memory_manager,
            skill_registry=self.skill_registry,
            tool_registry=self.tool_registry,
        )
        self.runtime_context = runtime_context.to_dict()

        set_runtime_context = getattr(self.chat_service, "set_runtime_context", None)
        if callable(set_runtime_context):
            set_runtime_context(self.runtime_context)


__all__ = ["OrchestrationService"]
