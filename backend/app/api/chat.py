"""智服通 - 对话 API

- POST /api/chat        非流式问答
- POST /api/chat/stream SSE 流式问答
"""

import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..core.logger import get_logger
from ..dialog import service, storage

logger = get_logger("api.chat")
router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    session_id: str | None = Field(None, description="会话ID，为空则创建新会话")
    message: str = Field(..., min_length=1, description="用户消息")
    category: str | None = Field(None, description="知识库分类过滤")


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    action: str
    confidence: float | None = None
    sources: list[dict] = Field(default_factory=list)
    ticket_id: str | None = None


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """非流式问答。"""
    # 会话不存在则创建
    session_id = req.session_id
    if not session_id or not storage.get_session(session_id):
        session_id = storage.create_session()

    result = service.process_message(session_id, req.message, category=req.category)
    logger.info(
        "chat s=%s action=%s conf=%s",
        session_id,
        result["action"],
        result.get("confidence"),
    )
    return ChatResponse(
        session_id=session_id,
        reply=result["reply"],
        action=result["action"],
        confidence=result.get("confidence"),
        sources=result.get("sources", []),
        ticket_id=result.get("ticket_id"),
    )


@router.post("/chat/stream")
async def chat_stream(req: ChatRequest, request: Request):
    """流式问答（SSE）。"""
    session_id = req.session_id
    if not session_id or not storage.get_session(session_id):
        session_id = storage.create_session()

    async def event_stream():
        # 前置：发一个 session 事件
        yield _sse({"type": "session", "data": {"session_id": session_id}})
        for event in service.stream_process(
            session_id, req.message, category=req.category
        ):
            if await request.is_disconnected():
                break
            yield _sse(event)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
