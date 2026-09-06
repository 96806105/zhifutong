"""智服通 - 意图识别

基于关键词 + 规则判断用户意图：
- transfer_human: 要求转人工
- fallback_need: 低置信度需要兜底/转人工
- query: 正常 IT 问题
- greeting: 问候闲聊
"""

from ..core.logger import get_logger

logger = get_logger("intent")

TRANSFER_KEYWORDS = [
    "转人工",
    "人工客服",
    "找人工",
    "请人工",
    "真人",
    "联系客服",
    "叫客服",
    "人工服务",
    "客服人员",
    "找个人",
    "快人工",
    "转接",
    "接人工",
    "human",
    "agent please",
    "人工处理",
]

NEGATIVE_EMOTION_KEYWORDS = [
    "投诉",
    "很生气",
    "太慢了",
    "垃圾",
    "差评",
    "废物",
    "忍不了",
    "无语",
    "失望",
    "气死",
    "坑人",
    "骗人",
    "糟糕",
    "崩溃",
]

SENSITIVE_KEYWORDS = [
    "退款",
    "赔偿",
    "高权限",
    "批量导出",
    "删除数据",
    "违规",
    "消除记录",
]

GREETING_KEYWORDS = [
    "你好",
    "您好",
    " hi",
    "hello",
    "在吗",
    "早上好",
    "下午好",
    "晚上好",
]


def classify(text: str) -> dict:
    """意图分类，返回 {intent, reason, is_transfer, is_negative, is_sensitive}。"""
    text_lower = text.lower()

    for kw in TRANSFER_KEYWORDS:
        if kw.lower() in text_lower:
            logger.info("intent=transfer_human kw=%s", kw)
            return {
                "intent": "transfer_human",
                "reason": f"用户明确要求转人工（关键词: {kw}）",
                "is_transfer": True,
                "is_negative": False,
                "is_sensitive": False,
            }

    is_negative = any(kw in text for kw in NEGATIVE_EMOTION_KEYWORDS)
    is_sensitive = any(kw in text for kw in SENSITIVE_KEYWORDS)

    if is_negative or is_sensitive:
        if is_negative:
            logger.info("intent=negative emotion detected")
            return {
                "intent": "negative",
                "reason": "检测到负面情绪关键词",
                "is_transfer": False,
                "is_negative": True,
                "is_sensitive": is_sensitive,
            }
        logger.info("intent=sensitive operation detected")
        return {
            "intent": "sensitive",
            "reason": "检测到敏感操作关键词",
            "is_transfer": False,
            "is_negative": False,
            "is_sensitive": True,
        }

    if any(kw in text_lower for kw in GREETING_KEYWORDS):
        return {
            "intent": "greeting",
            "reason": "问候",
            "is_transfer": False,
            "is_negative": False,
            "is_sensitive": False,
        }

    return {
        "intent": "query",
        "reason": "普通问题",
        "is_transfer": False,
        "is_negative": False,
        "is_sensitive": False,
    }
