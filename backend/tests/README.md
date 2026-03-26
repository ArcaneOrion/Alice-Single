# Alice-Single 测试框架

## 概述

本目录包含 Alice-Single 项目的所有测试代码，包括单元测试、集成测试和测试 fixtures。

## 目录结构

```
backend/tests/
├── __init__.py              # 测试包初始化
├── conftest.py              # pytest 配置和共享 fixtures
├── pytest.ini               # pytest 配置文件
├── fixtures/                # 测试 fixtures
│   ├── __init__.py
│   ├── mock_llm.py          # Mock LLM Provider
│   ├── mock_responses.py    # 预定义响应数据
│   ├── mock_docker.py       # Mock Docker 执行器
│   ├── mock_stream.py       # Mock 流数据
│   └── test_config.toml     # 测试配置
├── unit/                    # 单元测试
│   ├── test_core/           # 核心模块测试
│   │   ├── test_container.py
│   │   ├── test_event_bus.py
│   │   └── test_stream_manager.py
│   └── test_domain/         # Domain 层测试
│       ├── test_command.py
│       └── test_memory_models.py
└── integration/             # 集成测试
    ├── test_agent.py        # Agent 集成测试
    └── test_bridge.py       # Bridge 通信测试
```

## 运行测试

### 运行所有测试

```bash
# 从项目根目录
pytest backend/tests/

# 或使用 pytest.ini 配置
pytest
```

### 运行特定类型的测试

```bash
# 只运行单元测试
pytest -m unit

# 只运行集成测试
pytest -m integration

# 跳过慢速测试
pytest -m "not slow"
```

### 运行特定文件或测试

```bash
# 运行特定文件
pytest backend/tests/unit/test_core/test_container.py

# 运行特定测试类
pytest backend/tests/unit/test_core/test_container.py::TestContainerBasics

# 运行特定测试方法
pytest backend/tests/unit/test_core/test_container.py::TestContainerBasics::test_container_creation
```

### 生成覆盖率报告

```bash
# 生成终端覆盖率报告
pytest --cov=backend/alice --cov-report=term

# 生成 HTML 覆盖率报告
pytest --cov=backend/alice --cov-report=html

# 查看报告
open htmlcov/index.html
```

## 测试标记

| 标记 | 描述 |
|------|------|
| `unit` | 单元测试 - 快速，无外部依赖 |
| `integration` | 集成测试 - 测试组件间交互 |
| `slow` | 慢速测试 - 执行时间较长 |
| `docker` | 需要 Docker 的测试 |

## Fixtures

### conftest.py 提供的 fixtures

- `test_container` - 依赖注入容器
- `test_event_bus` - 事件总线
- `mock_llm_provider` - Mock LLM Provider
- `mock_docker_executor` - Mock Docker 执行器
- `sample_chat_messages` - 示例聊天消息
- `sample_memory_entries` - 示例内存条目
- `temp_dir` - 临时目录（自动清理）
- `temp_memory_dir` - 临时内存目录

### 使用示例

```python
def test_example(mock_llm_provider, sample_chat_messages):
    response = mock_llm_provider.chat(sample_chat_messages)
    assert response.content is not None
```

## 编写测试

### 单元测试模板

```python
"""
模块名称单元测试
"""

import pytest

from backend.alice.module import ClassToTest


class TestClassToTest:
    """ClassToTest 测试"""

    def test_something(self):
        """测试某功能"""
        obj = ClassToTest()
        result = obj.method()
        assert result == expected_value

    def test_with_fixture(self, mock_llm_provider):
        """测试使用 fixture"""
        # 使用 fixture 进行测试
        pass
```

### 集成测试模板

```python
"""
功能名称集成测试
"""

import pytest


@pytest.mark.integration
class TestFeatureIntegration:
    """功能集成测试"""

    def test_full_workflow(self, mock_llm_provider, mock_docker_executor):
        """测试完整工作流"""
        # 1. 准备
        # 2. 执行
        # 3. 验证
        pass
```

## 最佳实践

1. **使用 fixtures** - 利用 `conftest.py` 中的共享 fixtures
2. **明确标记** - 为测试添加适当的标记（`unit`, `integration` 等）
3. **保持独立** - 每个测试应该独立运行，不依赖其他测试
4. **清理资源** - 使用 `teardown` 或 `yield` 清理测试资源
5. **描述性命名** - 使用描述性的测试名称

## 调试测试

```bash
# 打印输出
pytest -s

# 进入 pdb 调试器
pytest --pdb

# 在第一个失败时停止
pytest -x

# 显示详细输出
pytest -vv

# 只运行失败的测试
pytest --lf
```
