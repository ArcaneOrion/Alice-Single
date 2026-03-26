//! # Alice Frontend
//!
//! Rust 前端模块，负责 TUI 渲染和用户交互。
//!
//! ## 模块结构
//!
//! - [`bridge`] - 与 Python 后端的通信桥接
//! - [`core`] - 核心功能 (事件总线、处理器)
//! - [`ui`] - UI 组件和布局
//! - [`app`] - 应用状态和主逻辑

// 核心模块
pub mod bridge;
pub mod core;
pub mod ui;
pub mod app;
pub mod util;

// 重新导出常用类型
pub use bridge::{BridgeClient, BridgeMessage, BridgeResult};

/// 应用版本
pub const VERSION: &str = env!("CARGO_PKG_VERSION");
