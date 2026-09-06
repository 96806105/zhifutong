"""智服通 - 知识库 API

- POST /api/kb/rebuild   全量重建索引
- GET  /api/kb/stats     索引统计
"""

from fastapi import APIRouter

from ..core.logger import get_logger
from ..rag.indexer import index_stats, rebuild_index

logger = get_logger("api.kb")
router = APIRouter(prefix="/api/kb", tags=["kb"])


@router.post("/rebuild")
async def rebuild():
    """全量重建知识库索引。"""
    result = rebuild_index()
    result["message"] = (
        f"知识库重建完成：{result['docs']} 个文档，{result['chunks']} 个片段"
    )
    return result


@router.get("/stats")
async def stats():
    """知识库索引统计。"""
    return index_stats()
