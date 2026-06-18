"""종목 기본정보 조회(yfinance) — 검색 1단계. 티커/영문명/한국코드를 심볼로 해석하고
현재가·등락률을 빠르게 가져온다(무료·결정적, Claude 무관).

한글 종목명은 Yahoo 검색이 약해 빈 결과가 나온다 → 코드(예: 005930)나 영문명으로
입력해야 해석됨. 해석 실패 시 None(프론트는 '바로 분석하기'로 Claude 에 맡김).
"""
import yfinance as yf


def _has_price(symbol: str) -> bool:
    try:
        return yf.Ticker(symbol).fast_info.get("lastPrice") is not None
    except Exception:
        return False


def _resolve(query: str) -> tuple[str, str]:
    """query → (symbol, name). 해석 실패 시 ('', '')."""
    q = query.strip()
    if not q:
        return "", ""
    # 1) Yahoo 검색(영문명·티커·한국 6자리코드)
    try:
        for x in yf.Search(q, max_results=5).quotes:
            if x.get("quoteType") in ("EQUITY", "ETF") and x.get("symbol"):
                return x["symbol"], (x.get("shortname") or x.get("longname") or "")
    except Exception:
        pass
    # 2) 한국 6자리 코드 직접(.KS=코스피, .KQ=코스닥)
    if q.isdigit() and len(q) == 6:
        for suf in (".KS", ".KQ"):
            if _has_price(q + suf):
                return q + suf, ""
    # 3) 심볼 그대로
    if _has_price(q.upper()):
        return q.upper(), ""
    return "", ""


def lookup(query: str) -> dict | None:
    """query → {ticker, name, market, price, change_pct, currency} 또는 None."""
    symbol, name = _resolve(query)
    if not symbol:
        return None
    try:
        fi = yf.Ticker(symbol).fast_info
    except Exception:
        return None
    last = fi.get("lastPrice")
    prev = fi.get("previousClose")
    currency = fi.get("currency") or ""
    change = (last / prev - 1) * 100 if last and prev else None
    market = "KR" if currency == "KRW" else "US"
    return {
        # 표시는 한국=코드(005930), 그 외=심볼(NVDA). 분석하기도 이 값으로 넘긴다.
        "ticker": symbol.split(".")[0] if market == "KR" else symbol,
        "name": name,
        "market": market,
        "price": last,
        "change_pct": change,
        "currency": currency,
    }
