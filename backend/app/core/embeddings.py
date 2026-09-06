"""智服通 - Embedding 模块

使用本地中文语义模型（BAAI/bge-small-zh-v1.5）做文本向量化。
优点：免费、离线可用、不受 API 额度限制；依赖 sentence-transformers。

首次使用会自动从 HuggingFace 镜像（hf-mirror.com）下载模型。
"""

from functools import lru_cache
from typing import Any

from .config import get_settings
from .logger import get_logger

logger = get_logger("embeddings")


@lru_cache
def get_embedder() -> Any:
    """加载（并缓存）embedding 模型。"""
    settings = get_settings()
    try:
        from sentence_transformers import SentenceTransformer

        logger.info("loading embedding model: %s", settings.embedding_model)
        model = SentenceTransformer(settings.embedding_model)
        logger.info("embedding model loaded")
        return model
    except Exception as exc:
        logger.error("embedding model load failed: %s", exc)
        raise


def embed_texts(texts: list[str]) -> list[list[float]]:
    """将文本列表向量化，返回向量列表。"""
    if not texts:
        return []
    model = get_embedder()
    vectors = model.encode(
        texts,
        normalize_embeddings=True,  # 归一化便于用余弦相似度
        show_progress_bar=False,
    )
    return [vec.tolist() for vec in vectors]


def embed_query(text: str) -> list[float]:
    """将单个查询向量化。"""
    return embed_texts([text])[0]
