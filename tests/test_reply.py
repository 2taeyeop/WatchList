"""자유 대화 프롬프트·세션 테스트 — 비서가 명령어·현황·기록을 알고 대화를 이어가야 한다."""
import json

import pytest

from backend.claude_runner import build_cmd


@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("WATCHLIST_DB", str(tmp_path / "t.db"))
    from backend import db as db_module
    db_module.init_db()
    return db_module


def test_chat_system_prompt_contains_bot_guide(db):
    from backend.reply import build_chat_system_prompt
    prompt = build_chat_system_prompt()
    # 봇 사용법(명령어·단계 설명)이 지식원에 포함되어야 자기 명령어를 답할 수 있다
    assert "[봇 사용법]" in prompt
    for cmd in ("/phase", "/monthly", "/entry", "/december",
                "/withdraw", "/setday", "/log", "/newchat"):
        assert cmd in prompt
    assert "SETUP" in prompt and "ENTRY" in prompt and "STEADY" in prompt
    assert "[투자 규칙서]" in prompt
    assert "가드레일" in prompt


def test_chat_system_prompt_contains_status(db):
    from backend.reply import build_chat_system_prompt
    db.update_state(phase="STEADY", monthly_day=25, tier1_fired=True, carry_usd=12.5)
    db.kv_set("last_snapshot", json.dumps({
        "date": "2026-08-07", "kind": "monthly",
        "tqqq_shares": 120, "jepi_shares": 80, "sgov_shares": 0,
        "tqqq_price": 72.5, "jepi_price": 57.3, "cash_usd": 44.5,
        "total_usd": 13284.0, "tqqq_weight": 0.655, "fx": 1425.2, "drawdown": -0.038,
        "pnl_krw": {"TQQQ": 1200000, "JEPI": -50000},
    }, ensure_ascii=False))
    db.append_log("월간적립 TQQQ 14주", "-3.8%", "63.1%→65.5%", "월간 루틴", date="2026-08-07")

    prompt = build_chat_system_prompt()
    assert "[현재 운용 상태]" in prompt
    assert "STEADY" in prompt and "매월 25일" in prompt
    assert "1단 발동됨" in prompt
    assert "TQQQ 120주" in prompt and "JEPI 80주" in prompt
    assert "$13,284.00" in prompt
    assert "월간적립 TQQQ 14주" in prompt  # 최근 기록 주입


def test_chat_system_prompt_survives_empty_db(db):
    from backend.reply import build_chat_system_prompt
    prompt = build_chat_system_prompt()  # 스냅샷·로그 없음
    assert "확인된 잔고 없음" in prompt
    assert "판정 기록 없음" in prompt


def test_usage_and_guide_cover_same_commands():
    from backend.reply import BOT_GUIDE, USAGE
    for cmd in ("/monthly", "/entry", "/december", "/withdraw",
                "/log", "/setday", "/phase", "/newchat"):
        assert cmd in USAGE
        assert cmd in BOT_GUIDE


def test_build_cmd_resume_and_system_prompt():
    cmd = build_cmd("질문", system_prompt="시스템", resume="sess-123")
    assert cmd[1:3] == ["-p", "질문"]
    assert "--append-system-prompt" in cmd and "시스템" in cmd
    assert "--resume" in cmd
    assert cmd[cmd.index("--resume") + 1] == "sess-123"


def test_build_cmd_without_session_flags():
    cmd = build_cmd("질문")
    assert "--resume" not in cmd
    assert "--append-system-prompt" not in cmd


def test_chat_session_roundtrip(db):
    from backend import reply
    assert db.kv_get("chat_session_id") is None
    db.kv_set("chat_session_id", "sess-abc")
    assert db.kv_get("chat_session_id") == "sess-abc"
    reply.reset_chat_session()  # /newchat 경로
    assert db.kv_get("chat_session_id") is None
