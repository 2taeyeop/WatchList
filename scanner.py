"""② 반등 조짐 스캐너 (watchlist 밖 종목).

종목 유니버스를 기술적 반등 조건으로 스크리닝하고, 후보가 있을 때만 텔레그램
알림을 보냅니다(없으면 발송 안 함 = 트리거형). 미국장 마감 후(예: 16:05 ET)에
실행하세요.

필요 환경변수: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
데이터: yfinance(무료). 안정성이 중요하면 Polygon/Finnhub 등 유료 API로 교체 권장.
"""
import pandas as pd
import yfinance as yf

from backend import db
from notify import send_telegram

# 스캔 유니버스 — 자유롭게 편집(반도체 + 메가테크를 출발점으로).
UNIVERSE = [
    "NVDA", "AVGO", "AMD", "MU", "MRVL", "TSM", "ASML", "LRCX", "AMAT", "KLAC",
    "INTC", "QCOM", "ARM", "SMCI", "ANET", "DELL", "MSFT", "GOOGL", "AMZN",
    "META", "AAPL", "ORCL", "PLTR", "CRWD", "NOW", "TXN", "ADI", "ON",
]


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, 1e-9)
    return 100 - 100 / (1 + rs)


def scan_one(ticker: str):
    df = yf.download(ticker, period="1y", interval="1d",
                     progress=False, auto_adjust=True)
    if df is None or len(df) < 200:
        return None
    if isinstance(df.columns, pd.MultiIndex):  # 단일 티커도 가끔 MultiIndex
        df.columns = df.columns.get_level_values(0)

    close = df["Close"]
    vol = df["Volume"]
    ma50 = close.rolling(50).mean()
    ma200 = close.rolling(200).mean()
    r = rsi(close)

    price = float(close.iloc[-1])
    prev = float(close.iloc[-2])
    reasons = []

    # 1) 200일선 회복(하락추세 → 추세 복원)
    if prev < ma200.iloc[-2] and price > ma200.iloc[-1]:
        reasons.append("200일선 회복")
    # 2) 50일선 회복
    if prev < ma50.iloc[-2] and price > ma50.iloc[-1]:
        reasons.append("50일선 회복")
    # 3) RSI 과매도(<30)에서 반등
    if r.iloc[-2] < 30 <= r.iloc[-1]:
        reasons.append(f"RSI 과매도 반등({r.iloc[-1]:.0f})")
    # 4) 상승일 거래량 급증
    avg_vol = vol.rolling(20).mean().iloc[-1]
    if price > prev and vol.iloc[-1] > 1.8 * avg_vol:
        reasons.append("거래량 급증(상승)")

    if reasons:
        chg = (price / prev - 1) * 100
        return ticker, price, chg, reasons
    return None


def main() -> None:
    hits = []
    for t in UNIVERSE:
        try:
            res = scan_one(t)
            if res:
                hits.append(res)
        except Exception as e:  # 한 종목 실패가 전체를 막지 않게
            print(f"{t}: {e}")

    # 대시보드용 DB 저장(베스트에포트). 빈 결과면 그날 기록을 비워 재실행 시 깔끔.
    try:
        db.init_db()
        saved = db.save_scans(hits)
        print(f"스캔 결과 DB 저장 완료 ({saved}, {len(hits)}건)")
    except Exception as e:
        print(f"DB 저장 실패(무시): {e}")

    if not hits:
        print("반등 후보 없음 — 알림 생략")
        return

    lines = ["📈 반등 조짐 스캔 (watchlist 밖)", ""]
    for t, price, chg, reasons in hits:
        lines.append(f"• {t}  ${price:,.2f} ({chg:+.1f}%) — {', '.join(reasons)}")
    lines += ["", "※ 매수 권유가 아니라 '관찰 후보'입니다. 직접 확인 필요."]
    send_telegram("\n".join(lines))
    print(f"반등 후보 {len(hits)}개 발송")


if __name__ == "__main__":
    main()
