"""智服通 - 会话记忆

滑动窗口多轮记忆：
- 每次追加 user + assistant 消息。
- 只保留最近 N 轮（默认 6 轮），防止上下文膨胀。
"""

from dataclasses import dataclass, field

from ..core.config import get_settings


@dataclass
class Memory:
    """进程内多轮记忆（以会话为粒度）。"""

    max_rounds: int = 6
    messages: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.max_rounds = get_settings().session_history_rounds

    def add(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})
        # 超出轮数则裁剪。messages 长度 = rounds * 2
        max_len = self.max_rounds * 2
        if len(self.messages) > max_len:
            self.messages = self.messages[-max_len:]

    def to_list(self) -> list[dict]:
        return list(self.messages)

    def clear(self) -> None:
        self.messages.clear()


# 全局记忆池（生产环境建议 Redis/DB 存储，演示用内存）
_memory_pool: dict[str, Memory] = {}


def get_memory(session_id: str) -> Memory:
    """获取指定会话的记忆对象。"""
    if session_id not in _memory_pool:
        _memory_pool[session_id] = Memory()
    return _memory_pool[session_id]


def delete_memory(session_id: str) -> None:
    _memory_pool.pop(session_id, None)
