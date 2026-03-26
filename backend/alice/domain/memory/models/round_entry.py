"""
Round Entry Model

对话轮次数据模型，用于工作内存中的对话记录。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class RoundEntry:
    """对话轮次

    表示工作内存中的一轮对话，包含用户输入和助手的思考与响应。

    Attributes:
        user_input: 用户输入内容
        assistant_thinking: 助手的思考过程（可选）
        assistant_response: 助手的最终响应（可选）
        timestamp: 对话发生的时间戳
    """

    user_input: str
    assistant_thinking: str = ""
    assistant_response: str = ""
    timestamp: Optional[datetime] = None

    def __post_init__(self):
        """初始化时间戳"""
        if self.timestamp is None:
            self.timestamp = datetime.now()

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "user_input": self.user_input,
            "assistant_thinking": self.assistant_thinking,
            "assistant_response": self.assistant_response,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RoundEntry":
        """从字典创建实例"""
        return cls(
            user_input=data["user_input"],
            assistant_thinking=data.get("assistant_thinking", ""),
            assistant_response=data.get("assistant_response", ""),
            timestamp=datetime.fromisoformat(data["timestamp"]) if data.get("timestamp") else None,
        )

    def to_markdown(self) -> str:
        """转换为 Markdown 格式用于文件存储"""
        lines = ["--- ROUND ---"]
        if self.user_input:
            lines.append(f"USER: {self.user_input}")
        if self.assistant_thinking:
            lines.append(f"ALICE_THINKING: {self.assistant_thinking}")
        if self.assistant_response:
            lines.append(f"ALICE_RESPONSE: {self.assistant_response}")
        return "\n".join(lines)

    @classmethod
    def from_markdown(cls, markdown: str) -> "RoundEntry":
        """从 Markdown 格式解析创建实例"""
        user_input = ""
        thinking = ""
        response = ""

        for line in markdown.split("\n"):
            line = line.strip()
            if line.startswith("USER:"):
                user_input = line[5:].strip()
            elif line.startswith("ALICE_THINKING:"):
                thinking = line[15:].strip()
            elif line.startswith("ALICE_RESPONSE:"):
                response = line[14:].strip()

        return cls(
            user_input=user_input,
            assistant_thinking=thinking,
            assistant_response=response,
        )


__all__ = ["RoundEntry"]
