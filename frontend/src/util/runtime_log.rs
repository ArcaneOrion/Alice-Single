//! # TUI 安全日志模块
//!
//! 将运行时日志写入文件，避免在 raw mode + alternate screen 下污染 TUI 渲染。
//!
//! 日志文件路径：`CARGO_MANIFEST_DIR/frontend.log`

use std::fs::OpenOptions;
use std::io::Write;
use std::path::PathBuf;
use std::sync::Mutex;

/// 全局文件锁，保证多线程安全写入
static LOG_LOCK: Mutex<()> = Mutex::new(());

fn log_path() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("frontend.log")
}

/// 写入一条运行时日志到文件。
///
/// 格式：`[event][module] detail`
///
/// 写入失败时静默忽略——TUI 模式下不能让日志问题影响主流程。
pub fn runtime_log(module: &str, event: &str, detail: &str) {
    let line = format!("[{}][{}] {}\n", event, module, detail);
    let _guard = LOG_LOCK.lock().unwrap_or_else(|e| e.into_inner());
    if let Ok(mut file) = OpenOptions::new()
        .create(true)
        .append(true)
        .open(log_path())
    {
        let _ = file.write_all(line.as_bytes());
    }
}
