"""
编排服务

协调 Domain 层的各个服务，提供统一的应用层接口。
"""

import logging
from pathlib import Path
from typing import Optional

from backend.alice.domain.memory.services.memory_manager import MemoryManager
from backend.alice.domain.execution.services.execution_service import ExecutionService
from backend.alice.domain.llm.services.chat_service import ChatService
from backend.alice.domain.skills.services.skill_registry import SkillRegistry
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
        skill_registry: Optional[SkillRegistry] = None,
        llm_provider: Optional[OpenAIProvider] = None,
    ):
        """初始化编排服务

        Args:
            memory_manager: 内存管理器
            execution_service: 执行服务
            chat_service: 聊天服务
            skill_registry: 技能注册表
            llm_provider: LLM 提供商
        """
        self.memory_manager = memory_manager
        self.execution_service = execution_service
        self.chat_service = chat_service
        self.skill_registry = skill_registry
        self.llm_provider = llm_provider

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
        # 创建 LLM Provider
        llm_config = OpenAIConfig(
            api_key=api_key,
            base_url=base_url,
            model_name=model_name,
            extra_headers=extra_headers or {},
            request_header_profiles=request_header_profiles or [],
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
        docker_executor = DockerExecutor(config=docker_config)

        execution_service = ExecutionService(
            executor=docker_executor,
            snapshot_manager=None,  # 将在初始化后设置
        )

        # 加载系统提示词
        system_prompt = cls._load_prompt(str(project_root / prompt_path))

        # 创建聊天服务
        chat_service = ChatService(
            provider=llm_provider,
            system_prompt=system_prompt,
            max_history=50,
        )

        # 创建编排服务
        orchestration = cls(
            memory_manager=memory_manager,
            execution_service=execution_service,
            chat_service=chat_service,
            skill_registry=skill_registry,
            llm_provider=llm_provider,
        )

        # 设置 snapshot manager 到 execution service
        # (创建一个简单的适配器)
        execution_service.snapshot_manager = _SkillSnapshotAdapter(skill_registry)

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
        """刷新对话上下文

        重新加载内存和技能信息到上下文中。
        """
        if not self.chat_service:
            return

        # 构建记忆上下文
        memory_context_parts = []

        if self.memory_manager:
            working_content = self.memory_manager.get_working_content()
            stm_content = self.memory_manager.get_stm_content()
            ltm_content = self.memory_manager.get_ltm_content()

            if working_content:
                memory_context_parts.append(f"### 即时对话背景\n{working_content}")
            if stm_content:
                memory_context_parts.append(f"### 短期记忆\n{stm_content}")
            if ltm_content:
                memory_context_parts.append(f"### 长期记忆\n{ltm_content}")

        # 构建技能索引
        if self.skill_registry:
            skills_summary = self.skill_registry.list_skills_summary()
            memory_context_parts.append(f"### 技能索引\n{skills_summary}")

        if memory_context_parts:
            memory_context = "【记忆与背景信息注入】\n\n" + "\n\n".join(memory_context_parts)

            # 更新聊天服务的消息历史
            # 保持最新的消息，添加内存上下文
            messages = self.chat_service.messages
            if len(messages) > 0:
                # 保留系统消息
                system_msg = None
                if messages and messages[0].role == "system":
                    system_msg = messages[0]

                # 保留最近的消息
                recent_messages = [m for m in messages if m.role != "system"][-4:]

                # 重建消息列表
                self.chat_service.clear_history(keep_system=False)
                if system_msg:
                    self.chat_service.add_message(system_msg)
                self.chat_service.add_user_message(memory_context)
                for msg in recent_messages:
                    self.chat_service.add_message(msg)


class _SkillSnapshotAdapter:
    """技能快照适配器

    适配 SkillRegistry 到 ExecutionService 需要的 snapshot_manager 接口。
    """

    def __init__(self, skill_registry: SkillRegistry):
        self._skill_registry = skill_registry

    def read_skill_file(self, relative_path: str) -> str | None:
        """读取技能文件"""
        skill = self._skill_registry.get_skill(relative_path.split("/")[0])
        if skill:
            return skill.content
        return None


__all__ = ["OrchestrationService"]
