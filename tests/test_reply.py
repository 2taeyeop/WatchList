"""자유 질문 프롬프트 조립 테스트 — 봇이 자기 명령어를 설명할 수 있어야 한다."""
from backend.reply import build_freeform_prompt, BOT_GUIDE, USAGE


def test_freeform_prompt_contains_bot_guide():
    prompt = build_freeform_prompt("phase 명령어가 뭐야?")
    # 봇 사용법(명령어·단계 설명)이 지식원에 포함되어야 자기 명령어를 답할 수 있다
    assert "[봇 사용법]" in prompt
    for cmd in ("/phase", "/monthly", "/entry", "/december", "/withdraw", "/setday", "/log"):
        assert cmd in prompt
    assert "SETUP" in prompt and "ENTRY" in prompt and "STEADY" in prompt
    # 규칙서·가드레일·질문도 함께
    assert "[투자 규칙서]" in prompt
    assert "가드레일" in prompt
    assert "phase 명령어가 뭐야?" in prompt


def test_usage_and_guide_cover_same_commands():
    # /help 목록에 있는 명령이 봇 사용법 설명에도 빠짐없이 있어야 한다
    for cmd in ("/monthly", "/entry", "/december", "/withdraw", "/log", "/setday", "/phase"):
        assert cmd in USAGE
        assert cmd in BOT_GUIDE
