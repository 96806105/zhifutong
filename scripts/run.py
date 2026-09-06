"""智服通 - 启动脚本

首次使用：
    pip install -r requirements.txt
    python scripts/build_kb.py      # 构建知识库索引（自动下载 embedding 模型）
    python scripts/run.py            # 启动服务

开发热重载：python scripts/run.py --reload
"""

import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))


def main() -> None:
    parser = argparse.ArgumentParser(description="启动智服通服务")
    parser.add_argument("--host", default=None, help="监听地址（默认读 .env）")
    parser.add_argument(
        "--port", type=int, default=None, help="监听端口（默认读 .env）"
    )
    parser.add_argument("--reload", action="store_true", help="开发热重载")
    args = parser.parse_args()

    import uvicorn
    from app.core.config import get_settings

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=args.host or settings.app_host,
        port=args.port or settings.app_port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
