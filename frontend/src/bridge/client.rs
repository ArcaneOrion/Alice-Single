//! # Python 桥接客户端
//!
//! 负责 Python 子进程的生命周期管理和通信。
//!
//! ## 职责
//!
//! 1. **进程管理**: 启动、监控、终止 Python 后端进程
//! 2. **消息发送**: 将用户输入和中断信号发送到 Python
//! 3. **消息接收**: 接收来自 Python 的状态、内容、错误消息
//! 4. **线程协调**: 管理 stdout/stderr 读取线程
//!
//! ## 使用示例
//!
//! ```ignore
//! let client = BridgeClient::spawn()?;
//! let msg_rx = client.message_receiver();
//! let err_rx = client.error_receiver();
//!
//! // 发送用户输入
//! client.send_input("Hello, Alice!")?;
//!
//! // 接收消息
//! while let Ok(msg) = msg_rx.recv() {
//!     match msg {
//!         BridgeMessage::Content { content } => println!("{}", content),
//!         BridgeMessage::Status { content } => println!("Status: {:?}", content),
//!         // ...
//!     }
//! }
//! ```

use std::sync::mpsc::{Receiver, TryRecvError};

use crate::bridge::protocol::message::{BridgeMessage, StatusContent};
use crate::bridge::transport::stdio_transport::{ChildStdinWrapper, StdioTransport};
use crate::bridge::{BridgeError, BridgeResult};
use crate::util::runtime_log::runtime_log;

fn summarize_text(text: &str, limit: usize) -> String {
    let normalized = text.replace('\n', "\\n");
    if normalized.chars().count() <= limit {
        normalized
    } else {
        let trimmed: String = normalized.chars().take(limit).collect();
        format!("{trimmed}...")
    }
}

/// Python 桥接客户端
///
/// 管理与 Python 后端的完整连接。
pub struct BridgeClient {
    /// 底层传输层
    transport: StdioTransport,

    /// 消息接收器 (来自 Python stdout)
    message_rx: Receiver<BridgeMessage>,

    /// 错误接收器 (来自 Python stderr)
    error_rx: Receiver<String>,

    /// 客户端状态
    state: ClientState,
}

/// 客户端状态
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ClientState {
    /// 刚创建，尚未连接
    Initial,

    /// 已连接到 Python
    Connected,

    /// Python 已准备就绪
    Ready,

    /// 连接断开
    Disconnected,
}

impl BridgeClient {
    /// 使用默认桥接脚本路径创建客户端
    ///
    /// # 默认路径
    ///
    /// `../backend/alice/cli/main.py`
    pub fn spawn_default() -> BridgeResult<Self> {
        Self::spawn(&StdioTransport::default_bridge_path().to_string_lossy())
    }

    /// 创建并启动新的 Python 桥接客户端
    ///
    /// # 参数
    ///
    /// - `bridge_path`: Python 桥接脚本的路径
    ///
    /// # 返回
    ///
    /// 返回初始化完成的客户端实例。
    pub fn spawn(bridge_path: &str) -> BridgeResult<Self> {
        runtime_log(
            "bridge.client",
            "system.start",
            &format!(
                "phase=bridge_client.spawn.start bridge_path={}",
                bridge_path
            ),
        );
        let (transport, message_rx, error_rx) = match StdioTransport::spawn(bridge_path) {
            Ok(parts) => parts,
            Err(err) => {
                runtime_log(
                    "bridge.client",
                    "bridge.error",
                    &format!("phase=bridge_client.spawn error={}", err),
                );
                return Err(err.into());
            }
        };
        runtime_log(
            "bridge.client",
            "system.start",
            "phase=bridge_client.spawn.connected state=connected",
        );

        Ok(Self {
            transport,
            message_rx,
            error_rx,
            state: ClientState::Connected,
        })
    }

    /// 发送用户输入到 Python
    ///
    /// # 参数
    ///
    /// - `input`: 用户输入的文本
    pub fn send_input(&mut self, input: &str) -> BridgeResult<()> {
        runtime_log(
            "bridge.client",
            "bridge.message_sent",
            &format!(
                "direction=frontend->backend message_type=user_input message_length={} summary={}",
                input.len(),
                summarize_text(input, 120)
            ),
        );
        self.transport.send_text(input)?;
        Ok(())
    }

    /// 发送中断信号到 Python
    ///
    /// 这将通知 Python 停止当前操作并返回空闲状态。
    pub fn send_interrupt(&mut self) -> BridgeResult<()> {
        runtime_log(
            "bridge.client",
            "bridge.interrupt",
            "direction=frontend->backend phase=bridge_client.send_interrupt",
        );
        self.transport.send_interrupt()?;
        Ok(())
    }

    /// 尝试接收一条消息 (非阻塞)
    ///
    /// # 返回
    ///
    /// - `Some(Ok(msg))`: 成功接收消息
    /// - `Some(Err(e))`: 接收出错
    /// - `None`: 通道无消息
    pub fn try_recv_message(&self) -> Option<Result<BridgeMessage, BridgeError>> {
        match self.message_rx.try_recv() {
            Ok(msg) => {
                if let BridgeMessage::Error { content } = &msg {
                    runtime_log(
                        "bridge.client",
                        "bridge.error",
                        &format!(
                            "phase=message_channel.recv message_type=error content_length={} summary={}",
                            content.len(),
                            summarize_text(content, 120)
                        ),
                    );
                }
                Some(Ok(msg))
            }
            Err(TryRecvError::Empty) => None,
            Err(TryRecvError::Disconnected) => {
                runtime_log(
                    "bridge.client",
                    "bridge.eof",
                    "phase=message_channel.recv reason=channel_closed",
                );
                Some(Err(BridgeError::ChannelClosed))
            }
        }
    }

    /// 阻塞接收一条消息
    ///
    /// # 返回
    ///
    /// 返回接收到的消息，或通道关闭错误。
    pub fn recv_message(&self) -> Result<BridgeMessage, BridgeError> {
        self.message_rx
            .recv()
            .map_err(|_| BridgeError::ChannelClosed)
    }

    /// 尝试接收一条错误消息 (非阻塞)
    pub fn try_recv_error(&self) -> Option<String> {
        match self.error_rx.try_recv() {
            Ok(err) => {
                runtime_log(
                    "bridge.client",
                    "bridge.error",
                    &format!(
                        "phase=error_channel.recv message_length={} summary={}",
                        err.len(),
                        summarize_text(&err, 120)
                    ),
                );
                Some(err)
            }
            Err(TryRecvError::Empty) => None,
            Err(TryRecvError::Disconnected) => {
                runtime_log(
                    "bridge.client",
                    "bridge.eof",
                    "phase=error_channel.recv reason=channel_closed",
                );
                None
            }
        }
    }

    /// 获取消息接收器的引用
    pub fn message_receiver(&self) -> &Receiver<BridgeMessage> {
        &self.message_rx
    }

    /// 获取错误接收器的引用
    pub fn error_receiver(&self) -> &Receiver<String> {
        &self.error_rx
    }

    /// 获取 stdin 写入器的引用
    pub fn stdin(&self) -> &ChildStdinWrapper {
        self.transport.stdin()
    }

    /// 获取 stdin 写入器的可变引用
    pub fn stdin_mut(&mut self) -> &mut ChildStdinWrapper {
        self.transport.stdin_mut()
    }

    /// 获取当前状态
    pub fn state(&self) -> ClientState {
        self.state
    }

    /// 设置状态
    pub fn set_state(&mut self, state: ClientState) {
        self.state = state;
    }

    /// 处理状态消息 (内部使用)
    pub fn handle_status_message(&mut self, content: &StatusContent) {
        match content {
            StatusContent::Ready => {
                self.state = ClientState::Ready;
                runtime_log("bridge.client", "system.start", "phase=backend.ready state=ready");
            }
            StatusContent::Done => self.state = ClientState::Ready,
            _ => {}
        }
    }

    /// 终止 Python 进程
    pub fn shutdown(mut self) -> BridgeResult<()> {
        runtime_log("bridge.client", "system.shutdown", "phase=bridge_client.shutdown.start");
        self.transport.kill()?;
        self.state = ClientState::Disconnected;
        runtime_log("bridge.client", "system.shutdown", "phase=bridge_client.shutdown.done");
        Ok(())
    }

    #[cfg(test)]
    pub(crate) fn with_test_channels(
        message_rx: Receiver<BridgeMessage>,
        error_rx: Receiver<String>,
    ) -> BridgeResult<Self> {
        let transport = StdioTransport::spawn_test_transport()?;

        Ok(Self {
            transport,
            message_rx,
            error_rx,
            state: ClientState::Connected,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_client_state() {
        let state = ClientState::Initial;
        assert_eq!(state, ClientState::Initial);
        assert_ne!(state, ClientState::Connected);
    }
}
