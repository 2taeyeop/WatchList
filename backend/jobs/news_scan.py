"""③ 뉴스 반등 후보 (약세 + 전일 하락 종목 중 '호재 뉴스'로 반등 가능성).

기술 스캐너(scanner.py)와 별개. yfinance 로 '약세(50/200일선 아래) + 전일 하락' 종목을
추린 뒤, Claude Code(`claude -p`, 구독 인증) 웹검색으로 각 종목의 최근 호재를 검토해
'반등 촉매가 확인된' 종목만 고른다. 개장 전(다이제스트와 함께) 실행 권장.

비용: Claude 구독(Max 등) 한도 차감 — 별도 API 종량 과금 없음(run_claude 가 강제).
필요: Claude Code 구독 인증(CLAUDE_CODE_OAUTH_TOKEN/로그인), TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID.
"""
import json

import pandas as pd
import yfinance as yf

from backend import db
from backend.jobs.digest import run_claude  # 구독 인증 claude -p 호출 재사용
from backend.notify import send_telegram
from backend.jobs.scanner import UNIVERSE

MAX_TICKERS = 12  # 뉴스 검토 상한(비용 방어)


def find_dropped() -> list[tuple[str, float]]:
    """약세(50일선 또는 200일선 아래) + 전일 하락 종목 → [(ticker, 전일등락률%)]."""
    out = []
    for t in UNIVERSE:
        try:
            df = yf.download(t, period="1y", interval="1d",
                             progress=False, auto_adjust=True)
            if df is None or len(df) < 200:
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            close = df["Close"]
            ma50 = close.rolling(50).mean()
            ma200 = close.rolling(200).mean()
            price = float(close.iloc[-1])
            prev = float(close.iloc[-2])
            weak = price < ma50.iloc[-1] or price < ma200.iloc[-1]
            dropped = price < prev
            if weak and dropped:
                out.append((t, (price / prev - 1) * 100))
        except Exception as e:  # 한 종목 실패가 전체를 막지 않게
            print(f"{t}: {e}")
    return out


PROMPT_TMPL = """당신은 내 투자 모니터링 어시스턴트입니다. 아래는 '최근 약세 + 전일 하락'한
미국 종목들입니다. 각 종목에 대해 최근 24~48시간(어젯밤~오늘 프리마켓) 뉴스를 웹에서
검색해, '반등을 만들 만한 실제 호재(촉매)'가 있는 종목만 선별하세요.

[호재 예시] 실적 서프라이즈·가이던스 상향, 애널리스트 목표가/투자의견 상향, 대형 수주·계약·
파트너십, 신제품/규제 호재, 업종 전반 강세 전환 등. 일반론·약한 재료는 제외하고 '확인된
구체 촉매'만. 호재가 없으면 그 종목은 빼세요. 과장 금지, 사실·출처 기반.

[검토 종목] (티커: 전일 등락률)
{tickers}

[출력 — 순수 JSON 배열 하나만, 마크다운/설명 없이]
[{{"ticker": "TICKER", "catalyst": "호재 한두 줄 요약(+출처 매체)", "view": "반등 관점 한 줄",
   "confidence": "high|medium|low"}}]
호재 있는 종목이 하나도 없으면 [] 만 출력하세요."""


def parse_news(text: str) -> list[dict]:
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


def main() -> None:
    dropped = find_dropped()
    db.init_db()

    if not dropped:
        print("약세+하락 종목 없음 — 뉴스 검토 생략")
        db.save_news_scans([])  # 그날 기록 비움
        return

    dropped = dropped[:MAX_TICKERS]
    drop_map = {t: c for t, c in dropped}
    tickers = "\n".join(f"- {t}: {c:+.1f}%" for t, c in dropped)
    print(f"약세+하락 {len(dropped)}개 → 뉴스 검토: {', '.join(drop_map)}")

    found = parse_news(run_claude(PROMPT_TMPL.format(tickers=tickers)))

    # Claude 결과를 우리 하락 목록과 대조(환각 티커·수치 방어). change_pct 는 실제 yfinance 값 사용.
    items = []
    for f in found:
        t = str(f.get("ticker", "")).upper()
        if t not in drop_map:
            continue
        items.append({
            "ticker": t, "change_pct": drop_map[t],
            "catalyst": f.get("catalyst", ""), "view": f.get("view", ""),
            "confidence": f.get("confidence", ""), "sources": f.get("sources", []),
        })

    try:
        saved = db.save_news_scans(items)
        print(f"뉴스 반등 후보 DB 저장 ({saved}, {len(items)}개)")
    except Exception as e:
        print(f"DB 저장 실패(무시): {e}")

    if not items:
        print("호재 있는 반등 후보 없음 — 알림 생략")
        return

    conf_kr = {"high": "확신 높음", "medium": "중간", "low": "낮음"}
    msg = ["📰 뉴스 반등 후보 (약세+하락 → 호재)", ""]
    for it in items:
        c = conf_kr.get(it["confidence"], it["confidence"])
        msg.append(f"• {it['ticker']} ({it['change_pct']:+.1f}%) [{c}]\n  {it['catalyst']}")
    msg += ["", "※ 매수 권유 아님. 뉴스 기반 관찰 후보 — 직접 확인 필요."]
    send_telegram("\n".join(msg))
    print(f"뉴스 반등 후보 {len(items)}개 발송")


if __name__ == "__main__":
    main()
