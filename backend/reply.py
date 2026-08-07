"""회신 조립 — 판정 숫자는 코드가 그대로 렌더한다(클로드가 숫자를 만지지 못하게).

클로드는 자유 질문(명령어도 사진도 아닌 텍스트)에만 쓰고, 그 경로에도
규칙서(prompts/rulebook.md) + 봇 인격 가드레일(작업지시 6절)을 강제한다.
"""
import os

from backend.claude_runner import run_claude
from backend.rules import Judgment, Order

RULEBOOK_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts", "rulebook.md")

CRISIS_BANNER = ("⚠️ 이 낙폭은 설계 시 예고된 숫자입니다 (-50%는 사실상 확정 이벤트, "
                 "TQQQ 줄 -80%는 확률 77%). 허용 행동은 셋: 적립 매수 / 가속 실행 / 무행동.")

REVISION_NOTICE = ("규칙 밖 매매는 계산을 돕지 않습니다. 개정 절차를 따르세요:\n"
                   "메모장 한 문단 → 72시간 재독 → 개정안 작성, 발효는 위기 모드 해제 후 30일.")

_SIDE_KR = {"SELL": "매도", "BUY": "매수"}

# 명령어 요약 — /help 회신과 자유 질문 지식원이 같은 원본을 쓰게 여기 한 곳에만 둔다.
USAGE = """사용법
잔고 스크린샷(토스)만 보내면 월간 루틴 판정(/monthly 와 동일)

/monthly — 월간 적립 판정
/entry — 진입기 주간 루틴(SGOV→TQQQ)
/december — 12월 리밸런싱 + 공제·손실 수확
/withdraw <원화금액> — 생계 인출(즉시 협조)
/log — 최근 기록 10줄
/setday <일> — 적립일 설정
/phase <SETUP|ENTRY|STEADY> — 단계 전환"""

# 자유 질문용 봇 자체 설명 — 규칙서에는 없는 명령어·플로우 지식(이게 빠지면
# 봇이 자기 명령어를 설명 못 한다).
BOT_GUIDE = """- 잔고 스크린샷 전송: 수치 추출 → 확인 게이트([✅ 맞음]/[❌ 다시]) → ✅ 시
  판정·주문표·기록 로그 회신. 명령 없이 사진만 보내면 월간 루틴(/monthly)으로 처리.
- /monthly: 월간 적립 판정. 달러 예수금 전액으로 TQQQ 비중<70%면 TQQQ, 아니면 JEPI 내림 매수.
- /entry: 진입기(ENTRY) 주간 루틴. 이번 주차 SGOV 매도(5주 분할, 5주차 전량) → TQQQ 매수.
  5회 완료 시 STEADY 자동 전환.
- /december: 12월 셋째 월요일 리밸런싱 + 공제·손실 수확. 먼저 올해 실현손익 합계를
  숫자로 입력한 뒤 스크린샷을 보낸다. 가속 발동 연도는 자동 스킵.
- /withdraw <원화금액>: 생계 인출 — 70:30 금액 비율 매도 주수와 예상 실현손익 보고. 양수만.
- /log: 최근 기록 10줄. 형식 `날짜 | 행동 | 하락률 | 비중 전→후 | 메모`.
- /setday <일>: 매월 적립일 설정(1~31). 해당 일이 없는 달은 말일에 리마인더.
- /phase <SETUP|ENTRY|STEADY>: 운용 단계 전환 — SETUP=가동 전(사진을 보내도 판정하지 않음),
  ENTRY=SGOV→TQQQ 5주 분할 진입기(/entry 사용 가능, 전환 시 1주차부터),
  STEADY=정상 운용(TQQQ/JEPI). 최초 설정 시 /phase 와 /setday 를 먼저 해야 봇이 가동된다.
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
    parts.append(f"④ 실행 후 예상 비중: TQQQ {weights}")
    if j.carry_delta_usd:
        parts.append(f"   이월 잔돈: ${j.carry_delta_usd:,.2f}")
    return "\n\n".join(parts), weights


FREEFORM_TMPL = """당신은 아래 투자 규칙서의 '집행 보조' 텔레그램 봇입니다. 규칙서 내용과
봇 사용법에 근거해 사용자의 질문에 답하세요. 봇의 명령어·단계·사용 방법에 대한 질문에는
[봇 사용법] 내용대로 정확히 안내하세요.

[봇 인격 가드레일 — 반드시 지킬 것]
- 시황 전망·매매 타이밍 의견·뉴스 언급 금지. 물어도 "규칙서의 입력값이 아닙니다"라고
  답하고 계산으로 복귀합니다.
- 규칙 밖 매매 요청("이번만 팔자", "종목 바꾸자")에는 계산을 돕지 않고 개정 절차를
  안내합니다: 메모장 한 문단 → 72시간 재독 → 개정안, 발효는 위기 모드 해제 후 30일.
  사용자가 재촉해도 이 선을 지킵니다.
- 단, 생계 인출·세금·안전이 걸린 문제는 거절하지 않고 즉시 돕습니다. '돕는다'는
  해당 명령 절차로 바로 연결한다는 뜻입니다: 인출 계산은 /withdraw <원화금액>,
  공제·세금 계산은 /december 로 안내하세요.
- 주수·세액·금액 등 숫자 산출은 직접 계산하지 마세요 — 돈 계산은 봇의 검증된
  코드만 수행합니다. 규칙 설명은 하되 구체 수치 계산은 명령어로 유도합니다.
- 회신은 간결하게: 표와 숫자 중심, 설교 금지.

[봇 사용법]
{guide}

[투자 규칙서]
{rulebook}

[사용자 질문]
{question}"""


def build_freeform_prompt(question: str) -> str:
    with open(RULEBOOK_PATH, encoding="utf-8") as f:
        rulebook = f.read()
    return FREEFORM_TMPL.format(rulebook=rulebook, guide=BOT_GUIDE, question=question)


def answer_freeform(question: str) -> str:
    return run_claude(build_freeform_prompt(question), timeout=300)
