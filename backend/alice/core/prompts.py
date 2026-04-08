"""运行时 prompt 分片与聚合工具。"""

from __future__ import annotations

from pathlib import Path

PROMPT_LAYER_FILES: tuple[str, ...] = (
    "01_identity.xml",
    "02_principles.xml",
    "03_memory.xml",
    "04_tools.xml",
    "05_output.xml",
)


def is_supported_prompt_fragment(filename: str) -> bool:
    return filename in PROMPT_LAYER_FILES


def compose_system_prompt(*, prompts_dir: Path) -> str:
    """按固定顺序组装 XML 系统提示词。"""
    fragments: list[str] = []

    for filename in PROMPT_LAYER_FILES:
        fragment_path = prompts_dir / filename
        fragments.append(fragment_path.read_text(encoding="utf-8").strip())

    joined_fragments = "\n".join(fragments)
    return f"<system_prompt>\n{joined_fragments}\n</system_prompt>\n"


def copy_prompt_templates(*, template_dir: Path, target_dir: Path) -> None:
    """将仓库模板复制到运行时 prompt 目录，不覆盖用户已有内容。"""
    target_dir.mkdir(parents=True, exist_ok=True)

    for filename in PROMPT_LAYER_FILES:
        template_path = template_dir / filename
        target_path = target_dir / filename
        if target_path.exists():
            continue
        target_path.write_text(template_path.read_text(encoding="utf-8"), encoding="utf-8")


def rebuild_runtime_prompt(*, prompts_dir: Path, prompt_path: Path) -> str:
    """根据运行时分片重建聚合 prompt 文件。"""
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    content = compose_system_prompt(prompts_dir=prompts_dir)
    prompt_path.write_text(content, encoding="utf-8")
    return content


__all__ = [
    "PROMPT_LAYER_FILES",
    "compose_system_prompt",
    "copy_prompt_templates",
    "is_supported_prompt_fragment",
    "rebuild_runtime_prompt",
]
