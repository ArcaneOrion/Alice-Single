//! # 应用主屏幕渲染
//!
//! 将 App 状态装配到现有 UI 组件，而不是在 `main.rs` 中直接渲染占位内容。

use std::mem;

use ratatui::{
    Frame,
    layout::{Constraint, Direction, Layout, Rect},
};

use crate::{
    app::{
        constants::{
            CHAT_WIDTH_PERCENTAGE_WHEN_SIDEBAR_HIDDEN, CHAT_WIDTH_PERCENTAGE_WHEN_SIDEBAR_SHOWN,
            HEADER_HEIGHT, INPUT_HEIGHT, SIDEBAR_WIDTH_PERCENTAGE,
        },
        state::{
            AgentStatus as AppAgentStatus, App, AreaBounds, Author as AppAuthor,
            Message as AppMessage,
        },
    },
    ui::component::{
        AgentStatus as HeaderAgentStatus, Author as ChatAuthor, ChatViewConfig, ChatViewState,
        HeaderConfig, InputBoxConfig, Message as ChatMessage, SidebarConfig, render_chat_view,
        render_header, render_input_box, render_sidebar,
    },
};

struct AppLayout {
    header_area: Rect,
    chat_area: Rect,
    sidebar_area: Rect,
    input_area: Rect,
}

/// 渲染完整应用界面，并同步更新 App 内的布局/滚动状态。
pub fn render_app(f: &mut Frame, app: &mut App) {
    let layout = build_layout(f.area(), app.show_thinking);
    app.area_bounds = AreaBounds {
        chat_area: layout.chat_area,
        sidebar_area: layout.sidebar_area,
        input_area: layout.input_area,
    };

    render_header(
        f,
        layout.header_area,
        &HeaderConfig {
            status: map_status(app.status),
            spinner_index: app.spinner_index,
            show_thinking: app.show_thinking,
            total_tokens: app.tokens.total,
            prompt_tokens: app.tokens.prompt,
            completion_tokens: app.tokens.completion,
        },
    );

    let messages = map_messages(&app.messages);
    let mut chat_config = ChatViewConfig {
        scroll_offset: app.chat_scroll.offset,
        auto_scroll: app.chat_scroll.auto_scroll,
        spinner_index: app.spinner_index,
    };
    let mut chat_state = ChatViewState {
        list_state: mem::take(&mut app.list_state),
    };
    render_chat_view(
        f,
        layout.chat_area,
        &messages,
        &mut chat_config,
        &mut chat_state,
    );
    app.chat_scroll.offset = chat_config.scroll_offset;
    app.chat_scroll.auto_scroll = chat_config.auto_scroll;
    app.list_state = chat_state.list_state;

    if app.show_thinking {
        let mut sidebar_config = SidebarConfig {
            scroll_offset: app.thinking_scroll.offset,
            auto_scroll: app.thinking_scroll.auto_scroll,
            spinner_index: app.spinner_index,
            is_thinking: app.status.is_processing(),
        };
        let thinking_content = latest_thinking_content(&app.messages);
        render_sidebar(
            f,
            layout.sidebar_area,
            &thinking_content,
            &mut sidebar_config,
        );
        app.thinking_scroll.offset = sidebar_config.scroll_offset;
        app.thinking_scroll.auto_scroll = sidebar_config.auto_scroll;
    }

    render_input_box(
        f,
        layout.input_area,
        &app.input,
        &InputBoxConfig {
            enabled: app.status.can_accept_input(),
            ..InputBoxConfig::default()
        },
    );
}

fn build_layout(area: Rect, show_thinking: bool) -> AppLayout {
    let vertical = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(HEADER_HEIGHT),
            Constraint::Min(1),
            Constraint::Length(INPUT_HEIGHT),
        ])
        .split(area);

    let main = if show_thinking {
        Layout::default()
            .direction(Direction::Horizontal)
            .constraints([
                Constraint::Percentage(CHAT_WIDTH_PERCENTAGE_WHEN_SIDEBAR_SHOWN),
                Constraint::Percentage(SIDEBAR_WIDTH_PERCENTAGE),
            ])
            .split(vertical[1])
    } else {
        Layout::default()
            .direction(Direction::Horizontal)
            .constraints([
                Constraint::Percentage(CHAT_WIDTH_PERCENTAGE_WHEN_SIDEBAR_HIDDEN),
                Constraint::Percentage(0),
            ])
            .split(vertical[1])
    };

    AppLayout {
        header_area: vertical[0],
        chat_area: main[0],
        sidebar_area: if show_thinking {
            main[1]
        } else {
            Rect::default()
        },
        input_area: vertical[2],
    }
}

fn map_status(status: AppAgentStatus) -> HeaderAgentStatus {
    match status {
        AppAgentStatus::Starting => HeaderAgentStatus::Starting,
        AppAgentStatus::Idle => HeaderAgentStatus::Idle,
        AppAgentStatus::Thinking => HeaderAgentStatus::Thinking,
        AppAgentStatus::Responding => HeaderAgentStatus::Responding,
        AppAgentStatus::ExecutingTool => HeaderAgentStatus::ExecutingTool,
    }
}

fn map_messages(messages: &[AppMessage]) -> Vec<ChatMessage> {
    messages
        .iter()
        .map(|message| ChatMessage {
            author: match message.author {
                AppAuthor::User => ChatAuthor::User,
                AppAuthor::Assistant => ChatAuthor::Assistant,
            },
            thinking: message.thinking.clone(),
            content: message.content.clone(),
            is_complete: message.is_complete,
        })
        .collect()
}

fn latest_thinking_content(messages: &[AppMessage]) -> String {
    messages
        .iter()
        .rev()
        .find(|message| matches!(message.author, AppAuthor::Assistant))
        .map(|message| message.thinking.clone())
        .unwrap_or_default()
}

#[cfg(test)]
mod tests {
    use std::sync::mpsc;

    use ratatui::{Terminal, backend::TestBackend};

    use super::*;
    use crate::bridge::client::BridgeClient;

    fn create_app() -> App {
        let (_msg_tx, msg_rx) = mpsc::channel();
        let (_err_tx, err_rx) = mpsc::channel();
        let bridge_client = BridgeClient::with_test_channels(msg_rx, err_rx).unwrap();
        App::new(bridge_client)
    }

    fn buffer_text(terminal: &Terminal<TestBackend>) -> String {
        let buffer = terminal.backend().buffer();
        let area = buffer.area();
        let mut output = String::new();

        for y in 0..area.height {
            for x in 0..area.width {
                output.push_str(buffer[(x, y)].symbol());
            }
            output.push('\n');
        }

        output
    }

    fn normalize_terminal_text(text: &str) -> String {
        text.chars().filter(|ch| !ch.is_whitespace()).collect()
    }

    #[test]
    fn test_render_app_uses_real_components_instead_of_placeholder() {
        let backend = TestBackend::new(80, 24);
        let mut terminal = Terminal::new(backend).unwrap();
        let mut app = create_app();
        app.handle_ready();
        app.input = "你好".into();

        terminal.draw(|f| render_app(f, &mut app)).unwrap();

        let text = buffer_text(&terminal);
        let normalized = normalize_terminal_text(&text);
        assert!(normalized.contains("ALICEASSISTANT"));
        assert!(normalized.contains("对话历史"));
        assert!(normalized.contains("输入消息"));
        assert!(!normalized.contains("UI组件正在迁移中"));
    }

    #[test]
    fn test_render_app_updates_area_bounds_with_sidebar() {
        let backend = TestBackend::new(100, 30);
        let mut terminal = Terminal::new(backend).unwrap();
        let mut app = create_app();
        app.show_thinking = true;
        app.messages.push(AppMessage::assistant_pending());
        app.append_thinking("分析用户请求");

        terminal.draw(|f| render_app(f, &mut app)).unwrap();

        assert!(app.area_bounds.chat_area.width > 0);
        assert!(app.area_bounds.sidebar_area.width > 0);
        assert!(app.area_bounds.input_area.height > 0);

        let text = buffer_text(&terminal);
        let normalized = normalize_terminal_text(&text);
        assert!(normalized.contains("分析用户请求"));
    }

    #[test]
    fn test_latest_thinking_content_clears_for_new_pending_assistant_message() {
        let messages = vec![
            AppMessage {
                author: AppAuthor::Assistant,
                thinking: "上一轮思考".into(),
                content: "上一轮回复".into(),
                is_complete: true,
            },
            AppMessage::user("新的问题".into()),
            AppMessage::assistant_pending(),
        ];

        assert_eq!(latest_thinking_content(&messages), "");
    }
}
