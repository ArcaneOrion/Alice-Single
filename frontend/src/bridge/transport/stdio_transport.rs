//! # stdin/stdout 传输层
//!
//! 通过标准输入输出与 Python 子进程通信。
//!
//! ## 架构
//!
//! ```text
//! Rust                          Python
//! │ ┌──────────────┐              ┌──────────────┐
//! │ │  StdioWriter │──stdin──────→│              │
//! │ └──────────────┘              │              │
//! │                               │ tui_bridge   │
//! │ ┌──────────────┐              │     .py      │
//! │ │StdioReader   │←─stdout─────│              │
//! │ └──────────────┘              └──────────────┘
//! ```
//!
//! ## 线程安全
//!
//! - `StdioWriter` 包装了 `ChildStdin`，实现了 `Send`
//! - 读取操作在独立线程中进行，通过 `mpsc::channel` 传递消息

use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::process::{Child, ChildStdin, Stdio};
use std::sync::mpsc::{self, Receiver, Sender};
use std::thread;

use crate::bridge::BridgeMessage;
use crate::bridge::protocol::codec::JsonLinesCodec;
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

fn summarize_bridge_message(msg: &BridgeMessage) -> (&'static str, String) {
    match msg {
        BridgeMessage::Status { content } => ("status", format!("status={}", content)),
        BridgeMessage::Thinking { content } => ("thinking", summarize_text(content, 120)),
        BridgeMessage::Content { content } => ("content", summarize_text(content, 120)),
        BridgeMessage::Tokens {
            total,
            prompt,
            completion,
        } => (
            "tokens",
            format!(
                "total={},prompt={},completion={}",
                total, prompt, completion
            ),
        ),
        BridgeMessage::Error { content } => ("error", summarize_text(content, 120)),
        BridgeMessage::Interrupt => ("interrupt", "__INTERRUPT__".to_string()),
    }
}

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
}

impl StdioTransport {
    /// 默认的 Python 桥接脚本路径（相对于 frontend crate 根目录）
    pub const DEFAULT_BRIDGE_PATH: &'static str = "../backend/alice/cli/main.py";

    /// 解析默认桥接脚本绝对路径
    pub fn default_bridge_path() -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join(Self::DEFAULT_BRIDGE_PATH)
    }

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
    pub fn spawn(
        bridge_path: &str,
    ) -> std::io::Result<(Self, Receiver<BridgeMessage>, Receiver<String>)> {
        runtime_log(
            "bridge.transport",
            "system.start",
            &format!("phase=backend.spawn.start bridge_path={}", bridge_path),
        );

        // 启动 Python 子进程 (使用 -u 禁用缓冲)
        let mut child = std::process::Command::new("python3")
            .arg("-u")
            .arg(bridge_path)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()?;
        runtime_log(
            "bridge.transport",
            "system.start",
            &format!("phase=backend.spawn.ok pid={}", child.id()),
        );

        let stdin = child.stdin.take().ok_or_else(|| {
            runtime_log(
                "bridge.transport",
                "bridge.error",
                "phase=backend.spawn.stdin error=Failed to open stdin",
            );
            std::io::Error::new(std::io::ErrorKind::BrokenPipe, "Failed to open stdin")
        })?;

        let stdout = child.stdout.take().ok_or_else(|| {
            runtime_log(
                "bridge.transport",
                "bridge.error",
                "phase=backend.spawn.stdout error=Failed to open stdout",
            );
            std::io::Error::new(std::io::ErrorKind::BrokenPipe, "Failed to open stdout")
        })?;

        let stderr = child.stderr.take().ok_or_else(|| {
            runtime_log(
                "bridge.transport",
                "bridge.error",
                "phase=backend.spawn.stderr error=Failed to open stderr",
            );
            std::io::Error::new(std::io::ErrorKind::BrokenPipe, "Failed to open stderr")
        })?;

        // 创建消息通道
        let (tx, rx): (Sender<BridgeMessage>, Receiver<BridgeMessage>) = mpsc::channel();
        let (err_tx, err_rx): (Sender<String>, Receiver<String>) = mpsc::channel();

        // 启动 stdout 读取线程
        thread::spawn(move || {
            runtime_log(
                "bridge.transport",
                "system.start",
                "phase=stdout_reader.start",
            );
            let codec = JsonLinesCodec::new();
            let reader = BufReader::new(stdout);
            for line_result in reader.lines() {
                match line_result {
                    Ok(line) => {
                        let line_len = line.len();
                        match codec.decode(&line) {
                            Ok(msg) => {
                                let (message_type, summary) = summarize_bridge_message(&msg);
                                runtime_log(
                                    "bridge.transport",
                                    "bridge.message_received",
                                    &format!(
                                        "direction=backend->frontend message_type={} payload_length={} summary={}",
                                        message_type, line_len, summary
                                    ),
                                );
                                if tx.send(msg).is_err() {
                                    runtime_log(
                                        "bridge.transport",
                                        "bridge.eof",
                                        "phase=stdout_reader.send reason=message_channel_closed",
                                    );
                                    break;
                                }
                            }
                            Err(err) => {
                                runtime_log(
                                    "bridge.transport",
                                    "bridge.error",
                                    &format!(
                                        "phase=stdout_reader.decode payload_length={} error={}",
                                        line_len, err
                                    ),
                                );
                            }
                        }
                    }
                    Err(err) => {
                        runtime_log(
                            "bridge.transport",
                            "bridge.error",
                            &format!("phase=stdout_reader.read error={}", err),
                        );
                        break;
                    }
                }
            }
            runtime_log("bridge.transport", "bridge.eof", "phase=stdout_reader.eof");
            runtime_log(
                "bridge.transport",
                "system.shutdown",
                "phase=stdout_reader.stop",
            );
        });

        // 启动 stderr 读取线程
        thread::spawn(move || {
            runtime_log(
                "bridge.transport",
                "system.start",
                "phase=stderr_reader.start",
            );
            let reader = BufReader::new(stderr);
            for line_result in reader.lines() {
                match line_result {
                    Ok(line) => {
                        if !line.trim().is_empty() {
                            runtime_log(
                                "bridge.transport",
                                "bridge.stderr",
                                &format!(
                                    "phase=stderr_reader.line message_length={} summary={}",
                                    line.len(),
                                    summarize_text(&line, 120)
                                ),
                            );
                            if err_tx.send(line).is_err() {
                                runtime_log(
                                    "bridge.transport",
                                    "bridge.eof",
                                    "phase=stderr_reader.send reason=error_channel_closed",
                                );
                                break;
                            }
                        }
                    }
                    Err(err) => {
                        runtime_log(
                            "bridge.transport",
                            "bridge.error",
                            &format!("phase=stderr_reader.read error={}", err),
                        );
                        break;
                    }
                }
            }
            runtime_log("bridge.transport", "bridge.eof", "phase=stderr_reader.eof");
            runtime_log(
                "bridge.transport",
                "system.shutdown",
                "phase=stderr_reader.stop",
            );
        });

        Ok((
            Self {
                child,
                stdin: ChildStdinWrapper(stdin),
            },
            rx,
            err_rx,
        ))
    }

    /// 使用默认路径创建传输层
    pub fn spawn_default() -> std::io::Result<(Self, Receiver<BridgeMessage>, Receiver<String>)> {
        let path = Self::default_bridge_path();
        Self::spawn(path.to_string_lossy().as_ref())
    }

    #[cfg(test)]
    pub(crate) fn spawn_test_transport() -> std::io::Result<Self> {
        let mut child = std::process::Command::new("python3")
            .arg("-u")
            .arg("-c")
            .arg("import sys\nfor _ in sys.stdin:\n    pass\n")
            .stdin(Stdio::piped())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()?;

        let stdin = child.stdin.take().ok_or(std::io::Error::new(
            std::io::ErrorKind::BrokenPipe,
            "Failed to open stdin",
        ))?;

        Ok(Self {
            child,
            stdin: ChildStdinWrapper(stdin),
        })
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
        self.send_line(text, "user_input")
    }

    /// 发送中断信号到 Python
    pub fn send_interrupt(&mut self) -> std::io::Result<()> {
        runtime_log(
            "bridge.transport",
            "bridge.interrupt",
            "direction=frontend->backend phase=send_interrupt signal=__INTERRUPT__",
        );
        self.send_line("__INTERRUPT__", "interrupt").map(|_| ())
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
        let pid = self.child.id();
        runtime_log(
            "bridge.transport",
            "system.shutdown",
            &format!("phase=backend.kill.start pid={}", pid),
        );
        let result = self.child.kill();
        if let Err(err) = &result {
            runtime_log(
                "bridge.transport",
                "bridge.error",
                &format!("phase=backend.kill error={}", err),
            );
        } else {
            runtime_log(
                "bridge.transport",
                "system.shutdown",
                &format!("phase=backend.kill.ok pid={}", pid),
            );
        }
        result
    }

    fn send_line(&mut self, text: &str, message_type: &str) -> std::io::Result<usize> {
        match writeln!(&mut self.stdin.0, "{}", text) {
            Ok(_) => {
                runtime_log(
                    "bridge.transport",
                    "bridge.message_sent",
                    &format!(
                        "direction=frontend->backend message_type={} message_length={} summary={}",
                        message_type,
                        text.len(),
                        summarize_text(text, 120)
                    ),
                );
                Ok(text.len() + 1) // +1 for newline
            }
            Err(err) => {
                runtime_log(
                    "bridge.transport",
                    "bridge.error",
                    &format!(
                        "phase=stdin_writer.write message_type={} message_length={} error={}",
                        message_type,
                        text.len(),
                        err
                    ),
                );
                Err(err)
            }
        }
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
        Self {
            stdin: ChildStdinWrapper(stdin),
        }
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
    fn test_default_bridge_path_is_absolute() {
        let path = StdioTransport::default_bridge_path();
        assert!(path.is_absolute());
        assert!(path.ends_with("backend/alice/cli/main.py"));
    }

    #[test]
    fn test_child_stdin_wrapper_send() {
        // 验证 `ChildStdinWrapper` 实现了 `Send`
        fn assert_send<T: Send>() {}
        assert_send::<ChildStdinWrapper>();
    }
}
