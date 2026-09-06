"""智服通 - 核心单元测试

覆盖：意图识别、转人工决策、文本分块、简易 BM25 检索、SQLite 存储。
运行：  pytest 或  python -m pytest tests -q
"""

import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
BACKEND_DIR = TESTS_DIR.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.dialog import intent as intent_mod
from app.dialog import storage as storage_mod
from app.dialog.transfer import TransferEvaluator
from app.rag.retriever import _tokenize
from app.rag.splitter import split_text


# ── 意图识别 ────────────────────────────────────────────
class TestIntent:
    def test_transfer_keyword(self):
        r = intent_mod.classify("帮我转人工")
        assert r["intent"] == "transfer_human"
        assert r["is_transfer"] is True

    def test_greeting(self):
        r = intent_mod.classify("你好呀")
        assert r["intent"] == "greeting"

    def test_negative_emotion(self):
        r = intent_mod.classify("你们的服务太垃圾了")
        assert r["is_negative"] is True
        assert r["is_transfer"] is False

    def test_sensitive_operation(self):
        r = intent_mod.classify("我要批量导出所有客户数据")
        assert r["is_sensitive"] is True

    def test_normal_query(self):
        r = intent_mod.classify("打印机无法连接怎么办")
        assert r["intent"] == "query"
        assert r["is_transfer"] is False


# ── 转人工决策 ────────────────────────────────────────────
class TestTransfer:
    def test_explicit_transfer(self):
        ev = TransferEvaluator()
        yes, _ = ev.should_transfer("s1", 0.95, explicit=True)
        assert yes is True

    def test_sensitive_transfer(self):
        ev = TransferEvaluator()
        yes, _ = ev.should_transfer("s1", 0.95, sensitive=True)
        assert yes is True

    def test_negative_transfer(self):
        ev = TransferEvaluator()
        yes, _ = ev.should_transfer("s1", 0.9, negative=True)
        assert yes is True

    def test_threshold_accumulation(self):
        ev = TransferEvaluator()
        # 连续 3 次低置信度触发转人工
        assert ev.should_transfer("s9", 0.2)[0] is False
        assert ev.should_transfer("s9", 0.2)[0] is False
        yes, reason = ev.should_transfer("s9", 0.2)
        assert yes is True
        assert "转" in reason

    def test_good_answer_resets_counter(self):
        ev = TransferEvaluator()
        ev.should_transfer("s10", 0.2)
        ev.should_transfer("s10", 0.9)  # 良好回答重置
        assert ev.fail_count("s10") == 0


# ── 文本分块 ────────────────────────────────────────────
class TestSplitter:
    def test_heading_split(self):
        text = "# 标题\n## 第一节\n内容A\n## 第二节\n内容B"
        chunks = split_text(text, chunk_size=500, chunk_overlap=0)
        joined = "".join(chunks)
        assert "内容A" in joined
        assert "内容B" in joined
        # 标题不应成为垃圾块
        assert all(c.strip() for c in chunks)

    def test_chunk_size_respected(self):
        text = "我" * 300
        chunks = split_text(text, chunk_size=100, chunk_overlap=10)
        # 300 字符 / (100 - 10) ≈ 4 块
        assert 3 <= len(chunks) <= 5


# ── 检索工具 ────────────────────────────────────────────
class TestRetrieverTools:
    def test_tokenize_chinese(self):
        toks = _tokenize("打印机无法连接")
        # bigram 切分：打印/印机/无法/连接
        assert "打印" in toks
        assert "连接" in toks


# ── SQLite 存储 ────────────────────────────────────────────
class TestStorage:
    def test_session_and_messages_roundtrip(self):
        init_db = getattr(storage_mod, "init_db", lambda: None)
        init_db()
        sid = storage_mod.create_session(user_name="tester-unit")
        assert sid

        storage_mod.add_message(sid, "user", "如何修改密码")
        storage_mod.add_message(sid, "assistant", "请参阅账号文档", confidence=0.8)

        msgs = storage_mod.get_session_messages(sid)
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[1]["confidence"] == 0.8

    def test_ticket_creation(self):
        init_db = getattr(storage_mod, "init_db", lambda: None)
        init_db()
        sid = storage_mod.create_session()
        tid = storage_mod.create_ticket(sid, reason="测试工单")
        assert tid.startswith("TKT-")
        tickets = storage_mod.list_tickets(limit=10)
        assert any(t["id"] == tid for t in tickets)


# ── 人工回复回写（飞书接线） ────────────────────────────────────────────
class TestHumanReply:
    def test_latest_open_ticket_binding(self):
        init_db = getattr(storage_mod, "init_db", lambda: None)
        init_db()
        sid = storage_mod.create_session()
        tid = storage_mod.create_ticket(sid, reason="人工接线测试")
        assert storage_mod.get_ticket_session(tid) == sid

        latest = storage_mod.get_latest_open_ticket()
        assert latest and latest["id"] == tid
        assert latest["session_id"] == sid

    def test_human_reply_written_and_ticket_closed(self):
        init_db = getattr(storage_mod, "init_db", lambda: None)
        init_db()
        sid = storage_mod.create_session()
        tid = storage_mod.create_ticket(sid, reason="人工接线测试")
        storage_mod.add_human_reply(sid, "已为您重置密码，请查收邮件。", ticket_id=tid)

        msgs = storage_mod.get_session_messages(sid)
        last = msgs[-1]
        assert last["role"] == "assistant"
        assert last["action"] == "human"
        # 工单应标记为已处理（done）
        assert storage_mod.get_ticket_status(tid) == "done"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
