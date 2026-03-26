//! # Widget 模块
//!
//! 重新导出 UI 组件，提供简化的访问路径。

pub use crate::ui::component::{
    AgentStatus, Author, ChatViewConfig, ChatViewState, HeaderConfig, InputBoxConfig,
    Message, SidebarConfig, INPUT_HEIGHT,
};

pub use crate::ui::util::format_text_to_lines;
