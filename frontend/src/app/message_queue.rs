//! # 消息队列模块
//!
//! 提供消息队列的管理功能，包括添加、检索和限制消息数量。

use serde::{Deserialize, Serialize};

use super::state::{Author, Message};

/// 消息队列配置
#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct MessageQueueConfig {
    /// 最大保留消息数量
    pub max_messages: usize,
    /// 是否启用自动修剪
    pub enable_pruning: bool,
    /// 修剪时的保留数量
    pub prune_keep_count: usize,
}

impl Default for MessageQueueConfig {
    fn default() -> Self {
        Self {
            max_messages: 1000,
            enable_pruning: true,
            prune_keep_count: 100,
        }
    }
}

impl MessageQueueConfig {
    /// 创建新的配置
    pub fn new() -> Self {
        Self::default()
    }

    /// 设置最大消息数量
    pub fn with_max_messages(mut self, count: usize) -> Self {
        self.max_messages = count;
        self
    }

    /// 设置修剪保留数量
    pub fn with_prune_keep_count(mut self, count: usize) -> Self {
        self.prune_keep_count = count;
        self
    }

    /// 禁用自动修剪
    pub fn without_pruning(mut self) -> Self {
        self.enable_pruning = false;
        self
    }
}

/// 消息队列
///
/// 管理应用中的消息历史，支持添加、检索、过滤和自动修剪。
#[derive(Debug, Clone, Default, Deserialize, Serialize)]
pub struct MessageQueue {
    /// 消息列表
    messages: Vec<Message>,
    /// 配置
    config: MessageQueueConfig,
}

impl MessageQueue {
    /// 创建新的消息队列
    pub fn new() -> Self {
        Self::with_config(MessageQueueConfig::default())
    }

    /// 使用指定配置创建消息队列
    pub fn with_config(config: MessageQueueConfig) -> Self {
        Self {
            messages: Vec::new(),
            config,
        }
    }

    /// 添加消息到队列末尾
    pub fn push(&mut self, message: Message) {
        self.messages.push(message);
        self.maybe_prune();
    }

    /// 添加用户消息
    pub fn push_user(&mut self, content: String) {
        self.push(Message::user(content));
    }

    /// 添加助手消息
    pub fn push_assistant(&mut self, content: String) {
        self.push(Message::assistant(content));
    }

    /// 获取所有消息
    pub fn all(&self) -> &[Message] {
        &self.messages
    }

    /// 获取可变引用的所有消息
    pub fn all_mut(&mut self) -> &mut [Message] {
        &mut self.messages
    }

    /// 获取消息数量
    pub fn len(&self) -> usize {
        self.messages.len()
    }

    /// 检查是否为空
    pub fn is_empty(&self) -> bool {
        self.messages.is_empty()
    }

    /// 获取最后一条消息
    pub fn last(&self) -> Option<&Message> {
        self.messages.last()
    }

    /// 获取最后一条消息的可变引用
    pub fn last_mut(&mut self) -> Option<&mut Message> {
        self.messages.last_mut()
    }

    /// 获取指定索引的消息
    pub fn get(&self, index: usize) -> Option<&Message> {
        self.messages.get(index)
    }

    /// 获取指定索引消息的可变引用
    pub fn get_mut(&mut self, index: usize) -> Option<&mut Message> {
        self.messages.get_mut(index)
    }

    /// 清空所有消息
    pub fn clear(&mut self) {
        self.messages.clear();
    }

    /// 移除最后一条消息
    pub fn pop(&mut self) -> Option<Message> {
        self.messages.pop()
    }

    /// 根据作者筛选消息
    pub fn filter_by_author(&self, author: Author) -> Vec<&Message> {
        self.messages
            .iter()
            .filter(|m| m.author == author)
            .collect()
    }

    /// 获取所有用户消息
    pub fn user_messages(&self) -> Vec<&Message> {
        self.filter_by_author(Author::User)
    }

    /// 获取所有助手消息
    pub fn assistant_messages(&self) -> Vec<&Message> {
        self.filter_by_author(Author::Assistant)
    }

    /// 获取最近 N 条消息
    pub fn recent(&self, count: usize) -> &[Message] {
        let start = if self.messages.len() > count {
            self.messages.len() - count
        } else {
            0
        };
        &self.messages[start..]
    }

    /// 修剪消息队列，保留最近的 N 条
    pub fn prune(&mut self, keep_count: usize) {
        if self.messages.len() > keep_count {
            let remove_count = self.messages.len() - keep_count;
            self.messages.drain(0..remove_count);
        }
    }

    /// 根据配置自动修剪
    fn maybe_prune(&mut self) {
        if self.config.enable_pruning && self.messages.len() > self.config.max_messages {
            self.prune(self.config.prune_keep_count);
        }
    }

    /// 获取消息总数统计
    pub fn stats(&self) -> MessageQueueStats {
        let user_count = self
            .messages
            .iter()
            .filter(|m| m.author == Author::User)
            .count();
        let assistant_count = self.messages.len() - user_count;

        MessageQueueStats {
            total: self.messages.len(),
            user_count,
            assistant_count,
            completed_count: self.messages.iter().filter(|m| m.is_complete).count(),
        }
    }

    /// 追加内容到最后的助手消息
    pub fn append_to_last_assistant(&mut self, content: &str) {
        if let Some(msg) = self.last_mut() {
            if msg.author == Author::Assistant {
                msg.content.push_str(content);
            }
        }
    }

    /// 追加思考内容到最后的助手消息
    pub fn append_thinking_to_last_assistant(&mut self, content: &str) {
        if let Some(msg) = self.last_mut() {
            if msg.author == Author::Assistant {
                msg.thinking.push_str(content);
            }
        }
    }

    /// 标记最后一条消息为完成
    pub fn mark_last_complete(&mut self) {
        if let Some(msg) = self.last_mut() {
            msg.is_complete = true;
        }
    }

    /// 检查最后一条消息是否来自助手
    pub fn is_last_from_assistant(&self) -> bool {
        self.last()
            .map(|m| m.author == Author::Assistant)
            .unwrap_or(false)
    }

    /// 检查最后一条消息是否完成
    pub fn is_last_complete(&self) -> bool {
        self.last().map(|m| m.is_complete).unwrap_or(true)
    }
}

/// 消息队列统计信息
#[derive(Debug, Clone, Copy, Default, Deserialize, Serialize)]
pub struct MessageQueueStats {
    /// 总消息数
    pub total: usize,
    /// 用户消息数
    pub user_count: usize,
    /// 助手消息数
    pub assistant_count: usize,
    /// 已完成消息数
    pub completed_count: usize,
}

impl From<&MessageQueue> for Vec<Message> {
    fn from(queue: &MessageQueue) -> Self {
        queue.messages.clone()
    }
}

// ============================================================================
// 单元测试
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_queue_creation() {
        let queue = MessageQueue::new();
        assert!(queue.is_empty());
        assert_eq!(queue.len(), 0);
    }

    #[test]
    fn test_push_messages() {
        let mut queue = MessageQueue::new();
        queue.push_user("Hello".to_string());
        queue.push_assistant("Hi there".to_string());

        assert_eq!(queue.len(), 2);
        assert!(queue.is_last_from_assistant());
    }

    #[test]
    fn test_filter_by_author() {
        let mut queue = MessageQueue::new();
        queue.push_user("Hello".to_string());
        queue.push_assistant("Hi".to_string());
        queue.push_user("How are you?".to_string());

        assert_eq!(queue.user_messages().len(), 2);
        assert_eq!(queue.assistant_messages().len(), 1);
    }

    #[test]
    fn test_recent_messages() {
        let mut queue = MessageQueue::new();
        for i in 0..10 {
            queue.push_user(format!("Message {}", i));
        }

        assert_eq!(queue.recent(3).len(), 3);
        assert_eq!(queue.recent(3)[0].content, "Message 7");
    }

    #[test]
    fn test_prune() {
        let mut queue = MessageQueue::new();
        for i in 0..10 {
            queue.push_user(format!("Message {}", i));
        }

        queue.prune(5);
        assert_eq!(queue.len(), 5);
        assert_eq!(queue.messages[0].content, "Message 5");
    }

    #[test]
    fn test_auto_prune() {
        let config = MessageQueueConfig {
            max_messages: 5,
            enable_pruning: true,
            prune_keep_count: 3,
        };
        let mut queue = MessageQueue::with_config(config);

        for i in 0..10 {
            queue.push_user(format!("Message {}", i));
        }

        assert_eq!(queue.len(), 4);
        assert_eq!(queue.messages[0].content, "Message 6");
    }

    #[test]
    fn test_stats() {
        let mut queue = MessageQueue::new();
        queue.push_user("Hello".to_string());
        queue.push_assistant("Hi".to_string());
        queue.push_user("How are you?".to_string());

        let stats = queue.stats();
        assert_eq!(stats.total, 3);
        assert_eq!(stats.user_count, 2);
        assert_eq!(stats.assistant_count, 1);
    }

    #[test]
    fn test_append_to_last_assistant() {
        let mut queue = MessageQueue::new();
        queue.push_assistant("Hello".to_string());
        queue.append_to_last_assistant(" World");

        assert_eq!(queue.last().unwrap().content, "Hello World");
    }

    #[test]
    fn test_mark_complete() {
        let mut queue = MessageQueue::new();
        queue.push(Message::assistant_pending());
        assert!(!queue.is_last_complete());

        queue.mark_last_complete();
        assert!(queue.is_last_complete());
    }
}
