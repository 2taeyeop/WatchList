"""④ 보유 ETF 구성종목 최신 뉴스(양방향 감성) — 분할매수 페이스 보정용.

내 ETF(SMH 반도체 / QLD 2x 나스닥100 / SSO 2x S&P500)의 핵심 구성종목을 정해,
Claude Code(`claude -p`, 구독 인증) 웹검색으로 각 종목의 '주가에 의미 있는 최신 뉴스'를
호재/악재/중립으로 판정한다. 결과는 대시보드(보유종목 탭)와 분할매수 페이스 보정에 쓰인다.

- 텔레그램 발송 없음(대시보드 전용 신호). 개장 전(다이제스트와 함께) 실행 권장.
- 비용: Claude 구독(Max 등) 한도 차감 — 별도 API 종량 과금 없음(run_claude 가 강제).
- 필요: Claude Code 구독 인증(CLAUDE_CODE_OAUTH_TOKEN/로그인).
"""
import json

from backend import db
from backend.jobs.digest import run_claude  # 구독 인증 claude -p 호출 재사용

# 내 ETF를 움직이는 핵심 구성종목(반도체=SMH, 메가캡=QLD/SSO). 비용 위해 상위만.
MONITOR = [
    "NVDA", "AVGO", "AMD", "TSM", "MU", "ASML", "QCOM", "ARM",  # 반도체(SMH)
    "AAPL", "MSFT", "GOOGL", "AMZN", "META",                    # 메가캡(QLD/SSO)
]
_MONITOR_SET = set(MONITOR)

PROMPT_TMPL = """당신은 내 보유 ETF(SMH 반도체 / QLD 2x 나스닥100 / SSO 2x S&P500)의
핵심 구성종목을 모니터링하는 어시스턴트입니다. 아래 각 종목에 대해 최근 24~48시간
(어젯밤 미국장 마감~오늘 프리마켓)의 '주가에 의미 있는 최신 뉴스'를 웹에서 검색해,
그 뉴스가 해당 종목 주가에 호재/악재/중립 중 무엇인지 판정하세요.

[판정 기준]
- positive: 실적·가이던스 상향, 대형 수주·승인, 목표가/투자의견 상향 등 명확한 호재
- negative: 실적·가이던스 하향, 규제·소송·리콜, 목표가 하향, 공급 차질 등 명확한 악재
- neutral: 의미 있는 뉴스 없음 또는 호악재가 혼재/불명확
사실·출처 기반, 과장 금지. 의미 있는 뉴스가 없으면 neutral.

[종목]
{tickers}

[출력 — 순수 JSON 배열 하나만, 마크다운/설명 없이]
[{{"ticker": "TICKER", "sentiment": "positive|neutral|negative",
   "headline": "핵심 뉴스 한 줄(+매체)", "source": "URL"}}]
위 종목을 각각 1개 항목으로 모두 채우세요(neutral 포함)."""


def parse_arr(text: str) -> list[dict]:
    """결과 텍스트에서 JSON 배열만 추출."""
    if "[" not in text or "]" not in text:
        return []
    raw = text[text.find("["):text.rfind("]") + 1]
    try:
        arr = json.loads(raw)
    except Exception as e:
        print(f"뉴스 JSON 파싱 실패(무시): {e}")
        return []
    return arr if isinstance(arr, list) else []


_VALID = {"positive", "neutral", "negative"}


def main() -> None:
    db.init_db()
    tickers = "\n".join(f"- {t}" for t in MONITOR)
    print(f"구성종목 뉴스 검토: {', '.join(MONITOR)}")

    found = parse_arr(run_claude(PROMPT_TMPL.format(tickers=tickers)))

    # 환각 티커/잘못된 감성 방어 + 종목당 1개로 dedupe.
    items, seen = [], set()
    for f in found:
        t = str(f.get("ticker", "")).upper()
        if t not in _MONITOR_SET or t in seen:
            continue
        seen.add(t)
        sent = str(f.get("sentiment", "neutral")).lower()
        if sent not in _VALID:
            sent = "neutral"
        items.append({
            "ticker": t, "sentiment": sent,
            "headline": f.get("headline", ""), "source": f.get("source", ""),
        })

    try:
        saved = db.save_holdings_news(items)
        pos = sum(1 for it in items if it["sentiment"] == "positive")
        neg = sum(1 for it in items if it["sentiment"] == "negative")
        print(f"구성종목 뉴스 DB 저장 ({saved}, {len(items)}개 · 호재 {pos} / 악재 {neg})")
    except Exception as e:
        print(f"DB 저장 실패(무시): {e}")


if __name__ == "__main__":
    main()
