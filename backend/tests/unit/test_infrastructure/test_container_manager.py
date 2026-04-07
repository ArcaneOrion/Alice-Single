from pathlib import Path

from backend.alice.infrastructure.docker.config import DockerConfig
from backend.alice.infrastructure.docker.container_manager import ContainerManager


def test_ensure_mount_directories_creates_alice_workspace(tmp_path) -> None:
    config = DockerConfig(project_root=tmp_path)
    manager = ContainerManager(config)

    manager._ensure_mount_directories()

    assert (tmp_path / "skills").exists()
    assert (tmp_path / ".alice" / "workspace").exists()
    assert not (tmp_path / "alice_output").exists()


def test_ensure_mount_directories_keeps_container_output_path_unchanged() -> None:
    config = DockerConfig(project_root=Path("/tmp/alice-project"))

    assert config.default_mounts[1].container_path == "/app/alice_output"
