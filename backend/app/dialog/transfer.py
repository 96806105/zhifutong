"""智服通 - 转人工决策引擎

综合判断是否转人工：
1. 用户明确要求。
2. 连续多次低置信度回答（默认 3 次）。
3. 负面情绪 / 敏感操作。

为每次会话维护失败计数，阈值可配置。
"""

from ..core.config import get_settings
from ..core.logger import get_logger

logger = get_logger("transfer")


class TransferEvaluator:
    """转人工评估器（按会话维护低置信度计数）。"""

    def __init__(self) -> None:
        self._fail_counts: dict[str, int] = {}
        self._threshold = get_settings().transfer_fail_threshold

    def fail_count(self, session_id: str) -> int:
        return self._fail_counts.get(session_id, 0)

    def record_result(self, session_id: str, confidence: float) -> None:
        """根据单轮回答置信度更新失败计数。"""
        # 低置信度视为一次失败
        if confidence < 0.4:
            self._fail_counts[session_id] = self._fail_counts.get(session_id, 0) + 1
            logger.debug(
                "session %s fail count -> %d", session_id, self._fail_counts[session_id]
            )
        else:
            # 回答良好则重置失败计数
            self._fail_counts[session_id] = 0

    def should_transfer(
        self,
        session_id: str,
        confidence: float,
        *,
        explicit: bool = False,
        negative: bool = False,
        sensitive: bool = False,
    ) -> tuple[bool, str]:
        """返回 (是否转人工, 原因)。"""
        # 明确要求
        if explicit:
            return True, "用户明确要求转人工"
        # 敏感操作直接转人工
        if sensitive:
            return True, "涉及敏感操作，需人工受理"
        # 负面情绪提供建议
        if negative:
            return True, "检测到负面情绪，建议人工介入"

        # 更新当前轮失败计数（此刻 confidence 属于本轮结果）
        self.record_result(session_id, confidence)
        if self.fail_count(session_id) >= self._threshold:
            logger.info(
                "session %s transferred: fail_count=%d >= %d",
                session_id,
                self.fail_count(session_id),
                self._threshold,
            )
            return True, f"连续 {self._threshold} 次未能解决，转为人工"

        return False, ""


_transfer_evaluator: TransferEvaluator | None = None


def get_evaluator() -> TransferEvaluator:
    global _transfer_evaluator
    if _transfer_evaluator is None:
        _transfer_evaluator = TransferEvaluator()
    return _transfer_evaluator
