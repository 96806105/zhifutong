"""智服通 - 知识库索引构建脚本

用法：
    python scripts/build_kb.py

将 knowledge_base 目录下的文档分块、向量化并写入 ChromaDB。
"""

import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))


def main() -> None:
    print("正在构建知识库索引...")
    t0 = time.time()
    from app.rag.indexer import rebuild_index

    result = rebuild_index()
    elapsed = time.time() - t0
    print(
        f"完成：{result['docs']} 个文档，{result['chunks']} 个片段（耗时 {elapsed:.1f}s）"
    )


if __name__ == "__main__":
    main()
