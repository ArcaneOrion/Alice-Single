//! # Bridge 模块
//!
//! 负责 Rust 前端与 Python 后端之间的通信桥接。
//!
//! ## 架构
//!
//! ```text
//! ┌─────────────────────────────────────────────────────────┐
//! │                    Bridge Client                        │
//! │  ┌───────────────┐  ┌──────────────┐  ┌─────────────┐ │
//! │  │   Message     │  │    Codec     │  │  Transport  │ │
//! │  │   Types       │→ │   (JSON)     │→ │  (stdio)    │ │
//! │  └───────────────┘  └──────────────┘  └─────────────┘ │
//! └─────────────────────────────────────────────────────────┘
//!                              ↓
//!                      Python 后端进程
//! ```
//!
//! ## 模块
//!
//! - [`client`] - Python 子进程客户端
//! - [`protocol`] - 消息协议定义和编解码
//! - [`transport`] - 底层传输抽象 (stdin/stdout)

pub mod client;
pub mod protocol;
pub mod transport;

// 重新导出常用类型
pub use client::BridgeClient;
pub use protocol::message::BridgeMessage;

/// 桥接层错误类型
pub type BridgeResult<T> = Result<T, BridgeError>;

/// 桥接层错误
#[derive(Debug, thiserror::Error)]
pub enum BridgeError {
    /// 子进程启动失败
    #[error("Failed to spawn child process: {0}")]
    SpawnError(#[from] std::io::Error),

    /// 消息编解码失败
    #[error("Codec error: {0}")]
    CodecError(String),

    /// 子进程已终止
    #[error("Child process exited: {0}")]
    ProcessExited(String),

    /// 通道关闭
    #[error("Channel closed")]
    ChannelClosed,
}
