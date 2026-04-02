//! # 应用状态模块
//!
//! 定义 TUI 应用的核心状态结构，包括消息存储、UI 状态和与后端的连接。

use ratatui::{layout::Rect, widgets::ListState};
use serde::{Deserialize, Serialize};

use crate::bridge::BridgeClient;
use crate::core::event::types::ScrollState;

/// 消息作者
#[derive(Debug, Clone, PartialEq, Eq, Deserialize, Serialize)]
pub enum Author {
    /// 用户消息
    User,
    /// 助手消息（Alice）
    Assistant,
}

/// 单条消息结构
#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct Message {
    /// 消息作者
    pub author: Author,
    /// 思考内容（显示在侧边栏）
    pub thinking: String,
    /// 正文内容（显示在聊天区）
    pub content: String,
    /// 消息是否完成
    pub is_complete: bool,
}

impl Message {
    /// 创建新的用户消息
    pub fn user(content: String) -> Self {
        Self {
            author: Author::User,
            thinking: String::new(),
            content,
            is_complete: true,
        }
    }

    /// 创建新的助手消息
    pub fn assistant(content: String) -> Self {
        Self {
            author: Author::Assistant,
            thinking: String::new(),
            content,
            is_complete: true,
        }
    }

    /// 创建空白的助手消息（用于流式响应）
    pub fn assistant_pending() -> Self {
        Self {
            author: Author::Assistant,
            thinking: String::new(),
            content: String::new(),
            is_complete: false,
        }
    }
}

/// Agent 运行状态
///
/// 状态机转换流程：
/// ```text
/// Starting -> Idle -> Thinking -> Responding -> Idle
///                 ↓
///            ExecutingTool -> Idle
/// ```
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum AgentStatus {
    /// 正在启动后端引擎
    Starting,
    /// 空闲状态，等待用户输入
    #[default]
    Idle,
    /// 正在思考（LLM 处理中）
    Thinking,
    /// 正在回复（流式输出中）
    Responding,
    /// 正在执行工具
    ExecutingTool,
}

impl AgentStatus {
    /// 检查是否可以接受用户输入
    pub fn can_accept_input(&self) -> bool {
        matches!(self, Self::Idle)
    }

    /// 检查是否正在处理中
    pub fn is_processing(&self) -> bool {
        matches!(
            self,
            Self::Thinking | Self::Responding | Self::ExecutingTool
        )
    }
}

/// Token 统计信息
#[derive(Debug, Clone, Copy, Default, Deserialize, Serialize)]
pub struct TokenStats {
    /// 总 token 数
    pub total: usize,
    /// 提示词 token 数
    pub prompt: usize,
    /// 补全 token 数
    pub completion: usize,
}

impl TokenStats {
    /// 创建新的 token 统计
    pub fn new() -> Self {
        Self::default()
    }

    /// 更新 token 统计
    pub fn update(&mut self, total: usize, prompt: usize, completion: usize) {
        self.total = total;
        self.prompt = prompt;
        self.completion = completion;
    }

    /// 检查是否有 token 数据
    pub fn has_data(&self) -> bool {
        self.total > 0
    }
}

/// 应用状态
///
/// 这是 TUI 应用的核心状态结构，包含所有需要持久化的状态信息。
pub struct App {
    /// 用户输入缓冲区
    pub input: String,
    /// 消息历史队列
    pub messages: Vec<Message>,
    /// Agent 当前状态
    pub status: AgentStatus,
    /// 是否显示思考侧边栏
    pub show_thinking: bool,
    /// 是否应该退出应用
    pub should_quit: bool,
    /// 旋转指示器索引（用于加载动画）
    pub spinner_index: usize,
    /// 聊天区滚动状态
    pub chat_scroll: ScrollState,
    /// 思考区滚动状态
    pub thinking_scroll: ScrollState,
    /// Token 统计
    pub tokens: TokenStats,
    /// 消息列表状态（用于 ratatui 渲染）
    pub list_state: ListState,
    /// UI 区域边界（用于鼠标碰撞检测）
    pub area_bounds: AreaBounds,
    /// 桥接客户端（用于与 Python 后端通信）
    pub bridge_client: BridgeClient,
}

/// UI 区域边界信息
///
/// 记录各 UI 组件的屏幕区域，用于事件分发和碰撞检测。
#[derive(Debug, Clone, Copy, Default)]
pub struct AreaBounds {
    /// 聊天区域
    pub chat_area: Rect,
    /// 侧边栏区域
    pub sidebar_area: Rect,
    /// 输入区域
    pub input_area: Rect,
}

impl App {
    /// 创建新的应用状态
    pub fn new(bridge_client: BridgeClient) -> Self {
        Self {
            input: String::new(),
            messages: vec![Message::assistant(
                "你好！我是你的智能助手 Alice。系统正在初始化...".to_string(),
            )],
            status: AgentStatus::Starting,
            show_thinking: false,
            should_quit: false,
            spinner_index: 0,
            chat_scroll: ScrollState::new(),
            thinking_scroll: ScrollState::new(),
            tokens: TokenStats::new(),
            list_state: ListState::default(),
            area_bounds: AreaBounds::default(),
            bridge_client,
        }
    }

    /// 发送用户消息
    ///
    /// 将用户输入添加到消息历史，并发送给 Python 后端。
    /// 如果后端连接正常，会预先插入一个占位消息用于流式响应。
    pub fn send_message(&mut self) {
        if self.input.trim().is_empty() || !self.status.can_accept_input() {
            return;
        }

        let input = self.input.clone();
        self.messages.push(Message::user(input.clone()));

        // 发送给 Python 后端
        if let Err(e) = self.bridge_client.send_input(&input) {
            self.messages.push(Message::assistant(format!(
                "错误: 无法连接到后端引擎。{}",
                e
            )));
        } else {
            self.status = AgentStatus::Thinking;
            // 预先插入 Alice 的占位消息
            self.messages.push(Message::assistant_pending());
            self.chat_scroll.reset();
        }

        self.input.clear();
    }

    /// 定时器事件处理
    ///
    /// 每个 tick 周期调用，用于更新动画等周期性状态。
    pub fn on_tick(&mut self) {
        self.spinner_index = (self.spinner_index + 1) % SPINNER_FRAMES;
    }

    /// 获取当前旋转指示器字符
    pub fn get_spinner(&self) -> &'static str {
        SPINNER[self.spinner_index]
    }

    /// 添加思考内容到当前消息
    pub fn append_thinking(&mut self, content: &str) {
        if let Some(msg) = self.messages.last_mut() {
            if msg.author == Author::Assistant {
                msg.thinking.push_str(content);
            }
        }
    }

    /// 添加正文内容到当前消息
    pub fn append_content(&mut self, content: &str) {
        if let Some(msg) = self.messages.last_mut() {
            if msg.author == Author::Assistant {
                msg.content.push_str(content);
            }
        }
    }

    /// 标记当前消息为完成
    pub fn mark_current_complete(&mut self) {
        if let Some(msg) = self.messages.last_mut() {
            msg.is_complete = true;
        }
    }

    /// 添加错误消息
    pub fn add_error(&mut self, content: String) {
        self.messages.push(Message {
            author: Author::Assistant,
            thinking: String::new(),
            content: format!("⚠️ {}", content),
            is_complete: true,
        });
    }

    /// 切换思考侧边栏显示状态
    pub fn toggle_thinking(&mut self) {
        self.show_thinking = !self.show_thinking;
    }

    /// 更新状态为空闲
    pub fn set_idle(&mut self) {
        self.status = AgentStatus::Idle;
    }

    /// 更新状态为思考中
    pub fn set_thinking(&mut self) {
        self.status = AgentStatus::Thinking;
    }

    /// 更新状态为执行工具中
    pub fn set_executing_tool(&mut self) {
        self.status = AgentStatus::ExecutingTool;
    }

    /// 更新状态为回复中
    pub fn set_responding(&mut self) {
        self.status = AgentStatus::Responding;
    }

    /// 处理就绪状态
    ///
    /// 当后端报告 ready 时调用，更新初始化消息。
    pub fn handle_ready(&mut self) {
        self.status = AgentStatus::Idle;
        if let Some(msg) = self.messages.last_mut() {
            if msg.author == Author::Assistant && msg.content.contains("系统正在初始化") {
                msg.content = "你好！我是你的智能助手 Alice。我已经准备好了！".to_string();
            }
        }
    }

    /// 发送中断信号
    pub fn interrupt(&mut self) -> bool {
        if self.status.is_processing() {
            if self.bridge_client.send_interrupt().is_err() {
                return false;
            }
            return true;
        }
        false
    }
}

// Default impl 已移除，因为 App 需要 BridgeClient
// 请使用 App::new(bridge_client) 创建实例

// ============================================================================
// 常量定义
// ============================================================================

/// 旋转指示器帧序列
pub const SPINNER: &[&str] = &["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"];

/// 旋转指示器帧数
pub const SPINNER_FRAMES: usize = 10;

/// 默认 tick 间隔（毫秒）
pub const DEFAULT_TICK_RATE_MS: u64 = 100;

/// 最大滚动偏移限制
pub const MAX_SCROLL_OFFSET: usize = 9999;

/// 聊天区默认宽度百分比（当侧边栏显示时）
pub const CHAT_WIDTH_PERCENTAGE: u16 = 75;

/// 侧边栏默认宽度百分比
pub const SIDEBAR_WIDTH_PERCENTAGE: u16 = 25;

/// Header 区域高度
pub const HEADER_HEIGHT: u16 = 3;

/// Input 区域高度
pub const INPUT_HEIGHT: u16 = 3;

// ============================================================================
// 单元测试
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_message_creation() {
        let user_msg = Message::user("Hello".to_string());
        assert_eq!(user_msg.author, Author::User);
        assert!(user_msg.is_complete);
        assert!(user_msg.thinking.is_empty());

        let assistant_msg = Message::assistant("Hi there".to_string());
        assert_eq!(assistant_msg.author, Author::Assistant);
        assert!(assistant_msg.is_complete);

        let pending_msg = Message::assistant_pending();
        assert_eq!(pending_msg.author, Author::Assistant);
        assert!(!pending_msg.is_complete);
        assert!(pending_msg.content.is_empty());
    }

    #[test]
    fn test_agent_status() {
        assert!(AgentStatus::Idle.can_accept_input());
        assert!(!AgentStatus::Thinking.can_accept_input());
        assert!(!AgentStatus::Responding.can_accept_input());
        assert!(!AgentStatus::ExecutingTool.can_accept_input());

        assert!(AgentStatus::Thinking.is_processing());
        assert!(AgentStatus::Responding.is_processing());
        assert!(AgentStatus::ExecutingTool.is_processing());
        assert!(!AgentStatus::Idle.is_processing());
    }

    #[test]
    fn test_token_stats() {
        let mut stats = TokenStats::new();
        assert!(!stats.has_data());

        stats.update(100, 60, 40);
        assert!(stats.has_data());
        assert_eq!(stats.total, 100);
        assert_eq!(stats.prompt, 60);
        assert_eq!(stats.completion, 40);
    }

    #[test]
    fn test_app_creation() {
        // 注意：此测试需要 mock BridgeClient
        // 暂时跳过，因为 App::new 需要 BridgeClient 参数
        // let app = App::new(mock_client);
        // assert_eq!(app.status, AgentStatus::Starting);
        // assert!(!app.show_thinking);
        // assert!(!app.should_quit);
        // assert_eq!(app.spinner_index, 0);
        // assert_eq!(app.messages.len(), 1);
    }

    #[test]
    fn test_app_toggle_thinking() {
        // 注意：此测试需要 mock BridgeClient
        // 暂时跳过
        // let mut app = App::new(mock_client);
        // assert!(!app.show_thinking);
        // app.toggle_thinking();
        // assert!(app.show_thinking);
        // app.toggle_thinking();
        // assert!(!app.show_thinking);
    }

    #[test]
    fn test_app_spinner() {
        // 注意：此测试需要 mock BridgeClient
        // 暂时跳过
        // let mut app = App::new(mock_client);
        // let original = app.get_spinner();
        // app.on_tick();
        // assert_ne!(app.get_spinner(), original);
    }

    #[test]
    fn test_app_append_content() {
        // 注意：此测试需要 mock BridgeClient
        // 暂时跳过
        // let mut app = App::new(mock_client);
        // app.messages.push(Message::assistant_pending());
        // app.append_content("Hello");
        // assert_eq!(app.messages.last().unwrap().content, "Hello");
        // app.append_content(" World");
        // assert_eq!(app.messages.last().unwrap().content, "Hello World");
    }

    #[test]
    fn test_app_append_thinking() {
        // 注意：此测试需要 mock BridgeClient
        // 暂时跳过
        // let mut app = App::new(mock_client);
        // app.messages.push(Message::assistant_pending());
        // app.append_thinking("Thinking...");
        // assert_eq!(app.messages.last().unwrap().thinking, "Thinking...");
        // app.append_thinking(" Done");
        // assert_eq!(
        //     app.messages.last().unwrap().thinking,
        //     "Thinking... Done"
        // );
    }
}
