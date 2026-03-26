"""
Bridge Protocol Codec

JSON 编解码器，负责消息对象与 JSON 格式之间的转换。
"""

import json
import logging
from typing import Any, Union

from .messages import (
    MessageType,
    StatusType,
    BridgeMessage,
    StatusMessage,
    ThinkingMessage,
    ContentMessage,
    TokensMessage,
    ErrorMessage,
    InterruptMessage,
    OutputMessage,
)

logger = logging.getLogger(__name__)


class MessageDecodeError(Exception):
    """消息解码异常"""
    pass


class MessageEncodeError(Exception):
    """消息编码异常"""
    pass


def message_from_dict(data: dict[str, Any]) -> BridgeMessage:
    """
    从字典解析消息。

    Args:
        data: 包含消息数据的字典

    Returns:
        BridgeMessage: 解析后的消息对象

    Raises:
        MessageDecodeError: 当消息类型未知或解析失败时
    """
    try:
        msg_type = data.get("type")

        if msg_type == MessageType.STATUS:
            return StatusMessage(
                type=MessageType.STATUS,
                content=StatusType(data.get("content", "ready"))
            )
        elif msg_type == MessageType.THINKING:
            return ThinkingMessage(
                type=MessageType.THINKING,
                content=data.get("content", "")
            )
        elif msg_type == MessageType.CONTENT:
            return ContentMessage(
                type=MessageType.CONTENT,
                content=data.get("content", "")
            )
        elif msg_type == MessageType.TOKENS:
            return TokensMessage(
                type=MessageType.TOKENS,
                total=data.get("total", 0),
                prompt=data.get("prompt", 0),
                completion=data.get("completion", 0)
            )
        elif msg_type == MessageType.ERROR:
            return ErrorMessage(
                type=MessageType.ERROR,
                content=data.get("content", ""),
                code=data.get("code", "")
            )
        elif msg_type == MessageType.INTERRUPT:
            return InterruptMessage(type=MessageType.INTERRUPT)
        else:
            raise MessageDecodeError(f"Unknown message type: {msg_type}")

    except (ValueError, TypeError) as e:
        raise MessageDecodeError(f"Failed to decode message: {e}") from e


def message_to_dict(message: BridgeMessage) -> OutputMessage:
    """
    将消息转换为字典（用于 JSON 序列化）。

    Args:
        message: 消息对象

    Returns:
        OutputMessage: 可序列化为 JSON 的字典

    Raises:
        MessageEncodeError: 当消息类型未知时
    """
    try:
        if isinstance(message, StatusMessage):
            return {
                "type": MessageType.STATUS.value,
                "content": message.content.value
            }
        elif isinstance(message, ThinkingMessage):
            return {
                "type": MessageType.THINKING.value,
                "content": message.content
            }
        elif isinstance(message, ContentMessage):
            return {
                "type": MessageType.CONTENT.value,
                "content": message.content
            }
        elif isinstance(message, TokensMessage):
            return {
                "type": MessageType.TOKENS.value,
                "total": message.total,
                "prompt": message.prompt,
                "completion": message.completion
            }
        elif isinstance(message, ErrorMessage):
            return {
                "type": MessageType.ERROR.value,
                "content": message.content,
                "code": message.code
            }
        elif isinstance(message, InterruptMessage):
            return {"type": MessageType.INTERRUPT.value}
        else:
            raise MessageEncodeError(f"Unknown message type: {type(message)}")

    except Exception as e:
        raise MessageEncodeError(f"Failed to encode message: {e}") from e


def message_to_json(message: BridgeMessage) -> str:
    """
    将消息序列化为 JSON 字符串。

    Args:
        message: 消息对象

    Returns:
        str: JSON 字符串
    """
    data = message_to_dict(message)
    return json.dumps(data, ensure_ascii=False)


def message_from_json(json_str: str) -> BridgeMessage:
    """
    从 JSON 字符串解析消息。

    Args:
        json_str: JSON 字符串

    Returns:
        BridgeMessage: 解析后的消息对象
    """
    try:
        data = json.loads(json_str)
        return message_from_dict(data)
    except json.JSONDecodeError as e:
        raise MessageDecodeError(f"Invalid JSON: {e}") from e


def create_status_message(content: StatusType | str) -> OutputMessage:
    """
    创建状态消息字典。

    Args:
        content: 状态内容

    Returns:
        OutputMessage: 消息字典
    """
    if isinstance(content, str):
        content = StatusType(content)
    return message_to_dict(StatusMessage(content=content))


def create_thinking_message(content: str) -> OutputMessage:
    """
    创建思考消息字典。

    Args:
        content: 思考内容

    Returns:
        OutputMessage: 消息字典
    """
    return message_to_dict(ThinkingMessage(content=content))


def create_content_message(content: str) -> OutputMessage:
    """
    创建正文消息字典。

    Args:
        content: 正文内容

    Returns:
        OutputMessage: 消息字典
    """
    return message_to_dict(ContentMessage(content=content))


def create_tokens_message(total: int, prompt: int, completion: int) -> OutputMessage:
    """
    创建 Token 统计消息字典。

    Args:
        total: 总 token 数
        prompt: 提示词 token 数
        completion: 补全 token 数

    Returns:
        OutputMessage: 消息字典
    """
    return message_to_dict(TokensMessage(total=total, prompt=prompt, completion=completion))


def create_error_message(content: str, code: str = "") -> OutputMessage:
    """
    创建错误消息字典。

    Args:
        content: 错误内容
        code: 错误代码

    Returns:
        OutputMessage: 消息字典
    """
    return message_to_dict(ErrorMessage(content=content, code=code))


__all__ = [
    "MessageDecodeError",
    "MessageEncodeError",
    "message_from_dict",
    "message_to_dict",
    "message_to_json",
    "message_from_json",
    "create_status_message",
    "create_thinking_message",
    "create_content_message",
    "create_tokens_message",
    "create_error_message",
]
