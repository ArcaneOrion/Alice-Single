//! # 事件模块
//!
//! 定义和管理 TUI 系统的所有事件类型和事件总线。

pub mod event_bus;
pub mod types;

// 重新导出常用类型
pub use event_bus::{EventBus, EventSender};
pub use types::{
    AppEvent, AreaBounds, BridgeMessage, KeyCode, KeyModifiers, KeyboardEvent, MouseButton,
    MouseEvent, MouseEventKind, ScrollState, UiArea,
};
