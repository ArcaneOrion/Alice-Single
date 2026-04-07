from pathlib import Path

from backend.alice.infrastructure.docker.config import DockerConfig


def test_default_mounts_use_alice_workspace_on_host() -> None:
    config = DockerConfig(project_root=Path("/tmp/alice-project"))

    mounts = config.default_mounts

    assert mounts[0].host_path == Path("/tmp/alice-project") / "skills"
    assert mounts[0].container_path == "/app/skills"
    assert mounts[1].host_path == Path("/tmp/alice-project") / ".alice" / "workspace"
    assert mounts[1].container_path == "/app/alice_output"
