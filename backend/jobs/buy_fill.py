"""분할매수 종가 채움 — buys 테이블에서 '구입했으나 매수단가(종가) 미기록'인
행을 yfinance 종가로 채운다. 미국장 마감 후 실행(외부호출이라 첫 실행 사용자 권장).

  python -m backend.jobs.buy_fill
"""
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

from backend import db


def _next_day(date: str) -> str:
    return (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")


def close_price(ticker: str, date: str) -> float | None:
    """date(YYYY-MM-DD)의 종가. 휴장/미반영이면 None.
    당일 봉을 포함하도록 [date, date+1) 범위로 받는다."""
    df = yf.download(ticker, start=date, end=_next_day(date), interval="1d",
                     progress=False, auto_adjust=True)
    if df is None or len(df) == 0:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return float(df["Close"].iloc[-1])


def main() -> None:
    db.init_db()
    pending = db.buys_missing_price()
    if not pending:
        print("종가 채울 매수 없음")
        return
    filled = 0
    for b in pending:
        try:
            px = close_price(b["ticker"], b["date"])
            if px is not None:
                db.fill_buy_price(b["date"], b["ticker"], px)
                filled += 1
                print(f"{b['date']} {b['ticker']} ← ${px:,.2f}")
            else:
                print(f"{b['date']} {b['ticker']}: 종가 없음(휴장?) — 건너뜀")
        except Exception as e:  # 한 종목 실패가 전체를 막지 않게
            print(f"{b['date']} {b['ticker']}: {e}")
    print(f"채움 {filled}/{len(pending)}")


if __name__ == "__main__":
    main()
