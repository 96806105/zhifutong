"""智服通 - 对话服务编排

整合意图识别、转人工、RAG 链、记忆与持久化，
为 API 层提供统一的对话处理逻辑。
"""

from ..core.llm import get_llm
from ..core.logger import get_logger
from ..rag import chain
from ..rag.retriever import Hit
from . import intent as intent_mod
from . import storage
from .memory import get_memory
from .transfer import get_evaluator

logger = get_logger("dialog_service")

# 兜底话术（检索不到 / 低置信度）不会再调用 LLM 造幻觉
FALLBACK_REPLY = (
    "很抱歉，我在企业 IT 知识库中暂时没有找到与您问题完全匹配的资料。\n"
    "您可以补充更具体的描述（如报错信息、软件名称），或点击「转人工」让技术支持为您处理。"
)


def _greeting_reply() -> str:
    return (
        "您好！我是「智服通」，企业 IT 技术支持智能助手。😊\n"
        "您可以向我咨询账号密码、网络连接、软件安装、硬件故障、安全权限等问题，"
        "我会基于企业知识库为您解答。请问有什么可以帮您？"
    )


def process_message(
    session_id: str,
    message: str,
    *,
    category: str | None = None,
) -> dict:
    """处理单条用户消息（非流式）。返回结构化结果。"""
    storage.get_session(session_id)  # 确认会话存在
    memory = get_memory(session_id)
    text = (message or "").strip()

    if not text:
        return {"reply": "请输入您的问题。", "action": "none", "confidence": 1.0}

    intent = intent_mod.classify(text)

    # 1) 问候
    if intent["intent"] == "greeting":
        reply = _greeting_reply()
        _persist_pair(
            session_id, memory, text, reply, action="greeting", confidence=1.0
        )
        return {"reply": reply, "action": "greeting", "confidence": 1.0}

    # 2) 明确要求转人工 / 敏感操作 → 立即转人工
    if intent["intent"] == "transfer_human" or intent["is_sensitive"]:
        return _do_transfer(session_id, memory, text, reason=intent["reason"])

    # 3) 检索 + 生成
    history = memory.to_list()
    result = chain.run_chain(text, history=history, category=category)

    hits: list[Hit] = result.hits

    # 4) 转人工决策
    evaluator = get_evaluator()
    should_transfer, reason = evaluator.should_transfer(
        session_id,
        result.confidence,
        explicit=False,
        negative=intent["is_negative"],
        sensitive=intent["is_sensitive"],
    )

    if should_transfer:
        return _do_transfer(session_id, memory, text, reason=reason)

    # 5) 检索完全未命中 → 兜底话术（不编造）
    if not hits:
        _persist_pair(
            session_id,
            memory,
            text,
            FALLBACK_REPLY,
            action="fallback",
            confidence=result.confidence,
        )
        return {
            "reply": FALLBACK_REPLY,
            "action": "fallback",
            "confidence": result.confidence,
            "sources": [],
        }

    # 6) 正常回答
    _persist_pair(
        session_id,
        memory,
        text,
        result.reply,
        action="none",
        confidence=result.confidence,
        sources=result.sources,
    )
    return {
        "reply": result.reply,
        "action": "none",
        "confidence": round(result.confidence, 3),
        "sources": result.sources,
    }


def _do_transfer(session_id: str, memory, user_text: str, reason: str) -> dict:
    """执行转人工：生成工单 + 记录。"""
    ticket_id = storage.create_ticket(session_id, reason=reason)
    storage.set_session_status(session_id, "transferred")
    reply = (
        "已为您转接人工客服。我们的技术支持人员会尽快处理您的问题。\n"
        f"您的工单号为：**{ticket_id}**，请妥善保存以便后续查询。"
    )
    _persist_pair(
        session_id, memory, user_text, reply, action="transfer", confidence=0.0
    )
    logger.info("session %s %s", session_id, reason)
    return {
        "reply": reply,
        "action": "transfer",
        "ticket_id": ticket_id,
        "confidence": 0.0,
    }


def _persist_pair(
    session_id: str,
    memory,
    user_text: str,
    reply: str,
    *,
    action: str = "none",
    confidence: float | None = None,
    sources: list[dict] | None = None,
) -> None:
    """持久化一条 user + assistant 消息对，并写入记忆。"""
    memory.add("user", user_text)
    memory.add("assistant", reply)
    storage.add_message(session_id, "user", user_text)
    storage.add_message(
        session_id,
        "assistant",
        reply,
        sources=sources,
        action=action,
        confidence=confidence,
    )


def stream_process(
    session_id: str,
    message: str,
    *,
    category: str | None = None,
):
    """流式处理用户消息，yield SSE 事件（生成器）。

    yield 结构: {"type": "delta", "data": str} / {"type": "meta", "data": dict}
    """
    storage.get_session(session_id)
    memory = get_memory(session_id)
    text = (message or "").strip()

    if not text:
        yield {"type": "meta", "data": {"reply": "请输入您的问题。", "action": "none"}}
        return

    intent = intent_mod.classify(text)

    # 问候
    if intent["intent"] == "greeting":
        reply = _greeting_reply()
        _persist_pair(
            session_id, memory, text, reply, action="greeting", confidence=1.0
        )
        yield {"type": "meta", "data": {"reply": reply, "action": "greeting"}}
        return

    # 明确转人工 / 敏感操作
    if intent["intent"] == "transfer_human" or intent["is_sensitive"]:
        result = _do_transfer(session_id, memory, text, reason=intent["reason"])
        yield {"type": "meta", "data": result}
        return

    # 检索
    hits = chain.stream_hits(text, history=memory.to_list(), category=category)

    # 未命中 → 兜底
    if not hits:
        _persist_pair(
            session_id,
            memory,
            text,
            FALLBACK_REPLY,
            action="fallback",
            confidence=0.0,
        )
        yield {
            "type": "meta",
            "data": {"reply": FALLBACK_REPLY, "action": "fallback", "sources": []},
        }
        return

    messages = chain.stream_context(text, hits, history=memory.to_list())
    llm = get_llm()

    full_reply_parts: list[str] = []
    for delta in llm.stream_chat(messages):
        full_reply_parts.append(delta)
        yield {"type": "delta", "data": delta}

    reply = "".join(full_reply_parts).strip()
    from ..rag.chain import _parse_confidence, _strip_confidence_json

    confidence = max(_parse_confidence(reply), hits[0].score)
    reply = _strip_confidence_json(reply)

    sources = [
        {
            "category": h.metadata.get("category", ""),
            "source": h.metadata.get("source", ""),
            "score": round(h.score, 4),
        }
        for h in hits[:3]
    ]

    # 转人工决策（流式结束后评估）
    evaluator = get_evaluator()
    should_transfer, reason = evaluator.should_transfer(
        session_id,
        confidence,
        explicit=False,
        negative=intent["is_negative"],
        sensitive=intent["is_sensitive"],
    )
    if should_transfer:
        transfer_result = _do_transfer(session_id, memory, text, reason=reason)
        yield {"type": "meta", "data": transfer_result}
        return

    _persist_pair(
        session_id,
        memory,
        text,
        reply,
        action="none",
        confidence=confidence,
        sources=sources,
    )
    yield {
        "type": "meta",
        "data": {
            "reply": reply,
            "action": "none",
            "confidence": round(confidence, 3),
            "sources": sources,
        },
    }
