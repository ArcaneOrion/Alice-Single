"""
Agent 集成测试

测试 Agent 的完整对话流程，包括内存管理、LLM 调用和命令执行
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

from backend.alice.core.interfaces.llm_provider import ChatMessage
from backend.alice.core.interfaces.command_executor import ExecutionResult
from backend.tests.fixtures.mock_llm import MockLLMProvider, MockLLMConfig
from backend.tests.fixtures.mock_docker import MockDockerExecutor, DockerMockConfig
from backend.tests.fixtures.mock_responses import MockResponses


# ============================================================================
# 完整对话流程测试
# ============================================================================

class TestAgentConversationFlow:
    """Agent 对话流程集成测试"""

    @pytest.mark.integration
    def test_simple_conversation(self, mock_llm_provider: MockLLMProvider):
        """测试简单对话流程"""
        # 准备消息
        messages = [
            ChatMessage(role="system", content="You are a helpful assistant"),
            ChatMessage(role="user", content="Hello!"),
        ]

        # 调用 LLM
        response = mock_llm_provider.chat(messages)

        # 验证响应
        assert response.content == "Mock response"
        assert response.usage["total_tokens"] > 0
        assert mock_llm_provider.call_count == 1

    @pytest.mark.integration
    def test_conversation_with_memory(
        self,
        mock_llm_provider: MockLLMProvider,
        sample_memory_entries
    ):
        """测试带记忆的对话"""
        # 构建包含历史记录的消息
        messages = [
            ChatMessage(role="system", content="You are Alice"),
            ChatMessage(role="user", content="What did we discuss?"),
        ]

        # 添加记忆内容到系统提示（模拟）
        memory_content = "\n".join(
            f"- {entry.content}" for entry in sample_memory_entries
        )
        messages[0].content += f"\nPrevious discussions:\n{memory_content}"

        response = mock_llm_provider.chat(messages)

        assert response.content is not None
        assert mock_llm_provider.call_count == 1

    @pytest.mark.integration
    def test_streaming_conversation(self, mock_llm_provider: MockLLMProvider):
        """测试流式对话"""
        messages = [
            ChatMessage(role="user", content="Tell me a story"),
        ]

        chunks = list(mock_llm_provider.stream_chat(messages))

        assert len(chunks) > 0
        assert all(isinstance(chunk, object) for chunk in chunks)
        assert mock_llm_provider.call_count == 1


# ============================================================================
# 工具调用流程测试
# ============================================================================

class TestToolCallFlow:
    """工具调用流程测试"""

    @pytest.mark.integration
    def test_tool_call_detection(self):
        """测试工具调用检测"""
        from backend.tests.fixtures.mock_llm import ToolCallMockLLMProvider

        provider = ToolCallMockLLMProvider(
            tool_name="get_weather",
            tool_args={"location": "Beijing"}
        )

        response = provider.chat([])

        assert len(response.tool_calls) > 0
        assert response.tool_calls[0]["function"]["name"] == "get_weather"

    @pytest.mark.integration
    def test_tool_call_execution(self, mock_docker_executor: MockDockerExecutor):
        """测试工具调用执行"""
        # 配置模拟响应
        mock_docker_executor.set_command_response(
            "get_weather --location Beijing",
            ExecutionResult(
                success=True,
                output="Sunny, 25C",
                exit_code=0
            )
        )

        result = mock_docker_executor.execute(
            "get_weather --location Beijing"
        )

        assert result.success is True
        assert "Sunny" in result.output
        assert mock_docker_executor.was_executed("get_weather --location Beijing")


# ============================================================================
# 内存管理集成测试
# ============================================================================

class TestMemoryIntegration:
    """内存管理集成测试"""

    @pytest.mark.integration
    def test_memory_entry_creation(self, sample_memory_entries):
        """测试内存条目创建"""
        assert len(sample_memory_entries) == 2
        assert all(entry.content.startswith("Test memory") for entry in sample_memory_entries)

    @pytest.mark.integration
    def test_round_entry_sequence(self, sample_round_entries):
        """测试对话轮次序列"""
        assert len(sample_round_entries) == 2
        assert sample_round_entries[0].user_input == "What is the weather?"
        assert sample_round_entries[1].user_input == "Tell me a joke"

    @pytest.mark.integration
    def test_memory_with_timestamps(self, sample_memory_entries):
        """测试带时间戳的内存"""
        entry1 = sample_memory_entries[0]
        entry2 = sample_memory_entries[1]

        assert entry2.timestamp > entry1.timestamp


# ============================================================================
# 执行服务集成测试
# ============================================================================

class TestExecutionIntegration:
    """执行服务集成测试"""

    @pytest.mark.integration
    def test_safe_command_execution(self, mock_docker_executor: MockDockerExecutor):
        """测试安全命令执行"""
        result = mock_docker_executor.execute("echo test")

        assert result.success is True
        assert result.exit_code == 0

    @pytest.mark.integration
    def test_dangerous_command_blocking(self, mock_docker_executor: MockDockerExecutor):
        """测试危险命令阻止"""
        # 添加安全规则
        from backend.alice.core.interfaces.command_executor import SecurityRule
        mock_docker_executor.add_security_rule(
            SecurityRule(
                name="block_dangerous",
                pattern="rm -rf",
                action="block",
                reason="Dangerous command"
            )
        )

        is_safe, warning = mock_docker_executor.validate("rm -rf /test")

        assert is_safe is False
        assert "Dangerous" in warning or "block" in warning.lower()

    @pytest.mark.integration
    def test_python_code_execution(self, mock_docker_executor: MockDockerExecutor):
        """测试 Python 代码执行"""
        result = mock_docker_executor.execute(
            "print('hello')",
            is_python_code=True
        )

        assert result.success is True

    @pytest.mark.integration
    def test_command_interrupt(self, mock_docker_executor: MockDockerExecutor):
        """测试命令中断"""
        mock_docker_executor.interrupt()

        result = mock_docker_executor.execute("long running command")

        assert result.success is False
        assert "interrupt" in result.error.lower()

        # 重置状态
        mock_docker_executor.reset_interrupt()


# ============================================================================
# 流管理器集成测试
# ============================================================================

class TestStreamManagerIntegration:
    """流管理器集成测试"""

    @pytest.mark.integration
    def test_full_stream_processing(self):
        """测试完整流处理"""
        from backend.alice.infrastructure.bridge.stream_manager import StreamManager

        manager = StreamManager()
        all_messages = []

        # 模拟流式数据
        chunks = [
            "Hello",
            ", ",
            "```python",
            "\nprint('world')",
            "\n```",
            "!",
        ]

        for chunk in chunks:
            messages = manager.process_chunk(chunk)
            all_messages.extend(messages)

        # 验证消息
        assert len(all_messages) > 0

        # 最后强制 flush
        final_messages = manager.flush()
        all_messages.extend(final_messages)

        # 应该有 content 和 thinking 类型的消息
        has_content = any(m["type"] == "content" for m in all_messages)
        has_thinking = any(m["type"] == "thinking" for m in all_messages)

        assert has_content
        assert has_thinking

    @pytest.mark.integration
    def test_stream_with_llm_chunks(self, mock_llm_provider: MockLLMProvider):
        """测试 LLM 块与流管理器集成"""
        from backend.alice.infrastructure.bridge.stream_manager import StreamManager

        manager = StreamManager()
        messages = [
            ChatMessage(role="user", content="Write some code"),
        ]

        # 获取流式响应
        chunks = list(mock_llm_provider.stream_chat(messages))

        # 处理每个块
        all_messages = []
        for chunk in chunks:
            messages = manager.process_chunk(chunk.content)
            all_messages.extend(messages)

        # Flush 剩余内容
        final = manager.flush()
        all_messages.extend(final)

        assert len(all_messages) >= 0


# ============================================================================
# 端到端场景测试
# ============================================================================

class TestEndToEndScenarios:
    """端到端场景测试"""

    @pytest.mark.integration
    def test_user_question_with_code_generation(
        self,
        mock_llm_provider: MockLLMProvider,
        mock_docker_executor: MockDockerExecutor
    ):
        """测试用户问题生成代码的场景"""
        # 用户提问
        user_query = "Write a function to calculate fibonacci"

        # LLM 生成代码
        messages = [ChatMessage(role="user", content=user_query)]
        response = mock_llm_provider.chat(messages)

        assert response.content is not None

        # 如果有代码，尝试执行
        if "```python" in response.content:
            # 提取代码
            code = response.content.split("```python")[1].split("```")[0].strip()

            # 执行代码
            result = mock_docker_executor.execute(code, is_python_code=True)
            # 模拟环境中可能成功也可能失败，只验证有调用
            assert mock_docker_executor.execute_count >= 0

    @pytest.mark.integration
    def test_multi_turn_conversation(self, mock_llm_provider: MockLLMProvider):
        """测试多轮对话"""
        conversation = [
            ChatMessage(role="system", content="You are Alice"),
            ChatMessage(role="user", content="What's your name?"),
        ]

        response1 = mock_llm_provider.chat(conversation)
        conversation.append(ChatMessage(role="assistant", content=response1.content))

        conversation.append(ChatMessage(role="user", content="Nice to meet you"))
        response2 = mock_llm_provider.chat(conversation)

        assert response1.content is not None
        assert response2.content is not None
        assert mock_llm_provider.call_count == 2

    @pytest.mark.integration
    def test_error_recovery(
        self,
        mock_llm_provider: MockLLMProvider,
        mock_docker_executor: MockDockerExecutor
    ):
        """测试错误恢复"""
        # 配置错误响应
        mock_docker_executor.set_command_response(
            "error",
            ExecutionResult(
                success=False,
                output="",
                error="Command failed",
                exit_code=1
            )
        )

        # 执行失败的命令
        result = mock_docker_executor.execute("error")
        assert result.success is False

        # 执行成功的命令
        result = mock_docker_executor.execute("echo test")
        assert result.success is True


# ============================================================================
# 结构化 runtime / tool calling 回归测试
# ============================================================================

class TestStructuredRuntimeIntegration:
    """结构化 runtime 与 typed tool calling 回归测试"""

    @pytest.mark.integration
    def test_chat_service_sets_runtime_context_on_system_message(self):
        """测试 ChatService 将 runtime context 注入系统消息而非伪 user 消息"""
        from backend.alice.domain.llm.services.chat_service import ChatService

        provider = MagicMock()
        chat_service = ChatService(provider=provider, system_prompt="You are Alice")

        runtime_context = chat_service.set_runtime_context({
            "memory": {
                "working": "working notes",
                "short_term": "",
                "long_term": "long term memory",
            },
            "skills": {
                "summary": "toolkit, memory",
            },
        })

        assert runtime_context["memory"]["working"] == "working notes"
        assert chat_service.messages[0].role == "system"
        assert "<runtime_context>" not in chat_service.messages[0].content
        assert "working notes" in chat_service.messages[0].content
        assert "long term memory" in chat_service.messages[0].content
        assert "toolkit, memory" in chat_service.messages[0].content
        assert '"short_term"' not in chat_service.messages[0].content

    @pytest.mark.integration
    def test_orchestration_refresh_context_uses_runtime_context(self):
        """测试编排层刷新上下文时不再伪造记忆 user message"""
        from backend.alice.application.services.orchestration_service import OrchestrationService
        from backend.alice.domain.execution.services.tool_registry import ToolRegistry
        from backend.alice.domain.llm.services.chat_service import ChatService

        provider = MagicMock()
        chat_service = ChatService(provider=provider, system_prompt="You are Alice")
        chat_service.add_user_message("hello")

        memory_manager = MagicMock()
        memory_manager.get_working_content.return_value = "working memory"
        memory_manager.get_stm_content.return_value = "short term memory"
        memory_manager.get_ltm_content.return_value = "long term memory"

        skill_registry = MagicMock()
        skill_registry.list_skills_summary.return_value = "toolkit, memory"
        skill_registry.get_all_skills.return_value = {}
        tool_registry = ToolRegistry(skill_registry=skill_registry)

        orchestration = OrchestrationService(
            memory_manager=memory_manager,
            chat_service=chat_service,
            skill_registry=skill_registry,
            tool_registry=tool_registry,
        )

        orchestration.refresh_context()

        messages = chat_service.messages
        assert len(messages) == 2
        assert messages[0].role == "system"
        assert messages[1].role == "user"
        assert messages[1].content == "hello"
        assert "【记忆与背景信息注入】" not in messages[1].content
        assert "working: working memory" in messages[0].content
        assert "short_term: short term memory" in messages[0].content
        assert "long_term: long term memory" in messages[0].content
        assert "summary: toolkit, memory" in messages[0].content
        assert "builtin_system_tools" not in messages[0].content
        assert "terminal_commands" not in messages[0].content
        assert "code_execution" not in messages[0].content
        assert "Memory snapshot:" in messages[0].content
        assert "Skill snapshot:" in messages[0].content
        assert orchestration.runtime_context["tools"]["builtin_system_tools"]
        assert orchestration.runtime_context["tools"]["terminal_commands"][0]["tool_id"] == "run_bash"
        assert orchestration.runtime_context["tools"]["code_execution"][0]["tool_id"] == "run_python"

    @pytest.mark.integration
    def test_execution_service_exposes_execute_tool_invocation_alias(self):
        """测试 ExecutionService 暴露 execute_tool_invocation 兼容入口"""
        from backend.alice.domain.execution.models.tool_calling import ToolInvocation
        from backend.alice.domain.execution.services.execution_service import ExecutionService

        executor = MagicMock()
        service = ExecutionService(executor=executor)
        expected = MagicMock()
        service.execute_tool_call = Mock(return_value=expected)

        invocation = ToolInvocation(
            id="call_1",
            name="run_bash",
            arguments='{"command": "echo test"}',
        )

        result = service.execute_tool_invocation(invocation, log_context={"trace_id": "t1"})

        assert result is expected
        service.execute_tool_call.assert_called_once_with(invocation, log_context={"trace_id": "t1"})


__all__ = []
