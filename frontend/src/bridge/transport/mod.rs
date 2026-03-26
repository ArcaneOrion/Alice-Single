//! # 传输层抽象
//!
//! 定义与 Python 后端进程的底层通信接口。

pub mod stdio_transport;

pub use stdio_transport::{StdioTransport, StdioWriter};
