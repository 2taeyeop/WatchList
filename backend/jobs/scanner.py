"""② 반등 조짐 스캐너 (watchlist 밖 종목).

종목 유니버스를 기술적 '반등' 조건으로 스크리닝하고, 후보가 있을 때만 텔레그램
알림을 보냅니다(없으면 발송 안 함 = 트리거형). 미국장 마감 후(예: 16:05 ET)에 실행.

판정 파이프라인(노이즈를 줄이고 '진짜 반등'만 잡도록 설계):
  A) 약세 게이트 — 최근 약했던(추세선 아래/RSI 저조/고점 대비 하락) 종목만 후보 대상.
     → 강세주가 '반등'으로 둔갑하는 것을 막는다.
  B) 강도 정렬  — 약세 게이트가 1차 노이즈 필터라, 게이트 통과 + 신호 1개면 후보.
     표시는 강신호(200일선 회복·RSI 과매도 반등) > 다중 신호 > 단일 신호 순으로 정렬.
  C) 휩쏘 버퍼   — 이동평균 회복은 'MA 위 +0.5% 마감'을 요구해 가짜 돌파를 거른다.
  D) RSI         — Wilder 평활(TradingView 기본과 동일).
  E) 거래량 기준 — 직전 20일 평균(당일 제외)과 비교.

필요 환경변수: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
데이터: yfinance(무료). 안정성이 중요하면 Polygon/Finnhub 등 유료 API로 교체 권장.
"""
import pandas as pd
import yfinance as yf

from backend import db
from backend.notify import send_telegram

# 스캔 유니버스 — 자유롭게 편집(반도체 + 메가테크를 출발점으로).
UNIVERSE = [
    "NVDA", "AVGO", "AMD", "MU", "MRVL", "TSM", "ASML", "LRCX", "AMAT", "KLAC",
    "INTC", "QCOM", "ARM", "SMCI", "ANET", "DELL", "MSFT", "GOOGL", "AMZN",
    "META", "AAPL", "ORCL", "PLTR", "CRWD", "NOW", "TXN", "ADI", "ON",
]

# --- 튜닝 파라미터 ---
LOOKBACK = 10        # 약세 판단 기간(거래일)
MA_BUFFER = 0.005    # 이동평균 회복 확인 버퍼(0.5% 위 마감)
VOL_MULT = 1.8       # 거래량 급증 배수(직전 20일 평균 대비)
PULLBACK = 0.10      # 6개월 고점 대비 -10% 이상이면 '약세'로 간주
RSI_LOW = 40         # 최근 RSI 가 이 아래로 내려간 적 있으면 '약세'
HIGH_WINDOW = 126    # 고점 비교 창(≈6개월 거래일)
# 단독으로도 알림 가능한 '강신호'(진짜 반등 의미가 큰 것). 나머지는 confluence 전용.
STRONG = {"200일선 회복", "RSI 과매도 반등"}


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder 평활 RSI (RMA = ewm alpha=1/period). 대부분 차트의 기본 RSI 와 일치."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-9)
    return 100 - 100 / (1 + rs)


def _base(reason: str) -> str:
    """'RSI 과매도 반등(31)' → 'RSI 과매도 반등' (괄호 수치 제거)."""
    return reason.split("(")[0].strip()


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
    avg_vol = vol.shift(1).rolling(20).mean()  # 직전 20일(당일 제외)

    price = float(close.iloc[-1])
    prev = float(close.iloc[-2])

    # --- A) 약세 게이트: 최근 LOOKBACK일에 '약했던' 적이 있어야 반등 후보로 본다 ---
    recent = slice(-LOOKBACK - 1, -1)  # 오늘 제외한 직전 LOOKBACK 봉
    high_6m = float(close.iloc[-HIGH_WINDOW:].max())
    was_weak = (
        bool((close.iloc[recent] < ma50.iloc[recent]).any())
        or bool((close.iloc[recent] < ma200.iloc[recent]).any())
        or bool((r.iloc[recent] < RSI_LOW).any())
        or price < high_6m * (1 - PULLBACK)
    )
    if not was_weak:
        return None

    reasons = []
    # ① 200일선 회복(어제 아래 → 오늘 +0.5% 위)
    if prev < ma200.iloc[-2] and price > ma200.iloc[-1] * (1 + MA_BUFFER):
        reasons.append("200일선 회복")
    # ② 50일선 회복(어제 아래 → 오늘 +0.5% 위)
    if prev < ma50.iloc[-2] and price > ma50.iloc[-1] * (1 + MA_BUFFER):
        reasons.append("50일선 회복")
    # ③ RSI 과매도(<30)에서 반등
    if r.iloc[-2] < 30 <= r.iloc[-1]:
        reasons.append(f"RSI 과매도 반등({r.iloc[-1]:.0f})")
    # ④ 상승일 거래량 급증
    if price > prev and vol.iloc[-1] > VOL_MULT * avg_vol.iloc[-1]:
        reasons.append("거래량 급증(상승)")

    if not reasons:
        return None

    chg = (price / prev - 1) * 100
    return ticker, price, chg, reasons


def main() -> None:
    hits = []
    for t in UNIVERSE:
        try:
            res = scan_one(t)
            if res:
                hits.append(res)
        except Exception as e:  # 한 종목 실패가 전체를 막지 않게
            print(f"{t}: {e}")

    # 강도순 정렬: 강신호 포함 > 신호 수 많은 순
    hits.sort(key=lambda h: (any(_base(x) in STRONG for x in h[3]), len(h[3])), reverse=True)

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
