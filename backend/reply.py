"""회신 조립 — 판정 숫자는 코드가 그대로 렌더한다(클로드가 숫자를 만지지 못하게).

자유 질문(명령어도 사진도 아닌 텍스트)은 '개인 주식 비서' 대화 창구다: 잡담·뉴스
검색(WebSearch)·현황 조회까지 허용하되, 매매 행동 제안과 돈 계산은 집행 가드레일로
막는다. 비서의 기억은 CLI 세션이 아니라 봇이 소유한 채팅방 기록(db.chat_log)이다 —
명령어·판정 회신·사진까지 채팅방의 모든 내용이 기록되고, 매 호출 시스템 프롬프트로
통째로 주입된다(/newchat 으로 초기화). 매 클로드 프로세스는 일회용이다.
"""
import json
import os
from datetime import datetime, timedelta, timezone

from backend import db
from backend.claude_runner import run_claude
from backend.rules import Judgment, Order

_KST = timezone(timedelta(hours=9))

RULEBOOK_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts", "rulebook.md")

CRISIS_BANNER = ("⚠️ 이 낙폭은 설계 시 예고된 숫자입니다 (-50%는 사실상 확정 이벤트, "
                 "QLD 줄 -80%대는 2008년 실측). 허용 행동은 셋: 적립 매수 / 가속 실행 / 무행동.")

REVISION_NOTICE = ("규칙 밖 매매는 계산을 돕지 않습니다. 개정 절차를 따르세요:\n"
                   "메모장 한 문단 → 72시간 재독 → 개정안 작성, 발효는 위기 모드 해제 후 30일.")

_SIDE_KR = {"SELL": "매도", "BUY": "매수"}

# 명령어 요약 — /help 회신과 자유 질문 지식원이 같은 원본을 쓰게 여기 한 곳에만 둔다.
USAGE = """사용법
잔고 스크린샷(토스)만 보내면 월간 루틴 판정(/monthly 와 동일)

/monthly — 월간 적립 판정
/entry — 진입기 주간 루틴(SGOV→QLD)
/december — 12월 리밸런싱 + 공제·손실 수확
/withdraw <원화금액> — 생계 인출(즉시 협조)
/log — 최근 기록 10줄
/setday <일> — 적립일 설정
/phase <SETUP|ENTRY|STEADY> — 단계 전환
/newchat — 비서 기억(채팅방 기록) 초기화"""

# 자유 질문용 봇 자체 설명 — 규칙서에는 없는 명령어·플로우 지식(이게 빠지면
# 봇이 자기 명령어를 설명 못 한다).
BOT_GUIDE = """- 잔고 스크린샷 전송: 수치 추출 → 확인 게이트([✅ 맞음]/[❌ 다시]) → ✅ 시
  판정·주문표·기록 로그 회신. 명령 없이 사진만 보내면 월간 루틴(/monthly)으로 처리.
- /monthly: 월간 적립 판정. 달러 예수금 전액으로 QLD 비중<70%면 QLD, 아니면 JEPI 내림 매수.
- /entry: 진입기(ENTRY) 주간 루틴. 이번 주차 SGOV 매도(5주 분할, 5주차 전량) → QLD 매수.
  5회 완료 시 STEADY 자동 전환.
- /december: 12월 셋째 월요일 리밸런싱 + 공제·손실 수확. 먼저 올해 실현손익 합계를
  숫자로 입력한 뒤 스크린샷을 보낸다. 가속 발동 연도는 자동 스킵.
- /withdraw <원화금액>: 생계 인출 — 70:30 금액 비율 매도 주수와 예상 실현손익 보고. 양수만.
- /log: 최근 기록 10줄. 형식 `날짜 | 행동 | 하락률 | 비중 전→후 | 메모`.
- /setday <일>: 매월 적립일 설정(1~31). 해당 일이 없는 달은 말일에 리마인더.
- /phase <SETUP|ENTRY|STEADY>: 운용 단계 전환 — SETUP=가동 전(사진을 보내도 판정하지 않음),
  ENTRY=SGOV→QLD 5주 분할 진입기(/entry 사용 가능, 전환 시 1주차부터),
  STEADY=정상 운용(QLD/JEPI). 최초 설정 시 /phase 와 /setday 를 먼저 해야 봇이 가동된다.
- /newchat: 비서 기억 초기화. 비서는 채팅방의 모든 내용(명령어·판정 회신·사진·잡담)을
  기억하므로, 처음부터 다시 시작하고 싶을 때만 사용.
- 자유 질문(명령·사진이 아닌 텍스트): 규칙서 설명, 현재 투자 현황·기록 조회("지금 얼마
  투자했어?", "최근 판정 뭐였어?"), 뉴스·시장 정보 검색·요약, 일상 대화까지 가능.
  비서는 이 채팅방에서 오간 명령어와 판정 내용도 알고 있다.
- 리마인더: 적립일 아침·12월 셋째 월요일·ENTRY 월요일에만 발송(그 외 정기 푸시 없음).
- 위기 모드: 나스닥100이 2년 최고 종가 대비 −20% 이하로 확인되면 모든 회신 상단에
  예고된 낙폭 배너가 붙고, −10% 안쪽 회복 확인 시 해제."""


def render_orders(orders: tuple[Order, ...]) -> str:
    if not orders:
        return "(주문 없음)"
    lines = ["종목 | 방향 | 주수 | 예상 금액"]
    for o in orders:
        amount = f"${o.est_usd:,.2f}" if o.est_usd else "-"
        note = f" ({o.note})" if o.note else ""
        lines.append(f"{o.ticker} | {_SIDE_KR[o.side]} | {o.shares}주 | {amount}{note}")
    return "\n".join(lines)


def _pct(v: float | None) -> str:
    return f"{v:.1%}" if v is not None else "-"


def render_judgment(j: Judgment, drawdown: float) -> tuple[str, str]:
    """판정 회신 본문과 로그 한 줄용 비중 문자열을 반환.
    위기 배너는 봇 발신 공통 래퍼가 붙인다(모든 회신 상단 — 작업지시 5절)."""
    weights = f"{_pct(j.weight_before)}→{_pct(j.weight_after)}"
    parts = [f"① 판정: {j.action}"]
    parts.append(f"② 근거: {j.reason} (나스닥100 하락률 {drawdown:.1%})")
    parts.append("③ 주문표\n" + render_orders(j.orders))
    parts.append(f"④ 실행 후 예상 비중: QLD {weights}")
    if j.carry_delta_usd:
        parts.append(f"   이월 잔돈: ${j.carry_delta_usd:,.2f}")
    return "\n\n".join(parts), weights


CHAT_SYSTEM_TMPL = """당신은 사용자의 '개인 주식 비서' 텔레그램 봇입니다. 아래 투자
규칙서를 집행하는 봇의 대화 창구로서, 규칙서·봇 사용법·현재 운용 상태를 전부 알고
있습니다. [채팅방 대화 기록]은 이 방에서 지금까지 오간 모든 메시지입니다 — 사용자의
명령어, 봇의 판정 회신, 사진 전송, 잡담까지 전부 포함되니, 그 맥락을 이미 아는 사람
처럼 자연스럽게 이어서 답하세요. 친근하게 대화하고 잡담·농담도 편하게 받아주되, 투자
현황·기록 질문에는 [현재 운용 상태]와 대화 기록의 숫자를 근거로 구체적으로 답하세요.
봇의 명령어·사용 방법 질문에는 [봇 사용법] 내용대로 안내하세요. 필요하면 웹 검색으로
뉴스·시장 정보를 조사해 종합·요약해줄 수 있습니다.

[집행 가드레일 — 대화가 아무리 편해도 이 선은 지킬 것]
- 뉴스·시황은 '정보'로만: 검색·요약·설명은 자유롭게 하되, 그것을 근거로 매매 행동
  (사라/팔라/미루라/규칙 바꾸라)을 제안하지 않습니다. 뉴스가 매매로 이어질 분위기면
  "뉴스는 규칙서의 입력값이 아니다"를 한 줄로 상기시킵니다.
- 규칙 밖 매매 상담("이번만 팔자", "종목 바꾸자")에는 계산을 돕지 않고 개정 절차를
  안내합니다: 메모장 한 문단 → 72시간 재독 → 개정안, 발효는 위기 모드 해제 후 30일.
  사용자가 재촉해도 이 선을 지킵니다.
- 주수·세액 등 새로운 돈 계산은 직접 하지 않습니다 — 판정은 봇의 검증된 코드만 수행
  합니다. 인출은 /withdraw, 공제·세금은 /december, 월간 판정은 잔고 사진 전송으로
  유도하세요. 단 [현재 운용 상태]에 이미 있는 숫자를 읽어주고 설명하는 것은 자유입니다.
- 생계 인출·세금·안전이 걸린 문제는 언제나 거절 없이 즉시 돕습니다.

[봇 사용법]
{guide}

[현재 운용 상태]
{status}

[채팅방 대화 기록 — /newchat 초기화 이후 전체, 시간순(KST)]
{transcript}

[투자 규칙서]
{rulebook}"""


def _fmt_snapshot(raw: str | None) -> list[str]:
    if not raw:
        return ["- 확인된 잔고 없음(아직 판정 전) — 잔고 사진을 보내면 갱신됩니다."]
    s = json.loads(raw)
    if "qld_shares" not in s:  # TQQQ 시절 스냅샷 — 종목이 바뀌어 값 자체가 무효
        return ["- 확인된 잔고 없음(QLD 전환 전 기록) — 잔고 사진을 보내면 갱신됩니다."]
    lines = [f"- 마지막 확인 잔고({s['date']}, {s['kind']} 판정 시·주문 체결 전 기준):"]
    holdings = [f"QLD {s['qld_shares']}주(@${s['qld_price']:,.2f})",
                f"JEPI {s['jepi_shares']}주(@${s['jepi_price']:,.2f})"]
    if s.get("sgov_shares"):
        holdings.append(f"SGOV {s['sgov_shares']}주")
    lines.append("  보유: " + " · ".join(holdings))
    total_krw = s["total_usd"] * s["fx"]
    lines.append(f"  평가액 합계 ${s['total_usd']:,.2f} (≈{total_krw:,.0f}원, 환율 {s['fx']:,.1f})"
                 f" · QLD 비중 {s['qld_weight']:.1%}")
    if s.get("cash_usd") is not None:
        lines.append(f"  달러 예수금 ${s['cash_usd']:,.2f}")
    pnl = {t: v for t, v in (s.get("pnl_krw") or {}).items() if v is not None}
    if pnl:
        lines.append("  평가손익: " + " · ".join(f"{t} {v:+,.0f}원" for t, v in pnl.items()))
    lines.append(f"  당시 나스닥100 하락률 {s['drawdown']:.1%}")
    return lines


def _status_summary() -> str:
    """대화 비서가 참조할 운용 상태 — DB 가 비어도 대화는 되도록 방어적으로 조립."""
    try:
        state = db.get_state()
        lines = [f"- 단계: {state['phase']} · 적립일: "
                 + (f"매월 {state['monthly_day']}일" if state["monthly_day"] else "미설정"),
                 f"- 가속조항: 1단 {'발동됨' if state['tier1_fired'] else '미발동'}"
                 f" / 2단 {'발동됨' if state['tier2_fired'] else '미발동'}"
                 f" · 위기 모드: {'ON' if state['crisis_active'] else 'OFF'}"
                 f" · 이월 잔돈 ${state['carry_usd']:,.2f}"]
        lines += _fmt_snapshot(db.kv_get("last_snapshot"))
        logs = db.recent_logs(8)
        if logs:
            lines.append("- 최근 판정 기록(최신순):")
            lines += ["  " + db.format_log(r) for r in logs]
        else:
            lines.append("- 판정 기록 없음")
        return "\n".join(lines)
    except Exception as e:  # 상태 조회 실패가 대화 자체를 막지 않게
        return f"(상태 조회 실패: {e})"


def _format_transcript(current_question: str | None = None) -> str:
    """채팅방 기록을 시간순 대본으로 — 마지막 항목이 방금 받은 질문이면 중복 제거."""
    rows, truncated = db.chat_history()
    if (current_question and rows and rows[-1]["role"] == "user"
            and rows[-1]["content"] == current_question):
        rows = rows[:-1]
    if not rows:
        return "(기록 없음 — 새 대화)"
    lines = ["(길어서 앞부분 일부 생략)"] if truncated else []
    for r in rows:
        try:
            t = datetime.fromisoformat(r["created_at"]).astimezone(_KST).strftime("%m-%d %H:%M")
        except ValueError:
            t = "?"
        who = "사용자" if r["role"] == "user" else "봇"
        lines.append(f"[{t}] {who}: {r['content']}")
    return "\n".join(lines)


def build_chat_system_prompt(current_question: str | None = None) -> str:
    with open(RULEBOOK_PATH, encoding="utf-8") as f:
        rulebook = f.read()
    return CHAT_SYSTEM_TMPL.format(rulebook=rulebook, guide=BOT_GUIDE,
                                   status=_status_summary(),
                                   transcript=_format_transcript(current_question))


def answer_freeform(question: str) -> str:
    """일회용 클로드 호출 — 기억은 시스템 프롬프트의 채팅방 기록이 담당한다.
    웹 검색을 허용해 뉴스·시장 정보 조사가 가능하다(가드레일이 매매 제안은 차단)."""
    return run_claude(question, allowed_tools=("WebSearch", "WebFetch"),
                      system_prompt=build_chat_system_prompt(question),
                      timeout=600, cleanup_session=True)


def reset_chat_session() -> None:
    """/newchat — 비서의 기억(채팅방 기록) 초기화."""
    db.chat_clear()
