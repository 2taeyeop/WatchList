"""① 개장 전 뉴스·신호 다이제스트.

Claude API(웹검색 도구 포함)가 우리가 만든 프롬프트로 다이제스트를 생성해
텔레그램으로 보냅니다. 미국 개장 약 30분 전(예: 09:00 ET)에 실행하세요.

필요 환경변수: ANTHROPIC_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
"""
import os
from anthropic import Anthropic

from backend import db
from notify import send_telegram

PROMPT = """당신은 내 반도체·레버리지 ETF 투자 모니터링 어시스턴트입니다.
미국 증시 개장 전에, 어젯밤 미국장 마감(4 PM ET) 이후부터 오늘 프리마켓까지의
정보를 웹에서 검색해 종합하고, 한국어로 간결한 '개장 전 다이제스트'를 작성하세요.
나는 이걸 보고 개장(또는 개장 +30분)에 정규장에서 진입·관리를 판단합니다.

[내 상황/맥락 — 총평에 반영]
- 나는 공격적 성장 투자자. QLD·SSO·SMH(레버리지)와 매월 ISA 2배 나스닥 보유/적립.
- 2026년 8월에 약 1,500만원을 일괄(또는 분할) 진입 예정 → 시장 과열도·매크로가
  진입 판단에 직접 영향.
- 디리스킹 규칙: capex 감액 / 메모리 가격 하락 전환 / SMH 200일선 이탈 중
  2개 이상이면 QLD·SMH부터 현금·SSO로 축소.
- 진입 신호 규칙: 신호 양호=일괄 / 1개 경고=절반 / 2개 이상=대기.
- 감정·헤드라인이 아니라 '확인된 신호 변화'가 행동을 정하게 할 것.

[모니터링 대상 — 중요도 순]
1. 하이퍼스케일러 capex 가이던스(MS·구글·아마존·메타): 데이터센터·AI 투자
   증액/감액. 분기 실적 시즌 특히 주목.
2. 메모리 고정거래가격(TrendForce DRAM·HBM·NAND): 상승/횡보/하락(전분기 대비).
3. SMH 가격과 200일 이동평균선: 200일선 위/아래, 이격도(과열 여부).
4. TSMC 월간 매출(매월 10일경): 전년동월·전월 대비.
5. Fed 통화정책·금리 전망(CME FedWatch): 인하/인상 기대 변화.
6. 어젯밤~오늘 반도체·AI·매크로 주요 헤드라인(실적·가이던스·지표 서프라이즈).

[작성 형식]
- 맨 위 "오늘 핵심 변화" 2~3줄 요약.
- 신호 항목별: 최신 수치/뉴스 + 직전 대비 변화 + 한 줄 코멘트 + 출처.
- "디리스킹 신호등": 🟢/🟡/🔴 + 근거 한 줄.
  (capex 감액·메모리 하락 전환·SMH 200일선 이탈을 '경고'로 간주.)
- 변화 없는 항목은 "변화 없음"으로 짧게.

[마지막 — 총평 코멘트, 반드시 포함]
- 오늘 신호를 한 문장으로 종합.
- '신호'와 '소음' 구분: 큰 단일 급락/'버블' 헤드라인이 핵심 3신호를 실제로
  꺾었는지, 회복된 노이즈였는지 명시.
- '수준'이 아니라 '변화'(어제 대비)에 초점.
- 두 질문 분리: ① 디리스킹해야 하나(신호등) ② 오늘/8월 진입해도 되나(과열·밸류).
- 경계 요인이 쌓이면 '디리스킹 계획 장전 유지' 환기.
- 마지막에 '한 줄 결론'.

[주의] 사실·데이터만, 매수/매도 권유 금지. 수치엔 출처·날짜. 텔레그램에 보낼
것이므로 표·과한 마크다운 없이 줄글+불릿으로 간결하게.
"""


# 프론트 대시보드용 구조화 신호 추출 도구(강제 호출). prose 를 신호등/지표/결론으로 변환.
SIGNAL_TOOL = {
    "name": "record_signal",
    "description": "위 다이제스트를 대시보드용 구조화 신호로 기록한다.",
    "input_schema": {
        "type": "object",
        "properties": {
            "signal_light": {
                "type": "string", "enum": ["green", "yellow", "red"],
                "description": "디리스킹 신호등. 경고 2개 이상이면 red, 1개면 yellow, 없으면 green.",
            },
            "indicators": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "지표명(예: SMH 200일선)"},
                        "status": {"type": "string", "enum": ["ok", "caution", "alert", "na"]},
                        "value": {"type": "string", "description": "최신 수치/상태"},
                        "change": {"type": "string", "description": "직전 대비 변화"},
                        "comment": {"type": "string"},
                        "source": {"type": "string"},
                    },
                    "required": ["name", "status"],
                },
            },
            "conclusion": {"type": "string", "description": "한 줄 결론"},
        },
        "required": ["signal_light", "indicators", "conclusion"],
    },
}


def extract_signal(client: Anthropic, prose: str) -> dict:
    """prose 다이제스트를 구조화 신호로 변환(저렴한 모델로 강제 도구 호출)."""
    try:
        r = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1500,
            tools=[SIGNAL_TOOL],
            tool_choice={"type": "tool", "name": "record_signal"},
            messages=[{"role": "user",
                       "content": f"다음 다이제스트를 record_signal 로 구조화하라:\n\n{prose}"}],
        )
        for b in r.content:
            if getattr(b, "type", "") == "tool_use" and b.name == "record_signal":
                return b.input
    except Exception as e:  # 구조화 실패해도 prose 저장/발송은 진행
        print(f"신호 구조화 실패(무시): {e}")
    return {"signal_light": "unknown", "indicators": [], "conclusion": ""}


def main() -> None:
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 12}],
        messages=[{"role": "user", "content": PROMPT}],
    )
    text = "".join(
        b.text for b in resp.content if getattr(b, "type", "") == "text"
    ).strip()
    if not text:
        text = "(다이제스트 생성 실패 — 응답이 비어 있습니다.)"

    # 대시보드용 구조화 신호 추출 + DB 저장(베스트에포트: 실패해도 발송은 계속).
    sig = extract_signal(client, text)
    try:
        db.init_db()
        saved = db.save_digest(
            prose=text,
            signal_light=sig.get("signal_light", "unknown"),
            indicators=sig.get("indicators", []),
            conclusion=sig.get("conclusion", ""),
        )
        print(f"다이제스트 DB 저장 완료 ({saved}, 신호등={sig.get('signal_light')})")
    except Exception as e:
        print(f"DB 저장 실패(무시): {e}")

    send_telegram(text)
    print("다이제스트 발송 완료")


if __name__ == "__main__":
    main()
