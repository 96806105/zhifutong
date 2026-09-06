"""智服通 - 飞书长连接客服机器人（后台进程）

作用：建立到飞书开放平台的长连接（WebSocket），实时接收「人工回复」，
并把回复回写到对应会话（由 Web 端轮询展示）。

运行方式：
    python scripts/feishu_bot.py

前提（docs/05）：
    - 飞书自建应用已开通机器人能力
    - .env 已配置 LARK_ENABLED=true 与 LARK_APP_ID / LARK_APP_SECRET
"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import get_settings
from app.core.logger import get_logger
from app.im.feishu import available, build_event_handler

logger = get_logger("feishu_bot")


def main() -> int:
    if not available():
        logger.error(
            "飞书未配置，请在 .env 设置 LARK_ENABLED=true / LARK_APP_ID / LARK_APP_SECRET"
        )
        return 1

    s = get_settings()
    from lark_oapi.ws import Client as WsClient

    logger.info("connecting feishu ws long-connection ...")
    event_handler = build_event_handler()
    ws = WsClient(s.lark_app_id, s.lark_app_secret, event_handler=event_handler)
    ws.start()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
