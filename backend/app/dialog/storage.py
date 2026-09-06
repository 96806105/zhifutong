"""智服通 - 会话与历史存储

管理会话的创建、消息读写、历史查询与工单创建。
"""

import secrets
from typing import Any

from sqlalchemy import select

from ..core.config import get_settings
from ..core.logger import get_logger
from .store import (
    MessageRecord,
    SessionLocal,
    SessionRecord,
    TicketRecord,
)

logger = get_logger("store")


def _db():
    return SessionLocal()


def create_session(user_name: str | None = None) -> str:
    """创建新会话，返回 session_id。"""
    session_id = secrets.token_hex(16)
    with _db() as db:
        db.add(SessionRecord(id=session_id, user_name=user_name))
        db.commit()
    logger.info("session created: %s", session_id)
    return session_id


def get_session(session_id: str) -> SessionRecord | None:
    with _db() as db:
        return db.get(SessionRecord, session_id)


def add_message(
    session_id: str,
    role: str,
    content: str,
    *,
    sources: list[dict] | None = None,
    action: str = "none",
    confidence: float | None = None,
) -> None:
    """持久化一条消息。"""
    with _db() as db:
        db.add(
            MessageRecord(
                session_id=session_id,
                role=role,
                content=content,
                sources=__import__("json").dumps(sources, ensure_ascii=False)
                if sources
                else None,
                action=action,
                confidence=confidence,
            )
        )
        session = db.get(SessionRecord, session_id)
        if session:
            session.updated_at = __import__("datetime").datetime.utcnow()
        db.commit()


def get_history(session_id: str, limit: int | None = None) -> list[dict[str, Any]]:
    """读取会话历史（按时间正序），可选限制条数。"""
    rounds = limit or get_settings().session_history_rounds
    with _db() as db:
        rows = (
            db.execute(
                select(MessageRecord)
                .where(MessageRecord.session_id == session_id)
                .order_by(MessageRecord.id.desc())
                .limit(rounds * 2)
            )
            .scalars()
            .all()
        )
    rows.reverse()
    return [{"role": m.role, "content": m.content, "action": m.action} for m in rows]


def list_sessions(limit: int = 50) -> list[dict[str, Any]]:
    """列出最近会话。"""
    with _db() as db:
        rows = (
            db.execute(
                select(SessionRecord)
                .order_by(SessionRecord.updated_at.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )
    return [
        {
            "id": s.id,
            "user_name": s.user_name,
            "status": s.status,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        }
        for s in rows
    ]


def set_session_status(session_id: str, status: str) -> None:
    with _db() as db:
        session = db.get(SessionRecord, session_id)
        if session:
            session.status = status
            db.commit()


def create_ticket(session_id: str, reason: str) -> str:
    """创建转人工工单，返回工单号。"""
    ticket_id = f"TKT-{secrets.token_hex(3).upper()}"
    with _db() as db:
        db.add(TicketRecord(id=ticket_id, session_id=session_id, reason=reason))
        db.commit()
    logger.info("ticket created: %s", ticket_id)
    return ticket_id


def list_tickets(limit: int = 50) -> list[dict[str, Any]]:
    with _db() as db:
        rows = (
            db.execute(
                select(TicketRecord)
                .order_by(TicketRecord.created_at.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )
    return [
        {
            "id": t.id,
            "session_id": t.session_id,
            "reason": t.reason,
            "status": t.status,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in rows
    ]


def get_session_messages(session_id: str) -> list[dict[str, Any]]:
    """获取会话的全部消息（管理端/历史页用）。"""
    with _db() as db:
        rows = (
            db.execute(
                select(MessageRecord)
                .where(MessageRecord.session_id == session_id)
                .order_by(MessageRecord.id)
            )
            .scalars()
            .all()
        )
    return [
        {
            "role": m.role,
            "content": m.content,
            "sources": m.sources,
            "action": m.action,
            "confidence": m.confidence,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in rows
    ]


def get_latest_open_ticket() -> dict[str, Any] | None:
    """获取最近一个「待人工处理」的工单（供人工回复定位会话）。"""
    with _db() as db:
        row = (
            db.execute(
                select(TicketRecord)
                .where(TicketRecord.status == "open")
                .order_by(TicketRecord.created_at.desc())
            )
            .scalars()
            .first()
        )
        if not row:
            return None
        return {
            "id": row.id,
            "session_id": row.session_id,
            "reason": row.reason,
            "status": row.status,
        }


def get_ticket_session(ticket_id: str) -> str | None:
    """按工单号定位所属会话。"""
    with _db() as db:
        row = db.get(TicketRecord, ticket_id)
        return row.session_id if row else None


def get_ticket_status(ticket_id: str) -> str | None:
    """查询工单状态：open / done（不存在返回 None）。"""
    with _db() as db:
        row = db.get(TicketRecord, ticket_id)
        return row.status if row else None


def mark_ticket_done(ticket_id: str) -> None:
    """将工单标记为已处理。"""
    with _db() as db:
        ticket = db.get(TicketRecord, ticket_id)
        if ticket:
            ticket.status = "done"
            logger.info("ticket %s marked done", ticket_id)
            db.commit()


def add_human_reply(
    session_id: str, text: str, *, ticket_id: str | None = None
) -> None:
    """人工回复回写：作为 assistant 消息写入会话，action=human。"""
    with _db() as db:
        db.add(
            MessageRecord(
                session_id=session_id,
                role="assistant",
                content=text,
                action="human",
                confidence=1.0,
            )
        )
        if ticket_id:
            ticket = db.get(TicketRecord, ticket_id)
            if ticket:
                ticket.status = "done"
        db.commit()
    logger.info("human reply written to %s", session_id)
