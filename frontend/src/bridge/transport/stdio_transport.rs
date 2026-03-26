//! # stdin/stdout 传输层
//!
//! 通过标准输入输出与 Python 子进程通信。
//!
//! ## 架构
//!
//! ```text
//! Rust                          Python
│ ┌──────────────┐              ┌──────────────┐
│ │  StdioWriter │──stdin──────→│              │
│ └──────────────┘              │              │
│                               │ tui_bridge   │
│ ┌──────────────┐              │     .py      │
│ │StdioReader   │←─stdout─────│              │
│ └──────────────┘              └──────────────┘
//! ```
//!
//! ## 线程安全
//!
//! - `StdioWriter` 包装了 `ChildStdin`，实现了 `Send`
//! - 读取操作在独立线程中进行，通过 `mpsc::channel` 传递消息

use std::io::{BufRead, BufReader, Write};
use std::process::{Child, ChildStdin, ChildStdout, ChildStderr, Stdio};
use std::sync::mpsc::{self, Receiver, Sender};
use std::thread;

use crate::bridge::BridgeMessage;
use crate::bridge::protocol::codec::JsonLinesCodec;

/// 子进程标准输入的包装器
///
/// `ChildStdin` 本身不实现 `Send`，我们需要用 newtype 模式包装它。
pub struct ChildStdinWrapper(pub ChildStdin);

// SAFETY: `ChildStdin` 实际上是线程安全的，只是标准库没有标记为 `Send`
// 这在 Rust 社区是常见的做法
unsafe impl Send for ChildStdinWrapper {}

impl std::ops::Deref for ChildStdinWrapper {
    type Target = ChildStdin;

    fn deref(&self) -> &Self::Target {
        &self.0
    }
}

impl std::ops::DerefMut for ChildStdinWrapper {
    fn deref_mut(&mut self) -> &mut Self::Target {
        &mut self.0
    }
}

/// stdin/stdout 传输层
///
/// 负责：
/// 1. 启动 Python 子进程
/// 2. 设置 stdout/stderr 读取线程
/// 3. 提供写入 stdin 的接口
pub struct StdioTransport {
    /// Python 子进程句柄
    child: Child,

    /// stdin 写入器
    stdin: ChildStdinWrapper,

    /// 消息接收器 (来自 stdout)
    receiver: Receiver<BridgeMessage>,

    /// 错误接收器 (来自 stderr)
    error_receiver: Receiver<String>,
}

impl StdioTransport {
    /// 默认的 Python 桥接脚本路径
    pub const DEFAULT_BRIDGE_PATH: &'static str = "./tui_bridge.py";

    /// 创建新的传输层并启动 Python 子进程
    ///
    /// # 参数
    ///
    /// - `bridge_path`: Python 桥接脚本的路径
    ///
    /// # 返回
    ///
    /// 返回 `(transport, message_rx, error_rx)`:
    /// - `transport`: 传输层实例，用于发送消息
    /// - `message_rx`: 接收来自 Python 的消息
    /// - `error_rx`: 接收来自 Python stderr 的错误
    ///
    /// # 错误
    ///
    /// 如果子进程启动失败，返回 `io::Error`。
    pub fn spawn(bridge_path: &str) -> std::io::Result<(Self, Receiver<BridgeMessage>, Receiver<String>)> {
        // 启动 Python 子进程
        let mut child = std::process::Command::new("python3")
            .arg(bridge_path)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()?;

        let stdin = child.stdin.take().ok_or(std::io::Error::new(
            std::io::ErrorKind::BrokenPipe,
            "Failed to open stdin"
        ))?;

        let stdout = child.stdout.take().ok_or(std::io::Error::new(
            std::io::ErrorKind::BrokenPipe,
            "Failed to open stdout"
        ))?;

        let stderr = child.stderr.take().ok_or(std::io::Error::new(
            std::io::ErrorKind::BrokenPipe,
            "Failed to open stderr"
        ))?;

        // 创建消息通道
        let (tx, rx): (Sender<BridgeMessage>, Receiver<BridgeMessage>) = mpsc::channel();
        let tx_err = tx.clone();
        let (err_tx, err_rx): (Sender<String>, Receiver<String>) = mpsc::channel();

        // 启动 stdout 读取线程
        thread::spawn(move || {
            let codec = JsonLinesCodec::new();
            let reader = BufReader::new(stdout);
            for line in reader.lines() {
                if let Ok(l) = line {
                    if let Ok(msg) = codec.decode(&l) {
                        let _ = tx.send(msg);
                    }
                }
            }
        });

        // 启动 stderr 读取线程
        thread::spawn(move || {
            let reader = BufReader::new(stderr);
            for line in reader.lines() {
                if let Ok(l) = line {
                    if !l.trim().is_empty() {
                        // 将 stderr 内容转换为错误消息
                        let _ = tx_err.send(BridgeMessage::Error {
                            content: format!("Backend stderr: {}", l)
                        });
                        // 同时发送到错误通道
                        let _ = err_tx.send(l);
                    }
                }
            }
        });

        Ok((
            Self {
                child,
                stdin: ChildStdinWrapper(stdin),
                receiver: rx,
                error_receiver: err_rx,
            },
            rx,
            err_rx,
        ))
    }

    /// 使用默认路径创建传输层
    pub fn spawn_default() -> std::io::Result<(Self, Receiver<BridgeMessage>, Receiver<String>)> {
        Self::spawn(Self::DEFAULT_BRIDGE_PATH)
    }

    /// 发送原始文本到 Python (通过 stdin)
    ///
    /// # 参数
    ///
    /// - `text`: 要发送的文本内容 (通常是用户输入或中断信号)
    ///
    /// # 返回
    ///
    /// 返回写入的字节数，或错误。
    pub fn send_text(&mut self, text: &str) -> std::io::Result<usize> {
        writeln!(&mut self.stdin.0, "{}", text)?;
        Ok(text.len() + 1) // +1 for newline
    }

    /// 发送中断信号到 Python
    pub fn send_interrupt(&mut self) -> std::io::Result<()> {
        self.send_text("__INTERRUPT__").map(|_| ())
    }

    /// 获取消息接收器
    pub fn receiver(&self) -> &Receiver<BridgeMessage> {
        &self.receiver
    }

    /// 获取错误接收器
    pub fn error_receiver(&self) -> &Receiver<String> {
        &self.error_receiver
    }

    /// 获取 stdin 写入器的引用
    pub fn stdin(&self) -> &ChildStdinWrapper {
        &self.stdin
    }

    /// 获取 stdin 写入器的可变引用
    pub fn stdin_mut(&mut self) -> &mut ChildStdinWrapper {
        &mut self.stdin
    }

    /// 终止子进程
    pub fn kill(mut self) -> std::io::Result<()> {
        self.child.kill()
    }
}

/// stdin 写入器的便捷封装
///
/// 当只需要向 Python 发送消息时，可以使用此类型。
pub struct StdioWriter {
    stdin: ChildStdinWrapper,
}

impl StdioWriter {
    /// 从 ChildStdin 创建新的写入器
    pub fn new(stdin: ChildStdin) -> Self {
        Self(ChildStdinWrapper(stdin))
    }

    /// 发送文本
    pub fn send(&mut self, text: &str) -> std::io::Result<()> {
        writeln!(&mut self.stdin.0, "{}", text)
    }

    /// 发送中断信号
    pub fn interrupt(&mut self) -> std::io::Result<()> {
        self.send("__INTERRUPT__")
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_child_stdin_wrapper_send() {
        // 验证 `ChildStdinWrapper` 实现了 `Send`
        fn assert_send<T: Send>() {}
        assert_send::<ChildStdinWrapper>();
    }
}
