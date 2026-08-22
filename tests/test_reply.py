"""자유 대화 프롬프트·기억 테스트 — 비서가 채팅방의 모든 내용을 알아야 한다."""
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
        "qld_shares": 120, "jepi_shares": 80, "sgov_shares": 0,
        "qld_price": 72.5, "jepi_price": 57.3, "cash_usd": 44.5,
        "total_usd": 13284.0, "qld_weight": 0.655, "fx": 1425.2, "drawdown": -0.038,
        "pnl_krw": {"QLD": 1200000, "JEPI": -50000},
    }, ensure_ascii=False))
    db.append_log("월간적립 QLD 14주", "-3.8%", "63.1%→65.5%", "월간 루틴", date="2026-08-07")

    prompt = build_chat_system_prompt()
    assert "[현재 운용 상태]" in prompt
    assert "STEADY" in prompt and "매월 25일" in prompt
    assert "1단 발동됨" in prompt
    assert "QLD 120주" in prompt and "JEPI 80주" in prompt
    assert "$13,284.00" in prompt
    assert "월간적립 QLD 14주" in prompt  # 최근 기록 주입


def test_stale_tqqq_snapshot_does_not_break_status(db):
    """QLD 전환 전 스냅샷이 남아도 상태 블록 전체가 죽지 않아야 한다."""
    from backend.reply import build_chat_system_prompt
    db.update_state(phase="STEADY", monthly_day=25)
    db.kv_set("last_snapshot", json.dumps({
        "date": "2026-08-07", "kind": "monthly",
        "tqqq_shares": 120, "jepi_shares": 80,
        "tqqq_price": 71.2, "jepi_price": 57.3,
        "total_usd": 13124.0, "tqqq_weight": 0.651, "fx": 1425.2, "drawdown": -0.038,
    }, ensure_ascii=False))

    prompt = build_chat_system_prompt()
    assert "상태 조회 실패" not in prompt
    assert "QLD 전환 전 기록" in prompt
    assert "STEADY" in prompt and "매월 25일" in prompt  # 나머지 상태는 살아 있어야


def test_chat_system_prompt_contains_full_transcript(db):
    """채팅방의 모든 내용(명령·봇 회신·사진·잡담)이 비서 프롬프트에 들어가야 한다."""
    from backend.reply import build_chat_system_prompt
    db.chat_append("user", "/setday 25")
    db.chat_append("bot", "적립일을 매월 25일로 설정했습니다.")
    db.chat_append("user", "[잔고 스크린샷 전송]")
    db.chat_append("bot", "① 판정: 월간적립 QLD 14주 ...")
    db.chat_append("user", "고마워 ㅋㅋ")

    prompt = build_chat_system_prompt()
    assert "[채팅방 대화 기록" in prompt
    assert "/setday 25" in prompt
    assert "적립일을 매월 25일로 설정했습니다." in prompt
    assert "[잔고 스크린샷 전송]" in prompt
    assert "월간적립 QLD 14주" in prompt
    assert "고마워 ㅋㅋ" in prompt


def test_transcript_dedupes_current_question(db):
    from backend.reply import _format_transcript
    db.chat_append("user", "가속조항이 뭐야?")
    text = _format_transcript(current_question="가속조항이 뭐야?")
    # 방금 받은 질문은 -p 프롬프트로 전달되므로 기록에서 중복 제거
    assert "가속조항이 뭐야?" not in text


def test_transcript_truncates_by_chars(db):
    from backend.reply import _format_transcript
    for i in range(50):
        db.chat_append("user", f"메시지-{i} " + "x" * 2000)
    text = _format_transcript()
    assert "생략" in text
    assert "메시지-49" in text      # 최신은 보존
    assert "메시지-0 " not in text  # 오래된 것은 탈락


def test_chat_clear_resets_memory(db):
    from backend import reply
    db.chat_append("user", "기억해줘")
    assert db.chat_history()[0]
    reply.reset_chat_session()  # /newchat 경로
    rows, truncated = db.chat_history()
    assert rows == [] and truncated is False


def test_chat_system_prompt_survives_empty_db(db):
    from backend.reply import build_chat_system_prompt
    prompt = build_chat_system_prompt()  # 스냅샷·로그·대화 없음
    assert "확인된 잔고 없음" in prompt
    assert "판정 기록 없음" in prompt
    assert "기록 없음 — 새 대화" in prompt


def test_usage_and_guide_cover_same_commands():
    from backend.reply import BOT_GUIDE, USAGE
    for cmd in ("/monthly", "/entry", "/december", "/withdraw",
                "/log", "/setday", "/phase", "/newchat"):
        assert cmd in USAGE
        assert cmd in BOT_GUIDE


def test_build_cmd_system_prompt():
    cmd = build_cmd("질문", system_prompt="시스템")
    assert cmd[1:3] == ["-p", "질문"]
    assert "--append-system-prompt" in cmd and "시스템" in cmd


def test_build_cmd_minimal():
    cmd = build_cmd("질문")
    assert "--append-system-prompt" not in cmd
    assert "--allowedTools" not in cmd
