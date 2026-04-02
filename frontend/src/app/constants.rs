//! # 应用常量定义模块
//!
//! 定义 TUI 应用中使用的各种常量。

// # 旋转指示器常量
//
// 用于显示加载状态的旋转动画字符序列。

/// 旋转指示器帧序列
///
/// 每个字符代表动画的一帧，按顺序循环显示。
pub const SPINNER_FRAMES: &[&str] = &["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"];

/// 旋转指示器帧数
pub const SPINNER_FRAME_COUNT: usize = SPINNER_FRAMES.len();

// # 定时器常量
//
// 控制定时器事件和动画更新频率。

/// 默认 tick 间隔（毫秒）
///
/// 控制动画更新频率和输入轮询间隔。
pub const DEFAULT_TICK_RATE_MS: u64 = 100;

/// 更快的 tick 间隔（毫秒）- 用于更流畅的动画
pub const FAST_TICK_RATE_MS: u64 = 50;

/// 较慢的 tick 间隔（毫秒）- 用于节省资源
pub const SLOW_TICK_RATE_MS: u64 = 200;

// # UI 布局常量
//
// 定义 TUI 各区域的大小和比例。

/// Header 区域高度（行数）
pub const HEADER_HEIGHT: u16 = 3;

/// Input 区域高度（行数）
pub const INPUT_HEIGHT: u16 = 3;

/// 聊天区默认宽度百分比（当侧边栏显示时）
pub const CHAT_WIDTH_PERCENTAGE_WHEN_SIDEBAR_SHOWN: u16 = 75;

/// 侧边栏默认宽度百分比
pub const SIDEBAR_WIDTH_PERCENTAGE: u16 = 25;

/// 聊天区宽度百分比（当侧边栏隐藏时）
pub const CHAT_WIDTH_PERCENTAGE_WHEN_SIDEBAR_HIDDEN: u16 = 100;

/// 最小聊天区宽度（字符数）
pub const MIN_CHAT_WIDTH: u16 = 20;

/// 最小侧边栏宽度（字符数）
pub const MIN_SIDEBAR_WIDTH: u16 = 15;

// # 滚动常量
//
// 控制滚动行为和边界。

/// 最大滚动偏移限制
///
/// 用于防止滚动偏移无限增长。
pub const MAX_SCROLL_OFFSET: usize = 9999;

/// 默认滚动步长（行数）
pub const DEFAULT_SCROLL_STEP: usize = 1;

/// Page Up/Down 滚动步长（行数）
pub const PAGE_SCROLL_STEP: usize = 10;

// # 消息常量
//
// 控制消息队列和显示相关限制。

/// 默认最大消息保留数量
pub const DEFAULT_MAX_MESSAGES: usize = 1000;

/// 自动修剪时的保留消息数量
pub const PRUNE_KEEP_MESSAGE_COUNT: usize = 100;

/// 单条消息最大长度（字符数）
pub const MAX_MESSAGE_LENGTH: usize = 100_000;

/// 消息内容截断长度（用于预览）
pub const MESSAGE_PREVIEW_LENGTH: usize = 100;

// # 颜色常量
//
// 虽然实际颜色由 ratatui 的 Color 枚举定义，
// 这里定义一些语义化的颜色名称映射。

/// 默认文本颜色
pub const COLOR_DEFAULT_TEXT: &str = "white";

/// 用户消息颜色
pub const COLOR_USER_MESSAGE: &str = "blue";

/// 助手消息颜色
pub const COLOR_ASSISTANT_MESSAGE: &str = "magenta";

/// 思考内容颜色
pub const COLOR_THINKING: &str = "gray";

/// 输入框文本颜色（就绪状态）
pub const COLOR_INPUT_READY: &str = "yellow";

/// 输入框文本颜色（忙碌状态）
pub const COLOR_INPUT_BUSY: &str = "darkgray";

// # 状态文本常量
//
// 各状态对应的显示文本。

/// 初始欢迎消息
pub const MSG_WELCOME_INIT: &str = "你好！我是你的智能助手 Alice。系统正在初始化...";

/// 就绪状态欢迎消息
pub const MSG_WELCOME_READY: &str = "你好！我是你的智能助手 Alice。我已经准备好了！";

/// 后端连接错误消息
pub const ERROR_BACKEND_CONNECTION: &str = "错误: 无法连接到后端引擎。";

/// 处理中占位文本
pub const MSG_PROCESSING_PLACEHOLDER: &str = "正在处理中...";

/// 暂无思考内容提示
pub const MSG_NO_THINKING: &str = "暂无思考过程...";

// # 输入提示文本常量

/// 输入框标题（就绪状态）
pub const INPUT_TITLE_READY: &str = " 输入消息 (Enter 发送, Ctrl+C 退出) ";

/// 输入框标题（等待状态）
pub const INPUT_TITLE_WAITING: &str = " 请等待 Alice 回复... ";

/// 侧边栏切换提示（隐藏状态）
pub const SIDEBAR_HINT_HIDDEN: &str = "隐藏思考过程 (Ctrl+O 显示)";

/// 侧边栏切换提示（显示状态）
pub const SIDEBAR_HINT_SHOWN: &str = "显示思考过程 (Ctrl+O 隐藏)";

// # 状态文本模板

/// 标题文本
pub const HEADER_TITLE: &str = " ALICE ASSISTANT ";

/// 状态标签前缀
pub const STATUS_LABEL: &str = " | 状态:";

/// 对话历史标题
pub const CHAT_HISTORY_TITLE: &str = " 对话历史 ";

/// 思考侧边栏标题
pub const THINKING_TITLE_BASE: &str = " 💭 ";

// # 作者显示名称

/// 用户消息前缀
pub const AUTHOR_USER_PREFIX: &str = " 你: ";

/// 助手消息前缀
pub const AUTHOR_ASSISTANT_PREFIX: &str = " Alice: ";

// # 单元测试

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_spinner_constants() {
        assert_eq!(SPINNER_FRAME_COUNT, 10);
        assert_eq!(SPINNER_FRAMES.len(), SPINNER_FRAME_COUNT);
    }

    #[test]
    #[allow(clippy::assertions_on_constants)]
    fn test_tick_rate_values() {
        assert!(DEFAULT_TICK_RATE_MS > 0);
        assert!(FAST_TICK_RATE_MS < DEFAULT_TICK_RATE_MS);
        assert!(SLOW_TICK_RATE_MS > DEFAULT_TICK_RATE_MS);
    }

    #[test]
    fn test_layout_heights() {
        assert_eq!(HEADER_HEIGHT + INPUT_HEIGHT, 6);
    }

    #[test]
    fn test_width_percentages_sum() {
        assert_eq!(
            CHAT_WIDTH_PERCENTAGE_WHEN_SIDEBAR_SHOWN + SIDEBAR_WIDTH_PERCENTAGE,
            100
        );
        assert_eq!(CHAT_WIDTH_PERCENTAGE_WHEN_SIDEBAR_HIDDEN, 100);
    }

    #[test]
    #[allow(clippy::assertions_on_constants)]
    fn test_message_limits() {
        assert!(DEFAULT_MAX_MESSAGES > PRUNE_KEEP_MESSAGE_COUNT);
        assert!(MAX_MESSAGE_LENGTH > MESSAGE_PREVIEW_LENGTH);
    }

    #[test]
    fn test_message_templates() {
        assert!(!MSG_WELCOME_INIT.is_empty());
        assert!(!MSG_WELCOME_READY.is_empty());
        assert!(!ERROR_BACKEND_CONNECTION.is_empty());
    }

    #[test]
    fn test_author_prefixes() {
        assert!(!AUTHOR_USER_PREFIX.is_empty());
        assert!(!AUTHOR_ASSISTANT_PREFIX.is_empty());
        assert_ne!(AUTHOR_USER_PREFIX, AUTHOR_ASSISTANT_PREFIX);
    }
}
