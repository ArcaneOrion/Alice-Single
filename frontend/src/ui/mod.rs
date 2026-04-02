//! # UI 模块
//!
//! 提供 Alice-Single 的所有 UI 组件。

pub mod component;
pub mod screen;
pub mod util;
pub mod widget;

// 重新导出核心组件
pub use component::{
    AgentStatus, Author, ChatViewConfig, ChatViewState, HeaderConfig, INPUT_HEIGHT, InputBoxConfig,
    Message, SidebarConfig,
};

// 重新导出工具函数
pub use screen::render_app;
pub use util::format_text_to_lines;
