"""시장 데이터 — 서버가 yfinance 로 직접 조회해 판정에 주입(작업지시 3절: 클로드 웹검색 의존 금지)."""
import pandas as pd
import yfinance as yf

NDX_WINDOW_DAYS = 504  # 최근 2년 거래일


def _closes(ticker: str, period: str) -> pd.Series:
    df = yf.download(ticker, period=period, interval="1d", progress=False, auto_adjust=False)
    if df is None or df.empty:
        raise RuntimeError(f"{ticker} 시세 조회 실패")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    closes = df["Close"].dropna()
    if closes.empty:
        raise RuntimeError(f"{ticker} 종가 없음")
    return closes


def ndx_drawdown() -> dict:
    """하락률 = 나스닥100 최신 종가 ÷ 최근 2년(504거래일) 최고 종가 − 1.
    판정은 종가로만(장중·월중 터치 무시 — 규칙서 사양)."""
    close = _closes("^NDX", "2y").tail(NDX_WINDOW_DAYS)
    latest = float(close.iloc[-1])
    peak = float(close.max())
    return {
        "latest_close": latest,
        "peak_close": peak,
        "drawdown": latest / peak - 1,
        "latest_date": str(close.index[-1].date()),
    }


def last_price(ticker: str) -> float:
    return float(_closes(ticker, "5d").iloc[-1])


def usdkrw() -> float:
    return float(_closes("KRW=X", "5d").iloc[-1])
