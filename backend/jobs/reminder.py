"""리마인더 잡 — 매일 아침 1회 실행(systemd timer). 해당일에만 발송, 그 외 침묵.

작업지시 4-3: 허용 리마인더는 적립일·12월 셋째 월요일·ENTRY 주간 셋뿐 —
매일 뉴스 푸시의 부활 금지. 발송 조건 판정은 순수 함수(due_messages)로 분리해 테스트한다.
"""
import calendar
from datetime import date, datetime, timedelta, timezone

from backend import db, notify

_KST = timezone(timedelta(hours=9))


def _is_third_monday(d: date) -> bool:
    return d.weekday() == 0 and 15 <= d.day <= 21


def due_messages(state: dict, d: date) -> list[str]:
    msgs = []
    monthly_day = state.get("monthly_day")
    if monthly_day:
        # 29~31 설정 시 그 일이 없는 달은 말일로 보정(무통보 누락 방지).
        last_day = calendar.monthrange(d.year, d.month)[1]
        if d.day == min(monthly_day, last_day):
            msgs.append("적립일입니다. 낮에 30만 환전(우대 시간대), 밤에 잔고 캡처를 보내세요.")
    if d.month == 12 and _is_third_monday(d):
        if state.get("skip_december_year") == d.year:
            msgs.append("가속 발동 연도라 올해 12월 리밸런싱은 건너뜁니다.")
        else:
            msgs.append("12월 셋째 월요일 — 리밸런싱과 공제 수확일입니다. /december 로 진행하세요.")
    if state.get("phase") == "ENTRY" and d.weekday() == 0:
        msgs.append(f"진입기 {state.get('entry_week', 1)}주차 월요일입니다. "
                    "/entry 후 잔고 캡처를 보내세요.")
    return msgs


def main() -> None:
    db.init_db()
    today = datetime.now(_KST).date()
    msgs = due_messages(db.get_state(), today)
    if not msgs:
        print("오늘은 리마인더 없음")
        return
    for m in msgs:
        notify.send(m)
    print(f"리마인더 {len(msgs)}건 발송")


if __name__ == "__main__":
    main()
