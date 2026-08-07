"""자유 질문 프롬프트·대화 세션 테스트 — 봇이 자기 명령어를 설명하고 대화를 이어가야 한다."""
import pytest

from backend.claude_runner import build_cmd
from backend.reply import build_chat_system_prompt, BOT_GUIDE, USAGE


def test_chat_system_prompt_contains_bot_guide():
    prompt = build_chat_system_prompt()
    # 봇 사용법(명령어·단계 설명)이 지식원에 포함되어야 자기 명령어를 답할 수 있다
    assert "[봇 사용법]" in prompt
    for cmd in ("/phase", "/monthly", "/entry", "/december",
                "/withdraw", "/setday", "/log", "/newchat"):
        assert cmd in prompt
    assert "SETUP" in prompt and "ENTRY" in prompt and "STEADY" in prompt
    assert "[투자 규칙서]" in prompt
    assert "가드레일" in prompt


def test_usage_and_guide_cover_same_commands():
    # /help 목록에 있는 명령이 봇 사용법 설명에도 빠짐없이 있어야 한다
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


def test_chat_session_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("WATCHLIST_DB", str(tmp_path / "t.db"))
    from backend import db, reply
    db.init_db()
    assert db.kv_get("chat_session_id") is None
    db.kv_set("chat_session_id", "sess-abc")
    assert db.kv_get("chat_session_id") == "sess-abc"
    reply.reset_chat_session()  # /newchat 경로
    assert db.kv_get("chat_session_id") is None
