"""智服通 - 文档加载器

加载 knowledge_base 目录下的 Markdown 文档，
提取文本、标题、分类（目录名）与文件名作为元数据。
"""

from dataclasses import dataclass, field

from ..core.config import get_settings
from ..core.logger import get_logger

logger = get_logger("loader")

SUPPORTED_EXTS = {".md", ".markdown", ".txt"}


@dataclass
class Document:
    """统一的文档对象。"""

    content: str
    metadata: dict = field(default_factory=dict)


def load_all_documents() -> list[Document]:
    """加载知识库目录下的所有支持文档。"""
    base = get_settings().knowledge_base_path
    if not base.exists():
        logger.warning("knowledge base dir not found: %s", base)
        return []

    docs: list[Document] = []
    for path in sorted(base.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTS:
            continue
        if path.name.startswith("."):
            continue
        category = str(path.parent.relative_to(base))
        docs.append(
            Document(
                content=path.read_text(encoding="utf-8"),
                metadata={
                    "category": category,
                    "source": path.name,
                },
            )
        )
    logger.info("loaded %d documents", len(docs))
    return docs
