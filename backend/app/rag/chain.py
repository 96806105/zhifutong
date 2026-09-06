"""智服通 - RAG 链编排

组合 System Prompt + 多轮历史 + 检索上下文 → 调用 LLM → 返回答案与引用。

设计要点：
- 强约束 LLM 仅基于知识库回答，避免幻觉。
- 返回检索来源（sources）供前端展示。
- 通过 max 检索分数近似置信度，用于转人工/兜底判断。
"""

import json
from dataclasses import dataclass, field

from ..core.llm import get_llm
from ..core.logger import get_logger
from .retriever import Hit, retrieve

logger = get_logger("chain")

SYSTEM_PROMPT = """你是一名专业的企业 IT 技术支持客服机器人，名为「智服通」。
请严格按照以下规则回答：

1. 只能基于「参考知识库」提供的内容回答，不要编造或猜测。
2. 如果知识库内容与问题相关，请清晰、有条理地给出解决步骤。
3. 如果知识库中没有相关信息，请明确告知："我暂时没有找到关于该问题的资料，建议你转人工或提交 IT 工单。"不要试图编造答案。
4. 回答使用简体中文，语气专业、友好、简洁。
5. 必要时分步骤说明，便于用户操作。
6. 仅在回复的末尾以 JSON 格式输出一个置信度字段，格式为：{{"confidence": 0.8}}，
   表示你对本次回答的信心（0-1）。不要解释这个 JSON。

参考知识库：
{context}
"""


@dataclass
class ChainResult:
    """RAG 链输出。"""

    reply: str
    sources: list[dict] = field(default_factory=list)
    confidence: float = 0.0
    hits: list[Hit] = field(default_factory=list)


def _format_hits(hits: list[Hit]) -> str:
    """将检索命中拼成知识库上下文文本。"""
    if not hits:
        return "(无)"
    parts = [f"### 参考片段 {i + 1}\n{h.content[:800]}" for i, h in enumerate(hits)]
    return "\n\n".join(parts)


def _parse_confidence(reply: str) -> float:
    """从回答末尾解析置信度 JSON，失败则返回 0.5 默认。"""
    for line in reversed(reply.strip().splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                data = json.loads(line)
                conf = float(data.get("confidence", 0.5))
                return max(0.0, min(1.0, conf))
            except (json.JSONDecodeError, ValueError, TypeError):
                continue
    return 0.5


def _strip_confidence_json(reply: str) -> str:
    """去掉回答末尾的置信度 JSON 行。"""
    lines = reply.strip().splitlines()
    if lines and lines[-1].strip().startswith("{") and lines[-1].strip().endswith("}"):
        try:
            json.loads(lines[-1].strip())
            return "\n".join(lines[:-1]).strip()
        except json.JSONDecodeError:
            pass
    return reply.strip()


def run_chain(
    query: str,
    history: list[dict] | None = None,
    category: str | None = None,
) -> ChainResult:
    """执行 RAG 问答链（非流式）。

    Args:
        query: 用户问题。
        history: 会话历史（[{role, content}]）。
        category: 分类过滤。
    """
    history = history or []
    hits = retrieve(query, category=category)

    if not hits:
        # 检索不到：返回兜底，不调用 LLM（节省成本并避免编造）
        logger.warning("no hit for query, q=%s", query[:50])
        result = ChainResult(
            reply=(
                "很抱歉，我在企业 IT 知识库中暂时没有找到与您问题相关的资料。\n"
                "建议您补充更多细节，或点击「转人工」让技术支持为您处理。"
            ),
            confidence=0.1,
        )
        return result

    # 近似置信度 = 最高检索分数（后续可结合 LLM 自评）
    max_score = hits[0].score
    context = _format_hits(hits)

    history_block = ""
    if history:
        lines = [
            f"{'用户' if m['role'] == 'user' else '助手'}: {m['content']}"
            for m in history[-6:]
        ]
        history_block = (
            "以下是本次会话的历史对话（新问题请结合历史理解）：\n"
            + "\n".join(lines)
            + "\n"
        )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT.format(context=context)},
    ]
    if history_block:
        messages.append({"role": "user", "content": history_block})
    messages.append({"role": "user", "content": f"[用户问题]\n{query}"})

    llm = get_llm()
    return _full_response(llm, messages, hits, max_score)


def stream_hits(
    query: str,
    history: list[dict] | None = None,
    category: str | None = None,
) -> list[Hit]:
    """仅检索，返回命中（供流式流程预检）。"""
    return retrieve(query, category=category)


def stream_context(
    query: str,
    hits: list[Hit],
    history: list[dict] | None = None,
) -> list[dict]:
    """构造流式调用的 messages（复用检索结果，避免重复检索）。"""
    history = history or []
    context = _format_hits(hits)
    history_block = ""
    if history:
        lines = [
            f"{'用户' if m['role'] == 'user' else '助手'}: {m['content']}"
            for m in history[-6:]
        ]
        history_block = (
            "以下是本次会话的历史对话（新问题请结合历史理解）：\n"
            + "\n".join(lines)
            + "\n"
        )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT.format(context=context)},
    ]
    if history_block:
        messages.append({"role": "user", "content": history_block})
    messages.append({"role": "user", "content": f"[用户问题]\n{query}"})
    return messages


def _full_response(llm, messages, hits, max_score) -> ChainResult:
    reply = llm.chat(messages)
    confidence = max(_parse_confidence(reply), max_score)
    reply = _strip_confidence_json(reply)

    sources = [
        {
            "category": h.metadata.get("category", ""),
            "source": h.metadata.get("source", ""),
            "score": round(h.score, 4),
        }
        for h in hits[:3]
    ]
    logger.info(
        "chain done: conf=%.2f sources=%d reply_len=%d",
        confidence,
        len(sources),
        len(reply),
    )
    return ChainResult(reply=reply, sources=sources, confidence=confidence, hits=hits)
