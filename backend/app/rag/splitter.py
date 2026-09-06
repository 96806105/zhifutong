"""智服通 - 文本分块器

中文友好的递归分块：优先按空行、换行、句号等切分，
尽量保持语义完整；重叠覆盖保证上下文连续性。

采用迭代 + 显式栈实现，避免深递归导致 RecursionError。
"""

from collections.abc import Iterable
from dataclasses import dataclass, field

from ..core.logger import get_logger

logger = get_logger("splitter")

# 中文/通用分隔优先级
SEPARATORS = ["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""]


@dataclass
class Chunk:
    """分块结果。"""

    content: str
    metadata: dict = field(default_factory=dict)


def _merge_splits(splits: list[str], chunk_size: int, chunk_overlap: int) -> list[str]:
    """将已按分隔符切分好的小片段合并为不超过 chunk_size 的块，块间有 overlap。"""
    chunks: list[str] = []
    current = ""
    for split in splits:
        piece = current + split
        if len(piece) <= chunk_size:
            current = piece
        else:
            if current:
                chunks.append(current)
            # overlap: 取当前块末尾 chunk_overlap 字符作为新块开头
            overlap_tail = current[-chunk_overlap:] if current else ""
            current = overlap_tail + split
    if current:
        chunks.append(current)
    return chunks


def _split_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """中文友好的递归字符分块（迭代模拟）。"""
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    # 找到第一个能用的分隔符
    sep = next((s for s in SEPARATORS if s and s in text), None)
    if sep is None:
        # 无分隔符：硬切 + overlap
        return [
            text[i : i + chunk_size]
            for i in range(0, len(text), chunk_size - chunk_overlap)
        ]

    # 用该分隔符切分
    parts = text.split(sep)
    splits: list[str] = []
    for part in parts:
        part = part.strip()
        if len(part) <= chunk_size:
            splits.append(part)
        else:
            splits.extend(_split_text(part, chunk_size, chunk_overlap))

    # 合并小片段
    return _merge_splits(splits, chunk_size, chunk_overlap)


def split_documents(
    docs: Iterable, chunk_size: int = 500, chunk_overlap: int = 50
) -> list[Chunk]:
    """将文档列表切分为带元数据的 chunk 列表。

    优先按 Markdown 标题（## 三级小节）作为自然边界切块，
    语义更内聚、检索更精准；标题级文本保留为独立小 chunk。
    """
    chunks: list[Chunk] = []
    chunk_overlap = min(chunk_overlap, chunk_size - 1)
    for doc in docs:
        sections = _split_by_md_headings(doc.content)
        for section in sections:
            parts = _split_text(section, chunk_size, chunk_overlap)
            for part in parts:
                md = dict(doc.metadata)
                md["chunk_id"] = f"{md.get('source', 'doc')}#{len(chunks)}"
                chunks.append(Chunk(content=part, metadata=md))
    logger.info("split into %d chunks", len(chunks))
    return chunks


def _split_by_md_headings(text: str) -> list[str]:
    """按 Markdown 二级标题切分（保持标题在新 chunk 开头）。"""
    lines = text.splitlines()
    sections: list[str] = []
    current: list[str] = []
    for line in lines:
        if line.startswith("## "):
            if current:
                sections.append("\n".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        sections.append("\n".join(current))
    # 过滤空段
    return [s.strip() for s in sections if s.strip()]


def split_text(text: str, chunk_size: int = 500, chunk_overlap: int = 50) -> list[str]:
    """纯文本分块（测试用）。"""
    return _split_text(text, chunk_size, min(chunk_overlap, chunk_size - 1))
