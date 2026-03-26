//! # 消息类型定义
//!
//! 定义 Rust 前端与 Python 后端之间的通信消息格式。
//!
//! ## 协议
//!
//! 基于 JSON Lines (每行一个 JSON 对象)：
//!
//! ```json
//! {"type": "status", "content": "ready"}
//! {"type": "thinking", "content": "正在思考..."}
//! {"type": "content", "content": "回复内容"}
//! {"type": "tokens", "total": 1234, "prompt": 800, "completion": 434}
//! {"type": "error", "content": "错误描述"}
//! ```
//!
//! ## 变体
//!
//! - [`Status`] - 状态更新 (ready, thinking, executing_tool, done)
//! - [`Thinking`] - 思考过程流式内容
//! - [`Content`] - 正文流式内容
//! - [`Tokens`] - Token 统计
//! - [`Error`] - 错误消息
//! - [`Interrupt`] - 中断信号

use serde::{Deserialize, Serialize};

/// Bridge 通信消息
///
/// 使用 tagged enum 表示，序列化为带 `type` 字段的 JSON 对象。
#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(tag = "type", rename_all = "lowercase")]
pub enum BridgeMessage {
    /// 状态更新消息
    Status { content: StatusContent },

    /// 思考过程内容 (显示在侧边栏)
    Thinking { content: String },

    /// 正文内容 (显示在主聊天区)
    Content { content: String },

    /// Token 统计
    Tokens { total: usize, prompt: usize, completion: usize },

    /// 错误消息
    Error { content: String },

    /// 中断信号 (前端 → 后端)
    Interrupt,
}

impl BridgeMessage {
    /// 判断消息是否需要流式追加到当前响应
    pub fn is_stream_content(&self) -> bool {
        matches!(self, Self::Thinking { .. } | Self::Content { .. })
    }

    /// 获取流式消息的内容
    pub fn stream_content(&self) -> Option<&str> {
        match self {
            Self::Thinking { content } => Some(content),
            Self::Content { content } => Some(content),
            _ => None,
        }
    }
}

/// 状态消息的内容值
#[derive(Debug, Clone, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum StatusContent {
    /// 后端已就绪，可以接收新请求
    Ready,

    /// LLM 正在思考中
    Thinking,

    /// 正在执行工具
    ExecutingTool,

    /// 当前请求处理完成
    Done,
}

impl AsRef<str> for StatusContent {
    fn as_ref(&self) -> &str {
        match self {
            Self::Ready => "ready",
            Self::Thinking => "thinking",
            Self::ExecutingTool => "executing_tool",
            Self::Done => "done",
        }
    }
}

impl std::fmt::Display for StatusContent {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.as_ref())
    }
}

/// 用于反序列化时的字符串变体
///
/// Python 侧发送的是字符串，我们需要先解析为字符串再转换。
#[derive(Debug, Clone, Deserialize)]
#[serde(field_identifier, rename_all = "snake_case")]
enum StatusField {
    Ready,
    Thinking,
    ExecutingTool,
    Done,
}

/// 状态消息的字符串内容 (用于与 Python 兼容)
///
/// Python 侧发送 `"content": "ready"` 这样的字符串，
/// 我们需要将其反序列化为 `StatusContent` 枚举。
#[derive(Debug, Deserialize)]
struct RawStatusMessage {
    content: String,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_serialize_status() {
        let msg = BridgeMessage::Status { content: StatusContent::Ready };
        let json = serde_json::to_string(&msg).unwrap();
        assert_eq!(json, r#"{"type":"status","content":"ready"}"#);
    }

    #[test]
    fn test_serialize_tokens() {
        let msg = BridgeMessage::Tokens { total: 1234, prompt: 800, completion: 434 };
        let json = serde_json::to_string(&msg).unwrap();
        assert_eq!(json, r#"{"type":"tokens","total":1234,"prompt":800,"completion":434}"#);
    }

    #[test]
    fn test_serialize_interrupt() {
        let msg = BridgeMessage::Interrupt;
        let json = serde_json::to_string(&msg).unwrap();
        assert_eq!(json, r#"{"type":"interrupt"}"#);
    }

    #[test]
    fn test_is_stream_content() {
        assert!(BridgeMessage::Thinking { content: "test".into() }.is_stream_content());
        assert!(BridgeMessage::Content { content: "test".into() }.is_stream_content());
        assert!(!BridgeMessage::Status { content: StatusContent::Ready }.is_stream_content());
        assert!(!BridgeMessage::Tokens { total: 0, prompt: 0, completion: 0 }.is_stream_content());
    }
}
