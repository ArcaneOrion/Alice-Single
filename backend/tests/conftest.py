"""
Pytest 配置和共享 fixtures

提供测试所需的共享 fixtures、mock 对象和测试工具
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path
from typing import Generator, Optional
from unittest.mock import MagicMock, Mock, patch
from datetime import datetime
import json

import pytest

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.alice.core.container import Container, reset_container
from backend.alice.core.event_bus import EventBus, get_event_bus, EventType
from backend.alice.core.interfaces.llm_provider import ChatMessage, StreamChunk, ChatResponse
from backend.alice.core.interfaces.memory_store import MemoryEntry, RoundEntry
from backend.alice.core.interfaces.command_executor import ExecutionResult, SecurityRule


# ============================================================================
# 测试目录 fixtures
# ============================================================================

@pytest.fixture(scope="session")
def test_data_dir() -> Path:
    """测试数据目录"""
    return project_root / "backend" / "tests" / "fixtures"


@pytest.fixture(scope="function")
def temp_dir() -> Generator[Path, None, None]:
    """临时目录，每个测试函数后自动清理"""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    if temp_path.exists():
        shutil.rmtree(temp_path)


@pytest.fixture(scope="function")
def temp_memory_dir(temp_dir: Path) -> Path:
    """临时内存目录，用于测试内存存储"""
    memory_dir = temp_dir / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    return memory_dir


# ============================================================================
# 容器 fixtures
# ============================================================================

@pytest.fixture(scope="function")
def test_container() -> Container:
    """测试用依赖注入容器"""
    reset_container()
    container = Container()
    yield container
    reset_container()


# ============================================================================
# 事件总线 fixtures
# ============================================================================

@pytest.fixture(scope="function")
def test_event_bus() -> EventBus:
    """测试用事件总线"""
    bus = EventBus(enable_async=False)
    yield bus
    bus.clear()


@pytest.fixture(scope="function")
def mock_event_handler() -> Mock:
    """Mock 事件处理器"""
    return Mock(side_effect=lambda e: None)


# ============================================================================
# LLM Provider fixtures
# ============================================================================

@pytest.fixture(scope="function")
def mock_llm_provider():
    """Mock LLM Provider"""
    from backend.tests.fixtures.mock_llm import MockLLMProvider

    return MockLLMProvider()


@pytest.fixture(scope="function")
def sample_chat_messages() -> list[ChatMessage]:
    """示例聊天消息"""
    return [
        ChatMessage(role="system", content="You are a helpful assistant"),
        ChatMessage(role="user", content="Hello, how are you?"),
    ]


# ============================================================================
# 内存存储 fixtures
# ============================================================================

@pytest.fixture(scope="function")
def sample_memory_entries() -> list[MemoryEntry]:
    """示例内存条目"""
    return [
        MemoryEntry(
            content="Test memory 1",
            timestamp=datetime(2024, 1, 1, 10, 0, 0),
            metadata={"source": "test"}
        ),
        MemoryEntry(
            content="Test memory 2",
            timestamp=datetime(2024, 1, 2, 10, 0, 0),
            metadata={"source": "test"}
        ),
    ]


@pytest.fixture(scope="function")
def sample_round_entries() -> list[RoundEntry]:
    """示例对话轮次"""
    return [
        RoundEntry(
            user_input="What is the weather?",
            assistant_thinking="I need to check the weather",
            assistant_response="The weather is sunny.",
            timestamp=datetime(2024, 1, 1, 10, 0, 0)
        ),
        RoundEntry(
            user_input="Tell me a joke",
            assistant_thinking="Thinking of a joke",
            assistant_response="Why did the chicken cross the road?",
            timestamp=datetime(2024, 1, 1, 10, 5, 0)
        ),
    ]


# ============================================================================
# 命令执行 fixtures
# ============================================================================

@pytest.fixture(scope="function")
def mock_docker_executor():
    """Mock Docker 执行器"""
    from backend.tests.fixtures.mock_docker import MockDockerExecutor

    return MockDockerExecutor()


@pytest.fixture(scope="function")
def sample_security_rules() -> list[SecurityRule]:
    """示例安全规则"""
    return [
        SecurityRule(
            name="block_rm_rf",
            pattern=r"rm\s+-rf\s+/",
            action="block",
            reason="Prevent accidental deletion"
        ),
        SecurityRule(
            name="warn_git",
            pattern=r"git\s+push",
            action="warn",
            reason="Confirm before pushing"
        ),
    ]


# ============================================================================
# Stream Manager fixtures
# ============================================================================

@pytest.fixture(scope="function")
def sample_stream_chunks() -> list[str]:
    """示例流式数据块"""
    return [
        "Hello",
        ", ",
        "```python",
        "\nprint('hello')\n",
        "```",
        " world!",
    ]


# ============================================================================
# 环境变量 fixtures
# ============================================================================

@pytest.fixture(scope="function")
def test_env_vars(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """设置测试环境变量"""
    env = {
        "API_KEY": "test_api_key",
        "API_BASE_URL": "https://test.api.com/v1",
        "MODEL_NAME": "test-model",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return env


# ============================================================================
# 技能系统 fixtures
# ============================================================================

@pytest.fixture(scope="function")
def sample_skill_content() -> str:
    """示例技能内容"""
    return """---
name: test-skill
description: A test skill
---

# Test Skill

This is a test skill for testing purposes.
"""


@pytest.fixture(scope="function")
def temp_skills_dir(temp_dir: Path) -> Path:
    """临时技能目录"""
    skills_dir = temp_dir / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)

    # 创建示例技能
    test_skill_dir = skills_dir / "test-skill"
    test_skill_dir.mkdir(parents=True, exist_ok=True)
    (test_skill_dir / "SKILL.md").write_text("""---
name: test-skill
description: A test skill
---

# Test Skill

This is a test skill.
""")

    return skills_dir


# ============================================================================
# 桥接协议 fixtures
# ============================================================================

@pytest.fixture(scope="function")
def mock_stdio_transport() -> MagicMock:
    """Mock stdin/stdout 传输"""
    mock = MagicMock()
    mock.stdin = MagicMock()
    mock.stdout = MagicMock()
    return mock


# ============================================================================
# 断言辅助函数
# ============================================================================

class AssertionHelpers:
    """断言辅助函数集合"""

    @staticmethod
    def assert_execution_success(result: ExecutionResult) -> None:
        """断言执行成功"""
        assert result.success, f"Execution failed: {result.error}"
        assert result.exit_code == 0

    @staticmethod
    def assert_execution_failure(result: ExecutionResult, error_contains: str = "") -> None:
        """断言执行失败"""
        assert not result.success, "Execution should have failed"
        if error_contains:
            assert error_contains in result.error or error_contains in result.output

    @staticmethod
    def assert_memory_entry(entry: MemoryEntry, content: str) -> None:
        """断言内存条目"""
        assert entry.content == content
        assert isinstance(entry.timestamp, datetime)

    @staticmethod
    def assert_stream_messages(messages: list[dict], expected_types: list[str]) -> None:
        """断言流式消息类型序列"""
        actual_types = [m.get("type") for m in messages]
        assert actual_types == expected_types, f"Expected {expected_types}, got {actual_types}"


@pytest.fixture(scope="session")
def assertions() -> type[AssertionHelpers]:
    """断言辅助类"""
    return AssertionHelpers


# ============================================================================
# Pytest 配置
# ============================================================================

def pytest_configure(config):
    """Pytest 配置钩子"""
    config.addinivalue_line("markers", "unit: 单元测试标记")
    config.addinivalue_line("markers", "integration: 集成测试标记")
    config.addinivalue_line("markers", "slow: 慢速测试标记")
    config.addinivalue_line("markers", "docker: 需要 Docker 的测试")


def pytest_collection_modifyitems(config, items):
    """修改测试项"""
    for item in items:
        # 为未标记的测试自动添加 unit 标记
        if not any(item.iter_markers()):
            item.add_marker(pytest.mark.unit)


# ============================================================================
# 跳过条件
# ============================================================================

def pytest_runtest_setup(item):
    """测试前检查"""
    # Docker 测试需要 Docker 可用
    if item.get_closest_marker("docker"):
        import shutil
        if not shutil.which("docker"):
            pytest.skip("Docker not available")


__all__ = [
    "test_data_dir",
    "temp_dir",
    "temp_memory_dir",
    "test_container",
    "test_event_bus",
    "mock_event_handler",
    "mock_llm_provider",
    "sample_chat_messages",
    "sample_memory_entries",
    "sample_round_entries",
    "mock_docker_executor",
    "sample_security_rules",
    "sample_stream_chunks",
    "test_env_vars",
    "sample_skill_content",
    "temp_skills_dir",
    "mock_stdio_transport",
    "assertions",
]
