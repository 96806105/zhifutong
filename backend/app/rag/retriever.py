"""智服通 - 检索器

混合检索：
- 向量相似度（ChromaDB 余弦）
- 关键词命中评分（BM25 简化版）

最终分数 = w1*vector_score + w2*keyword_score，提升多分类知识库检索准确度。
支持 Top-K、分类过滤、阈值过滤与基础重排。
"""

from collections import Counter
from dataclasses import dataclass, field

import chromadb

from ..core.config import get_settings
from ..core.embeddings import embed_query
from ..core.logger import get_logger
from .indexer import COLLECTION_NAME

logger = get_logger("retriever")


@dataclass
class Hit:
    """检索命中片段。"""

    content: str
    metadata: dict = field(default_factory=dict)
    score: float = 0.0
    vector_score: float = 0.0
    keyword_score: float = 0.0


def _get_collection():
    settings = get_settings()
    settings.vector_store_path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(settings.vector_store_path))
    return client.get_or_create_collection(
        name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
    )


# --- 关键词评分（简化 BM25） ---


def _tokenize(text: str) -> list[str]:
    """简单词元化：保留中文二元组与英文单词。"""
    tokens: list[str] = []
    # 英文/数字词
    tokens.extend(__import__("re").findall(r"[a-zA-Z0-9]+", text.lower()))
    # 中文连续片段按二元组
    zh = __import__("re").findall(r"[\u4e00-\u9fff]+", text)
    for segment in zh:
        if len(segment) == 1:
            tokens.append(segment)
        else:
            tokens.extend(segment[i : i + 2] for i in range(len(segment) - 1))
    return tokens


def _bm25_score(
    query_tokens: list[str], doc_tokens: list[str], avgdl: float, N: int, df: Counter
) -> float:
    """简化 BM25 评分。"""
    if not query_tokens or not doc_tokens:
        return 0.0
    k1, b = 1.5, 0.75
    doc_len = len(doc_tokens)
    tf = Counter(doc_tokens)
    score = 0.0
    for qt in set(query_tokens):
        if qt not in tf:
            continue
        idf = (
            __import__("math").log(1 + (N - df[qt] + 0.5) / (df[qt] + 0.5))
            if df[qt]
            else 0
        )
        f_d = tf[qt]
        score += idf * (f_d * (k1 + 1)) / (f_d + k1 * (1 - b + b * doc_len / avgdl))
    # 归一化到 0-1 近似
    return 1 - __import__("math").exp(-score)


def retrieve(
    query: str,
    top_k: int | None = None,
    category: str | None = None,
    threshold: float | None = None,
) -> list[Hit]:
    """混合检索与查询最相关的 top_k 个片段。"""
    settings = get_settings()
    top_k = top_k or settings.top_k
    threshold = settings.retrieve_threshold if threshold is None else threshold

    collection = _get_collection()
    if collection.count() == 0:
        logger.warning("vector store is empty, please rebuild index")
        return []

    query_vec = embed_query(query)
    where = {"category": category} if category else None
    try:
        result = collection.query(
            query_embeddings=[query_vec],
            n_results=min(top_k * 3, collection.count()),
            where=where,
        )
    except Exception as exc:  # noqa: BLE001
        import traceback

        logger.error("retrieve failed: %s\n%s", exc, traceback.format_exc())
        return []

    ids = result.get("ids", [[]])[0]
    docs = result.get("documents", [[]])[0]
    metas = result.get("metadatas", [[]])[0]
    dists = result.get("distances", [[]])[0]

    # BM25 语料统计
    all_docs = docs
    avgdl = sum(len(_tokenize(d)) for d in all_docs) / max(1, len(all_docs))
    df = Counter()
    for t in set().union(*(set(_tokenize(d)) for d in all_docs)):
        df[t] = sum(1 for d in all_docs if t in set(_tokenize(d)))

    query_tokens = _tokenize(query)

    hits: list[Hit] = []
    for doc_id, doc, meta, dist in zip(ids, docs, metas, dists, strict=False):
        vec_score = max(0.0, 1.0 - float(dist))
        kw_score = _bm25_score(query_tokens, _tokenize(doc), avgdl, len(all_docs), df)
        # 融合分数：向量为主，关键词加权
        fused = 0.8 * vec_score + 0.2 * kw_score
        if fused < threshold:
            continue
        hits.append(
            Hit(
                content=doc,
                metadata=meta or {},
                score=fused,
                vector_score=vec_score,
                keyword_score=kw_score,
            )
        )

    hits.sort(key=lambda h: h.score, reverse=True)
    hits = hits[:top_k]
    logger.info(
        "mixed retrieve %d hits (top_k=%d, threshold=%.2f)", len(hits), top_k, threshold
    )
    return hits
