//! # 应用状态模块
//!
//! 提供 TUI 应用的核心状态管理功能，包括：
//!
//! - [`state`] - 应用状态结构（App、Message、AgentStatus 等）
//! - [`message_queue`] - 消息队列管理
//! - [`constants`] - 应用常量定义
//!
//! ## 示例
//!
//! ```rust
//! use frontend::app::{App, AgentStatus};
//!
//! let mut app = App::new();
//! assert_eq!(app.status, AgentStatus::Starting);
//! ```

pub mod constants;
pub mod message_queue;
pub mod state;

// 重新导出常用类型
pub use state::{
    AgentStatus, App, AreaBounds, Author, ChildStdinWrapper, Message, TokenStats,
};
pub use message_queue::{MessageQueue, MessageQueueConfig, MessageQueueStats};

// 导出常量
pub use constants::{
    DEFAULT_MAX_MESSAGES, DEFAULT_TICK_RATE_MS, HEADER_HEIGHT,
    INPUT_HEIGHT, INPUT_TITLE_READY, INPUT_TITLE_WAITING,
    MSG_WELCOME_INIT, MSG_WELCOME_READY, PRUNE_KEEP_MESSAGE_COUNT, SPINNER_FRAMES,
};
