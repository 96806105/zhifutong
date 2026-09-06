"""智服通 - 飞书人工客服接线

实现「转人工 → 推送飞书 → 人工回复 → 回写会话」的双向闭环。

职责划分：
- 正常流程：智服通 Web 端把求助信息推送给飞书人工，人工在飞书里回复。
- 长连接进程（scripts/feishu_bot.py）内调用 on_message_received 处理收到的人工回复，
  回写会话并标记工单为已处理。

使用前提（见 docs/05-飞书人工接线.md）：
  1. 在飞书开放平台创建企业自建应用，开通「机器人」能力
  2. 权限：im:message（发消息/收消息回调）
  3. .env 配置 LARK_APP_ID / LARK_APP_SECRET / LARK_NOTIFY_CHAT_ID
"""

import json

from ..core.config import get_settings
from ..core.logger import get_logger
from ..dialog import storage as storage_mod

logger = get_logger("im.feishu")

_client = None


def _get_client():
    """惰性创建 lark-oapi 客户端（避免 import 成本 / 循环依赖）。"""
    global _client
    if _client is None:
        from lark_oapi import Client as LarkClient

        s = get_settings()
        _client = (
            LarkClient.builder()
            .app_id(s.lark_app_id)
            .app_secret(s.lark_app_secret)
            .log_level(2)  # INFO
            .build()
        )
    return _client


def available() -> bool:
    """飞书接线是否已配置可用。"""
    s = get_settings()
    return bool(s.lark_enabled and s.lark_app_id and s.lark_app_secret)


def _notify_target():
    """返回消息接收目标 (kind, id)。优先群聊，其次单聊。"""
    s = get_settings()
    if s.lark_notify_chat_id:
        return "chat_id", s.lark_notify_chat_id
    if s.lark_notify_open_id:
        return "open_id", s.lark_notify_open_id
    return None, None


def notify_human(session_id: str, user_text: str, ticket_id: str) -> bool:
    """把转人工诉求推送给飞书人工。返回是否发送成功。"""
    if not available():
        logger.info("feishu not configured, skip notify")
        return False

    kind, target = _notify_target()
    if not target:
        logger.warning("feishu notify target empty, skip")
        return False

    content = {
        "text": (
            f"📣 【智服通】转人工请求\n"
            f"工单号：{ticket_id}\n"
            f"会话ID：{session_id}\n"
            f"用户问题：{user_text or '（无）'}\n"
            f"处理方式：直接在本聊天中回复内容，回复将自动回传给用户。"
        )
    }
    body = {
        kind: target,
        "msg_type": "text",
        "content": json.dumps(content, ensure_ascii=False),
    }
    req_kwargs = {
        "receive_id_type": kind,
        "body": body,
    }
    try:
        req = __import__("lark_oapi").api.im.v1.CreateMessageRequest
        request = req(**req_kwargs)
        resp = _get_client().im.v1.message.create(request)
        if not resp.success():
            logger.error("feishu notify failed: code=%s msg=%s", resp.code, resp.msg)
            return False
        logger.info("feishu notify sent: %s -> %s", session_id, ticket_id)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("feishu notify error: %s", exc)
        return False


def on_message_received(message) -> None:
    """长连接线程收到消息时的回调。

    人工在接收方聊天里回复 → 解析目标会话 → 回写为人工回复。
    可写 `TKT-ABC123 具体回复内容` 精确定位；否则自动绑定最近待处理工单。
    """
    import re as _re

    try:
        event = message.event
        msg = event.message
        if not msg or msg.message_type != "text":
            return
        content = json.loads(msg.content or "{}")
        text = (content.get("text") or "").strip()
        if not text:
            return

        logger.info("im message received: %s", text[:60])

        # 1) 若回复以 TKT-XXXX 开头 → 精确绑定该工单
        match = _re.match(r"^(TKT-[A-F0-9]{6})\s*(.*)$", text, _re.IGNORECASE)
        if match:
            ticket_id = match.group(1).upper()
            session_id = storage_mod.get_ticket_session(ticket_id)
            reply_text = match.group(2).strip() or text
            if not session_id:
                logger.warning("ticket %s not found", ticket_id)
                return
        else:
            # 2) 否则绑定最近待处理工单
            ticket = storage_mod.get_latest_open_ticket()
            if not ticket:
                logger.warning("no pending ticket to bind reply, drop")
                return
            ticket_id, session_id, reply_text = ticket["id"], ticket["session_id"], text

        storage_mod.add_human_reply(session_id, reply_text, ticket_id=ticket_id)
        logger.info(
            "human reply bound: %s -> %s (ticket %s)",
            session_id,
            reply_text[:40],
            ticket_id,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("on_message_received error: %s", exc)


def build_event_handler():
    """构造飞书长连接事件处理器（供 scripts/feishu_bot.py 使用）。"""
    from lark_oapi import EventDispatcherHandler

    return (
        EventDispatcherHandler.builder("", "")
        .register_p2_im_message_receive_v1(on_message_received)
        .build()
    )
