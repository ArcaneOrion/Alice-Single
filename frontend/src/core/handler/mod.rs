//! # 事件处理器模块
//!
//! 包含键盘和鼠标事件处理器。

pub mod keyboard_handler;
pub mod mouse_handler;

// 重新导出常用类型
pub use keyboard_handler::{KeyAction, KeyboardHandler};
pub use mouse_handler::{MouseAction, MouseHandler};
