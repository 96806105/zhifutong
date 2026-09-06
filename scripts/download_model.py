"""智服通 - Embedding 模型下载脚本

从 HuggingFace 下载中文 embedding 模型（BAAI/bge-small-zh-v1.5）到本地目录，
供系统完全离线使用。

用法：
    python scripts/download_model.py

说明：
- 国内网络自动使用镜像 HF_ENDPOINT=https://hf-mirror.com
- 下载完成后保存在 ./models/bge-small-zh-v1.5
"""

import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

REPO_ID = "BAAI/bge-small-zh-v1.5"
TARGET_DIR = Path(__file__).resolve().parent.parent / "models" / "bge-small-zh-v1.5"


def main() -> None:
    os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

    if TARGET_DIR.exists() and (TARGET_DIR / "model.safetensors").exists():
        print(f"模型已存在：{TARGET_DIR}")
        return

    print(f"下载模型 {REPO_ID} ...（首次约 100MB，请耐心等待）")
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(REPO_ID)
    TARGET_DIR.parent.mkdir(parents=True, exist_ok=True)
    model.save(TARGET_DIR)
    print(f"模型已保存至：{TARGET_DIR}")


if __name__ == "__main__":
    main()
