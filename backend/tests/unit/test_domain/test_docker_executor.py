"""
DockerExecutor 单元测试

验证执行器构造阶段不会抢先初始化 Docker 环境。
"""

import unittest
from unittest.mock import patch

from backend.alice.domain.execution.executors.docker_executor import DockerExecutor


class TestDockerExecutor(unittest.TestCase):
    """DockerExecutor 测试"""

    def test_constructor_does_not_eagerly_initialize_docker(self) -> None:
        """构造阶段不应立即触发 Docker 环境检查"""
        with patch.object(DockerExecutor, "_ensure_docker_environment") as ensure_mock:
            DockerExecutor()

        ensure_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
