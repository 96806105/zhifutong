"""智服通 - 历史 / 会话 API"""

from fastapi import APIRouter, Query
from pydantic import BaseModel

from ..core.logger import get_logger
from ..dialog import storage

logger = get_logger("api.history")
router = APIRouter(prefix="/api", tags=["history"])


class NewSessionRequest(BaseModel):
    user_name: str | None = None


class NewSessionResponse(BaseModel):
    session_id: str


@router.post("/session", response_model=NewSessionResponse)
async def new_session(req: NewSessionRequest | None = None):
    """创建新会话。"""
    user_name = req.user_name if req else None
    session_id = storage.create_session(user_name=user_name)
    return NewSessionResponse(session_id=session_id)


@router.get("/history")
async def history(
    session_id: str = Query(..., description="会话ID"),
):
    """获取指定会话的历史消息（不含 system，含消息项）。"""
    messages = storage.get_session_messages(session_id)
    return {"session_id": session_id, "messages": messages}


@router.get("/sessions")
async def sessions(limit: int = Query(50, ge=1, le=200)):
    """列出最近会话。"""
    return {"sessions": storage.list_sessions(limit=limit)}
