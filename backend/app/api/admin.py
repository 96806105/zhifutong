"""智服通 - 管理 API（需鉴权）

- GET /api/admin/tickets   工单列表
- GET /api/admin/sessions  会话列表
- GET /api/admin/stats     系统统计
"""

from fastapi import APIRouter, Query

from ..dialog import storage
from ..rag.indexer import index_stats

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/tickets")
async def tickets(limit: int = Query(50, ge=1, le=200)):
    return {"tickets": storage.list_tickets(limit=limit)}


@router.get("/sessions")
async def sessions(limit: int = Query(50, ge=1, le=200)):
    return {"sessions": storage.list_sessions(limit=limit)}


@router.get("/stats")
async def stats():
    return {"kb": index_stats(), "sessions": len(storage.list_sessions(limit=1000))}
