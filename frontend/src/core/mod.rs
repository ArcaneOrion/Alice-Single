//! # Core 模块
//!
//! 提供前端核心功能，包括事件系统、事件处理和分发。
//!
//! ## 模块结构
//!
//! - [`event`] - 事件类型定义和事件总线
//! - [`handler`] - 键盘和鼠标事件处理器
//! - [`dispatcher`] - 事件分发器
//!
//! ## 使用示例
//!
//! ```ignore
//! use std::time::Duration;
//!
//! use alice_frontend::core::{AppState, EventBus, EventDispatcher};
//!
//! // 创建事件总线
//! let event_bus = EventBus::new();
//!
//! // 创建事件分发器
//! let mut dispatcher = EventDispatcher::new(event_bus);
//!
//! // 更新状态
//! dispatcher.set_state(AppState::Idle);
//!
//! // 在事件循环中
//! dispatcher.dispatch_crossterm(Duration::from_millis(100))?;
//! ```

pub mod dispatcher;
pub mod event;
pub mod handler;

// 重新导出常用类型
pub use dispatcher::{AppState, EventDispatcher, EventLoop};
pub use event::{
    AppEvent, AreaBounds, EventBus, EventSender, KeyCode, KeyModifiers, KeyboardEvent, MouseEvent,
    MouseEventKind, ScrollState, UiArea,
};
pub use handler::{KeyAction, KeyboardHandler, MouseAction, MouseHandler};
