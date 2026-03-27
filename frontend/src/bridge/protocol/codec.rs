//! # JSON Lines 编解码器
//!
//! 处理 BridgeMessage 与 JSON Lines 格式之间的转换。
//!
//! ## 格式
//!
//! JSON Lines: 每行一个 JSON 对象，以换行符 `\n` 分隔。
//!
//! ## 错误处理
//!
//! - 无效的 JSON 行会被跳过
//! - 未知类型的消息会被解析为 `BridgeMessage::Error`

use serde_json;
use std::io::{BufRead, Write};

use super::message::BridgeMessage;

/// 编码结果
pub type EncodeResult<T> = Result<T, EncodeError>;

/// 解码结果
pub type DecodeResult<T> = Result<T, DecodeError>;

/// 编码错误
#[derive(Debug, thiserror::Error)]
pub enum EncodeError {
    #[error("JSON serialization error: {0}")]
    JsonError(#[from] serde_json::Error),

    #[error("IO error: {0}")]
    IoError(#[from] std::io::Error),
}

/// 解码错误
#[derive(Debug, thiserror::Error)]
pub enum DecodeError {
    #[error("JSON deserialization error: {0}")]
    JsonError(#[from] serde_json::Error),

    #[error("Invalid message format: {0}")]
    InvalidFormat(String),
}

/// JSON Lines 编解码器
#[derive(Debug, Clone)]
pub struct JsonLinesCodec;

impl JsonLinesCodec {
    /// 创建新的编解码器
    pub fn new() -> Self {
        Self
    }

    /// 将消息编码为 JSON Lines 格式 (单行 JSON + 换行符)
    ///
    /// # 示例
    ///
    /// ```ignore
    /// let codec = JsonLinesCodec::new();
    /// let msg = BridgeMessage::Status { content: StatusContent::Ready };
    /// let encoded = codec.encode(&msg)?;
    /// assert_eq!(encoded, "{\"type\":\"status\",\"content\":\"ready\"}\n");
    /// ```
    pub fn encode(&self, message: &BridgeMessage) -> EncodeResult<String> {
        let json = serde_json::to_string(message)?;
        Ok(format!("{}\n", json))
    }

    /// 编码并发送到写入器
    pub fn encode_to<W: Write>(
        &self,
        message: &BridgeMessage,
        writer: &mut W,
    ) -> EncodeResult<usize> {
        let json = self.encode(message)?;
        let bytes = json.as_bytes();
        writer.write_all(bytes)?;
        Ok(bytes.len())
    }

    /// 从单行 JSON 解析消息
    pub fn decode(&self, line: &str) -> DecodeResult<BridgeMessage> {
        let trimmed = line.trim();
        if trimmed.is_empty() {
            return Err(DecodeError::InvalidFormat("Empty line".into()));
        }
        let msg: BridgeMessage = serde_json::from_str(trimmed)?;
        Ok(msg)
    }

    /// 从读取器批量解析消息 (直到 EOF)
    pub fn decode_from_reader<R: BufRead>(&self, reader: &mut R) -> Vec<BridgeMessage> {
        let mut messages = Vec::new();
        for line in reader.lines() {
            match line {
                Ok(l) => {
                    if let Ok(msg) = self.decode(&l) {
                        messages.push(msg);
                    }
                    // 忽略无效行，继续处理后续消息
                }
                Err(_) => break,
            }
        }
        messages
    }
}

impl Default for JsonLinesCodec {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::bridge::protocol::message::StatusContent;

    #[test]
    fn test_encode_status() {
        let codec = JsonLinesCodec::new();
        let msg = BridgeMessage::Status {
            content: StatusContent::Ready,
        };
        let encoded = codec.encode(&msg).unwrap();
        assert_eq!(encoded, "{\"type\":\"status\",\"content\":\"ready\"}\n");
    }

    #[test]
    fn test_encode_thinking() {
        let codec = JsonLinesCodec::new();
        let msg = BridgeMessage::Thinking {
            content: "正在思考...".into(),
        };
        let encoded = codec.encode(&msg).unwrap();
        assert_eq!(
            encoded,
            "{\"type\":\"thinking\",\"content\":\"正在思考...\"}\n"
        );
    }

    #[test]
    fn test_decode_status() {
        let codec = JsonLinesCodec::new();
        let msg = codec
            .decode("{\"type\":\"status\",\"content\":\"ready\"}")
            .unwrap();
        assert_eq!(
            msg,
            BridgeMessage::Status {
                content: StatusContent::Ready
            }
        );
    }

    #[test]
    fn test_decode_tokens() {
        let codec = JsonLinesCodec::new();
        let msg = codec
            .decode("{\"type\":\"tokens\",\"total\":1234,\"prompt\":800,\"completion\":434}")
            .unwrap();
        assert_eq!(
            msg,
            BridgeMessage::Tokens {
                total: 1234,
                prompt: 800,
                completion: 434
            }
        );
    }

    #[test]
    fn test_decode_empty_line() {
        let codec = JsonLinesCodec::new();
        assert!(codec.decode("").is_err());
        assert!(codec.decode("   ").is_err());
    }

    #[test]
    fn test_decode_invalid_json() {
        let codec = JsonLinesCodec::new();
        assert!(codec.decode("not a json").is_err());
    }
}
