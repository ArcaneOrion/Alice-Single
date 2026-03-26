"""
Distiller Service

记忆提炼服务，将过期的短期记忆提炼为长期价值内容。
"""

import logging
from datetime import datetime
from typing import Optional, Any

from backend.alice.domain.llm.services.client_provider import ClientProvider

logger = logging.getLogger(__name__)


class Distiller:
    """记忆提炼服务

    调用 LLM 将过期的短期记忆提炼为具有长期价值的内容。
    """

    DEFAULT_DISTILL_PROMPT = (
        "你是一个记忆提炼专家。以下是用户最近 7 天的短期记忆记录：\n\n{full_context}\n\n"
        "请重点分析即将被删除的旧记忆：\n{expired_content}\n\n"
        "请根据这 7 天的整体背景，结合旧记忆，提炼出具有长期价值的：\n"
        "1. 用户的新习惯或偏好变更。\n"
        "2. 重要的项目决策或里程碑进展。\n"
        "3. 用户提到的重要个人事实。\n\n"
        "请以 Markdown 列表格式输出提炼结果，保持简洁。如果没有值得记录的长期价值，请回复"无重要更新"。"
    )

    def __init__(
        self,
        llm_provider: Optional[ClientProvider] = None,
        model_name: Optional[str] = None,
    ):
        """初始化提炼服务

        Args:
            llm_provider: LLM 提供者
            model_name: 使用的模型名称
        """
        self.llm_provider = llm_provider
        self.model_name = model_name

    def distill_stm(
        self,
        expired_content: str,
        full_context: Optional[str] = None,
    ) -> dict[str, Any]:
        """提炼短期记忆

        Args:
            expired_content: 过期的短期记忆内容
            full_context: 完整的短期记忆上下文（可选）

        Returns:
            提炼结果字典
        """
        if not self.llm_provider:
            return {
                "success": False,
                "error": "No LLM provider available",
                "summary": None,
            }

        if not expired_content.strip():
            return {
                "success": True,
                "summary": None,
                "message": "No content to distill",
            }

        try:
            # 构建提炼提示词
            prompt = self._build_distill_prompt(expired_content, full_context)

            # 调用 LLM
            client = self.llm_provider.get_client()
            model_name = self.model_name or self.llm_provider.get_model_name()

            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
            )

            summary = response.choices[0].message.content.strip()

            logger.info(f"记忆提炼完成，输出长度: {len(summary)}")

            return {
                "success": True,
                "summary": summary if summary and "无重要更新" not in summary else None,
                "raw_summary": summary,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"记忆提炼失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "summary": None,
            }

    def _build_distill_prompt(self, expired_content: str, full_context: Optional[str] = None) -> str:
        """构建提炼提示词

        Args:
            expired_content: 过期内容
            full_context: 完整上下文

        Returns:
            提炼提示词
        """
        context = full_context or expired_content
        return self.DEFAULT_DISTILL_PROMPT.format(
            full_context=context,
            expired_content=expired_content,
        )

    def set_custom_prompt(self, prompt: str) -> None:
        """设置自定义提炼提示词

        Args:
            prompt: 自定义提示词模板，应包含 {full_context} 和 {expired_content} 占位符
        """
        self.DEFAULT_DISTILL_PROMPT = prompt


__all__ = ["Distiller"]
