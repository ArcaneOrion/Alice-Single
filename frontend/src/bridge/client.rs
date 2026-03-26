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

use std::sync::mpsc::Receiver;
use std::process::ChildStdin;

use crate::bridge::{BridgeError, BridgeResult};
use crate::bridge::transport::stdio_transport::{ChildStdinWrapper, StdioTransport};
use crate::bridge::protocol::message::{BridgeMessage, StatusContent};

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
    /// `./tui_bridge.py`
    pub fn spawn_default() -> BridgeResult<Self> {
        Self::spawn("./tui_bridge.py")
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
        let (transport, message_rx, error_rx) = StdioTransport::spawn(bridge_path)?;

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
        self.transport.send_text(input)?;
        Ok(())
    }

    /// 发送中断信号到 Python
    ///
    /// 这将通知 Python 停止当前操作并返回空闲状态。
    pub fn send_interrupt(&mut self) -> BridgeResult<()> {
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
            Ok(msg) => Some(Ok(msg)),
            Err(mpsc::TryRecvError::Empty) => None,
            Err(mpsc::TryRecvError::Disconnected) => Some(Err(BridgeError::ChannelClosed)),
        }
    }

    /// 阻塞接收一条消息
    ///
    /// # 返回
    ///
    /// 返回接收到的消息，或通道关闭错误。
    pub fn recv_message(&self) -> Result<BridgeMessage, BridgeError> {
        self.message_rx.recv().map_err(|_| BridgeError::ChannelClosed)
    }

    /// 尝试接收一条错误消息 (非阻塞)
    pub fn try_recv_error(&self) -> Option<String> {
        self.error_rx.try_recv().ok()
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
            StatusContent::Ready => self.state = ClientState::Ready,
            StatusContent::Done => self.state = ClientState::Ready,
            _ => {}
        }
    }

    /// 终止 Python 进程
    pub fn shutdown(mut self) -> BridgeResult<()> {
        self.transport.kill()?;
        self.state = ClientState::Disconnected;
        Ok(())
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
