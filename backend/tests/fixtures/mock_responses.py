"""
Mock 响应数据

提供预定义的 API 响应数据，用于测试
"""

from datetime import datetime
from typing import Any

from backend.alice.core.interfaces.llm_provider import ChatMessage, StreamChunk, ChatResponse
from backend.alice.core.interfaces.command_executor import ExecutionResult
from backend.alice.infrastructure.bridge.protocol.messages import (
    StatusMessage,
    ThinkingMessage,
    ContentMessage,
    TokensMessage,
    ErrorMessage,
    StatusType,
)


class MockResponses:
    """预定义的 Mock 响应数据"""

    # ========================================================================
    # LLM 响应
    # ========================================================================

    @staticmethod
    def simple_chat_response() -> ChatResponse:
        """简单聊天响应"""
        return ChatResponse(
            content="Hello! How can I help you today?",
            thinking="",
            tool_calls=[],
            usage={"total_tokens": 50, "prompt_tokens": 20, "completion_tokens": 30}
        )

    @staticmethod
    def chat_with_thinking() -> ChatResponse:
        """带思考的聊天响应"""
        return ChatResponse(
            content="Based on my analysis, the answer is 42.",
            thinking="I need to calculate the meaning of life...",
            tool_calls=[],
            usage={"total_tokens": 100, "prompt_tokens": 30, "completion_tokens": 70}
        )

    @staticmethod
    def chat_with_tool_call() -> ChatResponse:
        """带工具调用的聊天响应"""
        return ChatResponse(
            content="Let me check the weather for you.",
            thinking="User wants to know the weather",
            tool_calls=[{
                "id": "call_abc123",
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "arguments": '{"location": "Beijing", "unit": "celsius"}'
                }
            }],
            usage={"total_tokens": 80, "prompt_tokens": 40, "completion_tokens": 40}
        )

    @staticmethod
    def streaming_chunks() -> list[StreamChunk]:
        """流式响应块序列"""
        return [
            StreamChunk(content="Hello", thinking="", is_complete=False, tool_calls=[]),
            StreamChunk(content=" there", thinking="", is_complete=False, tool_calls=[]),
            StreamChunk(content="!", thinking="", is_complete=True, tool_calls=[], usage={"total_tokens": 50}),
        ]

    @staticmethod
    def streaming_with_code_block() -> list[StreamChunk]:
        """带代码块的流式响应"""
        return [
            StreamChunk(content="Here's", thinking="", is_complete=False, tool_calls=[]),
            StreamChunk(content=" the", thinking="", is_complete=False, tool_calls=[]),
            StreamChunk(content=" code:\n```python", thinking="", is_complete=False, tool_calls=[]),
            StreamChunk(content="print('hello')", thinking="", is_complete=False, tool_calls=[]),
            StreamChunk(content="\n```", thinking="", is_complete=False, tool_calls=[]),
            StreamChunk(content=" Done!", thinking="", is_complete=True, tool_calls=[], usage={"total_tokens": 100}),
        ]

    @staticmethod
    def streaming_with_thinking() -> list[StreamChunk]:
        """带思考标记的流式响应"""
        return [
            StreamChunk(content="", thinking="<thought>", is_complete=False, tool_calls=[]),
            StreamChunk(content="I need to think about this...", thinking="", is_complete=False, tool_calls=[]),
            StreamChunk(content="", thinking="</thought>", is_complete=False, tool_calls=[]),
            StreamChunk(content="The answer is 42.", thinking="", is_complete=True, tool_calls=[], usage={"total_tokens": 80}),
        ]

    # ========================================================================
    # 命令执行响应
    # ========================================================================

    @staticmethod
    def success_output() -> ExecutionResult:
        """成功执行结果"""
        return ExecutionResult(
            success=True,
            output="Command executed successfully",
            error="",
            exit_code=0,
            execution_time=0.1
        )

    @staticmethod
    def error_output() -> ExecutionResult:
        """错误执行结果"""
        return ExecutionResult(
            success=False,
            output="",
            error="Command failed: permission denied",
            exit_code=1,
            execution_time=0.05
        )

    @staticmethod
    def timeout_output() -> ExecutionResult:
        """超时执行结果"""
        return ExecutionResult(
            success=False,
            output="",
            error="Command timed out after 120 seconds",
            exit_code=124,
            execution_time=120.0
        )

    @staticmethod
    def python_output() -> ExecutionResult:
        """Python 代码执行结果"""
        return ExecutionResult(
            success=True,
            output="Hello, World!\n",
            error="",
            exit_code=0,
            execution_time=0.2
        )

    # ========================================================================
    # Bridge 消息
    # ========================================================================

    @staticmethod
    def status_ready() -> StatusMessage:
        """就绪状态消息"""
        return StatusMessage(content=StatusType.READY)

    @staticmethod
    def status_thinking() -> StatusMessage:
        """思考状态消息"""
        return StatusMessage(content=StatusType.THINKING)

    @staticmethod
    def status_executing() -> StatusMessage:
        """执行状态消息"""
        return StatusMessage(content=StatusType.EXECUTING_TOOL)

    @staticmethod
    def thinking_message(content: str = "Thinking...") -> ThinkingMessage:
        """思考内容消息"""
        return ThinkingMessage(content=content)

    @staticmethod
    def content_message(content: str = "Response content") -> ContentMessage:
        """正文内容消息"""
        return ContentMessage(content=content)

    @staticmethod
    def tokens_message(total: int = 100, prompt: int = 50, completion: int = 50) -> TokensMessage:
        """Token 统计消息"""
        return TokensMessage(total=total, prompt=prompt, completion=completion)

    @staticmethod
    def error_message(content: str = "An error occurred", code: str = "ERROR") -> ErrorMessage:
        """错误消息"""
        return ErrorMessage(content=content, code=code)

    # ========================================================================
    # 聊天消息
    # ========================================================================

    @staticmethod
    def system_prompt() -> ChatMessage:
        """系统提示消息"""
        return ChatMessage(
            role="system",
            content="You are Alice, a helpful AI assistant."
        )

    @staticmethod
    def user_message(content: str = "Hello") -> ChatMessage:
        """用户消息"""
        return ChatMessage(role="user", content=content)

    @staticmethod
    def assistant_message(content: str = "Hi there!") -> ChatMessage:
        """助手消息"""
        return ChatMessage(role="assistant", content=content)

    @staticmethod
    def conversation_history() -> list[ChatMessage]:
        """对话历史"""
        return [
            MockResponses.system_prompt(),
            MockResponses.user_message("What's the weather?"),
            MockResponses.assistant_message("The weather is sunny."),
            MockResponses.user_message("What about tomorrow?"),
        ]

    # ========================================================================
    # 事件数据
    # ========================================================================

    @staticmethod
    def llm_start_event() -> dict:
        """LLM 开始事件数据"""
        return {
            "type": "llm.start",
            "model": "gpt-4",
            "messages_count": 3,
            "timestamp": datetime.now().isoformat()
        }

    @staticmethod
    def llm_chunk_event() -> dict:
        """LLM 块事件数据"""
        return {
            "type": "llm.chunk",
            "content": "Hello",
            "thinking": "",
            "timestamp": datetime.now().isoformat()
        }

    @staticmethod
    def exec_start_event() -> dict:
        """执行开始事件数据"""
        return {
            "type": "exec.start",
            "command": "echo test",
            "is_python": False,
            "timestamp": datetime.now().isoformat()
        }

    @staticmethod
    def exec_complete_event() -> dict:
        """执行完成事件数据"""
        return {
            "type": "exec.complete",
            "command": "echo test",
            "success": True,
            "output": "test",
            "duration_ms": 50,
            "timestamp": datetime.now().isoformat()
        }

    # ========================================================================
    # 技能数据
    # ========================================================================

    @staticmethod
    def skill_metadata() -> dict:
        """技能元数据"""
        return {
            "name": "test-skill",
            "description": "A test skill",
            "version": "1.0.0",
            "author": "test",
            "license": "MIT"
        }

    @staticmethod
    def skill_manifest() -> str:
        """技能清单内容"""
        return """---
name: test-skill
description: A test skill for testing
version: 1.0.0
license: MIT
---

# Test Skill

This is a test skill for testing purposes.
"""

    # ========================================================================
    # 内存数据
    # ========================================================================

    @staticmethod
    def memory_entry() -> dict:
        """内存条目"""
        return {
            "content": "Test memory content",
            "timestamp": datetime.now().isoformat(),
            "metadata": {"source": "test", "importance": "high"}
        }

    @staticmethod
    def working_memory_content() -> str:
        """工作内存内容"""
        return """--- ROUND ---
User: Hello
Assistant: Hi there!

--- ROUND ---
User: How are you?
Assistant: I'm doing well!
"""

    @staticmethod
    def stm_content() -> str:
        """短期记忆内容"""
        return """## 2024-01-01
- User prefers concise answers
- User is working on Python project

## 2024-01-02
- User asked about weather
- User mentioned they like jazz music
"""

    @staticmethod
    def ltm_content() -> str:
        """长期记忆内容"""
        return """## 经验教训

### 用户偏好
- 用户喜欢简洁的回答
- 用户偏好使用 Python

### 重要信息
- 用户正在开发 AI 项目
- 用户喜欢爵士乐
"""

    # ========================================================================
    # Docker 数据
    # ========================================================================

    @staticmethod
    def docker_ps_output() -> str:
        """Docker ps 输出"""
        return """alice-sandbox-instance   Up 2 hours
another-container        Up 1 day
"""

    @staticmethod
    def docker_inspect_output() -> dict:
        """Docker inspect 输出"""
        return {
            "Id": "abc123",
            "State": {
                "Running": True,
                "Status": "running"
            },
            "Config": {
                "Image": "alice-sandbox:latest",
                "WorkingDir": "/app"
            }
        }

    # ========================================================================
    # 完整对话场景
    # ========================================================================

    @staticmethod
    def simple_conversation() -> dict:
        """简单对话场景"""
        return {
            "messages": [
                MockResponses.system_prompt(),
                MockResponses.user_message("What is 2+2?"),
            ],
            "response": MockResponses.simple_chat_response(),
            "expected_tool_calls": [],
        }

    @staticmethod
    def tool_call_conversation() -> dict:
        """工具调用对话场景"""
        return {
            "messages": [
                MockResponses.system_prompt(),
                MockResponses.user_message("What's the weather in Beijing?"),
            ],
            "response": MockResponses.chat_with_tool_call(),
            "expected_tool_calls": ["get_weather"],
        }


class ResponseBuilder:
    """动态构建响应数据的工具类"""

    @staticmethod
    def chat_response(content: str, thinking: str = "", tokens: int = 100) -> ChatResponse:
        """构建聊天响应"""
        return ChatResponse(
            content=content,
            thinking=thinking,
            tool_calls=[],
            usage={"total_tokens": tokens, "prompt_tokens": tokens // 2, "completion_tokens": tokens // 2}
        )

    @staticmethod
    def execution_result(
        success: bool = True,
        output: str = "",
        error: str = "",
        exit_code: int = 0
    ) -> ExecutionResult:
        """构建执行结果"""
        return ExecutionResult(
            success=success,
            output=output,
            error=error,
            exit_code=exit_code,
            execution_time=0.1
        )

    @staticmethod
    def stream_chunks_from_text(text: str, chunk_size: int = 10) -> list[StreamChunk]:
        """从文本构建流式块序列"""
        chunks = []
        for i in range(0, len(text), chunk_size):
            is_last = (i + chunk_size >= len(text))
            chunks.append(StreamChunk(
                content=text[i:i + chunk_size],
                thinking="",
                is_complete=is_last,
                tool_calls=[],
                usage={"total_tokens": len(text) // 4} if is_last else None
            ))
        return chunks

    @staticmethod
    def bridge_message(msg_type: str, content: str = "", **kwargs) -> dict:
        """构建 Bridge 消息"""
        return {
            "type": msg_type,
            "content": content,
            **kwargs
        }


__all__ = [
    "MockResponses",
    "ResponseBuilder",
]
