"""智服通 - 知识库索引器

将 chunk 向量化后写入 ChromaDB（持久化到本地目录）。
支持全量重建与增量添加。
"""

from uuid import uuid4

import chromadb

from ..core.config import get_settings
from ..core.embeddings import embed_texts
from ..core.logger import get_logger
from .loader import load_all_documents
from .splitter import split_documents

logger = get_logger("indexer")
COLLECTION_NAME = "it_support_kb"


def _get_collection():
    settings = get_settings()
    settings.vector_store_path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(settings.vector_store_path))
    return client.get_or_create_collection(
        name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
    )


def rebuild_index() -> dict:
    """全量重建知识库索引，返回统计信息。"""
    settings = get_settings()
    docs = load_all_documents()
    chunks = split_documents(
        docs, chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap
    )

    if not chunks:
        logger.warning("no chunks to index")
        return {"docs": 0, "chunks": 0}

    collection = _get_collection()
    # 全量重建：删除旧数据
    try:
        collection.delete(where={"$or": [{"source": {"$ne": ""}}]})
    except Exception:  # noqa: BLE001 - 空集合可能报错
        logger.warning("clear old index failed (probably empty)")

    ids = [str(uuid4()) for _ in chunks]
    texts = [c.content for c in chunks]
    metadatas = [c.metadata for c in chunks]

    logger.info("embedding %d chunks...", len(chunks))
    vectors = embed_texts(texts)

    # 分批写入（避免单次请求过大）
    batch = 64
    for i in range(0, len(chunks), batch):
        collection.add(
            ids=ids[i : i + batch],
            documents=texts[i : i + batch],
            embeddings=vectors[i : i + batch],
            metadatas=metadatas[i : i + batch],
        )
        logger.info("indexed %d/%d", min(i + batch, len(chunks)), len(chunks))

    logger.info("rebuild done: %d chunks", len(chunks))
    return {"docs": len(docs), "chunks": len(chunks)}


def index_stats() -> dict:
    """返回当前知识库统计。"""
    try:
        collection = _get_collection()
        count = collection.count()
        docs = 0
        try:
            metas = collection.get(include=["metadatas"]).get("metadatas") or []
            docs = len({m.get("source") for m in metas if m.get("source")})
        except Exception:  # noqa: BLE001
            docs = 0
        return {"chunks": count, "docs": docs}
    except Exception as exc:  # noqa: BLE001
        logger.warning("index_stats failed: %s", exc)
        return {"chunks": 0, "docs": 0}
