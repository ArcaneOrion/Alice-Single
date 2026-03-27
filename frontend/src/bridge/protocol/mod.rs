//! # 协议模块
//!
//! 定义 Bridge 通信协议和编解码。

pub mod codec;
pub mod message;

pub use codec::{DecodeError, DecodeResult, EncodeError, EncodeResult, JsonLinesCodec};
pub use message::{BridgeMessage, StatusContent};
