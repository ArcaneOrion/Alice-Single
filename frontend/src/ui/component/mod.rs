//! # 组件模块
//!
//! 导出所有 UI 组件。

pub mod chat;
pub mod header;
pub mod input;
pub mod sidebar;

// 重新导出常用类型
pub use header::{AgentStatus, HeaderConfig, render_header};
pub use chat::{Author, ChatViewConfig, ChatViewState, Message, render_chat_view};
pub use sidebar::{SidebarConfig, render_sidebar};
pub use input::{InputBoxConfig, INPUT_HEIGHT, render_input_box};
