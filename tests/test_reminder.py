"""리마인더 발송 조건 테스트 — 허용 3종 외 어떤 날도 침묵해야 한다."""
from datetime import date

from backend.jobs.reminder import due_messages


def state(**kw):
    base = {"phase": "STEADY", "entry_week": 1, "monthly_day": None,
            "skip_december_year": None}
    base.update(kw)
    return base


def test_silent_on_ordinary_day():
    assert due_messages(state(monthly_day=25), date(2026, 7, 22)) == []


def test_monthly_day_reminder():
    msgs = due_messages(state(monthly_day=22), date(2026, 7, 22))
    assert len(msgs) == 1 and "적립일" in msgs[0]


def test_december_third_monday():
    msgs = due_messages(state(), date(2026, 12, 21))  # 2026-12 셋째 월요일
    assert len(msgs) == 1 and "리밸런싱" in msgs[0]


def test_december_skipped_in_accel_year():
    msgs = due_messages(state(skip_december_year=2026), date(2026, 12, 21))
    assert len(msgs) == 1 and "건너뜁니다" in msgs[0]


def test_december_other_mondays_silent():
    assert due_messages(state(), date(2026, 12, 14)) == []  # 둘째 월요일
    assert due_messages(state(), date(2026, 12, 28)) == []  # 넷째 월요일


def test_entry_monday_reminder():
    msgs = due_messages(state(phase="ENTRY", entry_week=3), date(2026, 7, 20))  # 월요일
    assert len(msgs) == 1 and "3주차" in msgs[0]


def test_entry_non_monday_silent():
    assert due_messages(state(phase="ENTRY"), date(2026, 7, 22)) == []


def test_monthly_day_31_clamps_to_month_end():
    # 4월은 30일까지 — 31 설정이어도 말일(30일)에 발송, 무통보 누락 방지
    msgs = due_messages(state(monthly_day=31), date(2026, 4, 30))
    assert len(msgs) == 1 and "적립일" in msgs[0]
    assert due_messages(state(monthly_day=31), date(2026, 4, 29)) == []
    # 31일이 있는 달은 그대로 31일에
    assert len(due_messages(state(monthly_day=31), date(2026, 7, 31))) == 1
    assert due_messages(state(monthly_day=31), date(2026, 7, 30)) == []


def test_monthly_day_30_clamps_in_february():
    msgs = due_messages(state(monthly_day=30), date(2027, 2, 28))
    assert len(msgs) == 1 and "적립일" in msgs[0]
