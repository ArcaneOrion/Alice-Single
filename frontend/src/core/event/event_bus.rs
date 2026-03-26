//! # 事件总线
//!
//! 提供事件的发送、接收和多路复用机制。

use std::sync::mpsc::{self, Receiver, RecvError, RecvTimeoutError, Sender, TryRecvError};
use std::time::Duration;

use super::types::AppEvent;

/// 事件总线 - 管理事件的生产者和消费者
#[derive(Debug)]
pub struct EventBus {
    /// 事件发送器
    sender: Sender<AppEvent>,
    /// 事件接收器
    receiver: Receiver<AppEvent>,
}

impl EventBus {
    /// 创建新的事件总线
    pub fn new() -> Self {
        let (sender, receiver) = mpsc::channel();
        Self { sender, receiver }
    }

    /// 获取发送器克隆
    pub fn sender(&self) -> Sender<AppEvent> {
        self.sender.clone()
    }

    /// 获取接收器引用
    pub fn receiver(&self) -> &Receiver<AppEvent> {
        &self.receiver
    }

    /// 发送事件
    pub fn send(&self, event: AppEvent) -> Result<(), mpsc::SendError<AppEvent>> {
        self.sender.send(event)
    }

    /// 尝试接收事件（非阻塞）
    pub fn try_recv(&self) -> Result<AppEvent, TryRecvError> {
        self.receiver.try_recv()
    }

    /// 接收事件（阻塞）
    pub fn recv(&self) -> Result<AppEvent, RecvError> {
        self.receiver.recv()
    }

    /// 带超时的接收事件
    pub fn recv_timeout(&self, timeout: Duration) -> Result<AppEvent, RecvTimeoutError> {
        self.receiver.recv_timeout(timeout)
    }

    /// 清空所有待处理事件
    pub fn drain(&self) {
        while self.try_recv().is_ok() {
            // 持续清空直到无事件
        }
    }

    /// 检查是否有待处理事件
    pub fn has_pending(&self) -> bool {
        self.receiver.try_recv().is_ok()
    }
}

impl Default for EventBus {
    fn default() -> Self {
        Self::new()
    }
}

/// 事件发送器句柄
///
/// 用于在需要发送事件但不持有完整 EventBus 的地方
#[derive(Debug, Clone)]
pub struct EventSender {
    sender: Sender<AppEvent>,
}

impl EventSender {
    /// 从 EventBus 创建发送器
    pub fn from_bus(bus: &EventBus) -> Self {
        Self {
            sender: bus.sender.clone(),
        }
    }

    /// 从原始 Sender 创建
    pub fn from_sender(sender: Sender<AppEvent>) -> Self {
        Self { sender }
    }

    /// 发送事件
    pub fn send(&self, event: AppEvent) -> Result<(), mpsc::SendError<AppEvent>> {
        self.sender.send(event)
    }

    /// 发送键盘事件
    pub fn send_key(
        &self,
        code: KeyCode,
        modifiers: KeyModifiers,
        is_release: bool,
    ) -> Result<(), mpsc::SendError<AppEvent>> {
        use super::types::{KeyboardEvent, AppEvent};
        self.send(AppEvent::Key(KeyboardEvent {
            code,
            modifiers,
            is_release,
        }))
    }

    /// 发送刻度事件
    pub fn send_tick(&self) -> Result<(), mpsc::SendError<AppEvent>> {
        self.send(AppEvent::Tick)
    }

    /// 发送退出事件
    pub fn send_quit(&self) -> Result<(), mpsc::SendError<AppEvent>> {
        self.send(AppEvent::Quit)
    }
}

// 重新导出类型
pub use super::types::{KeyCode, KeyModifiers};

#[cfg(test)]
mod tests {
    use super::*;
    use crate::core::event::types::{KeyboardEvent, MouseEvent, MouseEventKind};

    #[test]
    fn test_event_bus_send_recv() {
        let bus = EventBus::new();
        let event = AppEvent::Tick;

        bus.send(event.clone()).unwrap();
        let received = bus.recv().unwrap();

        assert_eq!(received, event);
    }

    #[test]
    fn test_event_bus_try_recv() {
        let bus = EventBus::new();

        // 空总线应返回错误
        assert!(matches!(bus.try_recv(), Err(TryRecvError::Empty)));

        bus.send(AppEvent::Tick).unwrap();
        assert!(bus.try_recv().is_ok());
        assert!(matches!(bus.try_recv(), Err(TryRecvError::Empty)));
    }

    #[test]
    fn test_event_bus_clone_sender() {
        let bus = EventBus::new();
        let sender = EventSender::from_bus(&bus);

        sender.send_tick().unwrap();
        assert!(matches!(bus.try_recv(), Ok(AppEvent::Tick)));
    }

    #[test]
    fn test_event_bus_drain() {
        let bus = EventBus::new();

        bus.send(AppEvent::Tick).unwrap();
        bus.send(AppEvent::Quit).unwrap();
        bus.send(AppEvent::Tick).unwrap();

        bus.drain();

        assert!(matches!(bus.try_recv(), Err(TryRecvError::Empty)));
    }
}
