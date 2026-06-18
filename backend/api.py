"""FastAPI — 대시보드용 읽기 + 검색/매수 쓰기 API.

파이프라인이 저장한 SQLite(backend.db)를 읽어 JSON으로 제공한다. 대부분 읽기지만,
검색(기술분석 즉시 실행·캐시)과 매수추적 기록은 프론트에서 직접 쓰므로 POST 를 받는다.
뉴스 검색 분석은 Claude 구독을 쓰는 ticker_analyze 잡(사용자 실행)이 채우고, 여기선
캐시만 조회한다(API 에서 Claude 직접호출 안 함). nginx 가 정적 프론트와 함께 /api 를
이 앱(uvicorn :8000)으로 프록시한다.

개발 서버:  uvicorn backend.api:app --reload
"""
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend import db
from backend.jobs import quote, ticker_search

app = FastAPI(title="WatchList API", version="1.0")

# 로컬 개발 시 Vite(기본 5173)에서의 호출 허용. 운영은 nginx 동일 출처라 CORS 불필요.
# WATCHLIST_CORS_ORIGINS="https://watch.example.com" 처럼 콤마로 추가 지정 가능.
_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
_extra = os.environ.get("WATCHLIST_CORS_ORIGINS", "").strip()
if _extra:
    _origins += [o.strip() for o in _extra.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class SearchIn(BaseModel):
    query: str  # 티커 또는 종목명(한국·미국장)


class BuyIn(BaseModel):
    ticker: str
    amount: float
    bought: bool = True
    date: str | None = None  # 없으면 ET 거래일
    price: float | None = None  # 매수단가(직접 입력, 없으면 buy_fill 잡이 채움)


@app.on_event("startup")
def _startup() -> None:
    db.init_db()  # DB 파일/스키마 없으면 생성(빈 상태로 API 가 떠도 200)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.get("/api/dates")
def dates() -> list[dict]:
    """사이드바/달력용 — 날짜 + 신호등 + 스캔 후보 수(최신순)."""
    return db.list_dates()


@app.get("/api/digests/latest")
def digest_latest() -> dict | None:
    return db.latest_digest()


@app.get("/api/digests/{date}")
def digest_by_date(date: str) -> dict:
    d = db.get_digest(date)
    if d is None:
        raise HTTPException(status_code=404, detail=f"{date} 다이제스트 없음")
    return d


@app.get("/api/scans/{date}")
def scans_by_date(date: str) -> list[dict]:
    return db.get_scans(date)


@app.get("/api/news-scans/{date}")
def news_scans_by_date(date: str) -> list[dict]:
    """뉴스 반등 후보(약세+하락 종목 중 호재)."""
    return db.get_news_scans(date)


@app.get("/api/holdings-news/{date}")
def holdings_news_by_date(date: str) -> list[dict]:
    """내 ETF 구성종목 최신 뉴스(양방향 감성) — 분할매수 페이스 보정용."""
    return db.get_holdings_news(date)


# ── 검색 분석 ──
@app.get("/api/quote")
def quote_lookup(q: str) -> dict:
    """검색 1단계 — yfinance 기본정보(티커/영문명/한국코드 해석 + 현재가). Claude 무관."""
    res = quote.lookup(q)
    if not res:
        raise HTTPException(
            status_code=404,
            detail=f"'{q}' 기본정보를 찾지 못했습니다(코드/영문명으로 시도하거나 바로 분석하기)",
        )
    return res


@app.post("/api/search")
def search(body: SearchIn) -> dict:
    """검색어(한국·미국장) → Claude 웹검색 분석 → 저장(날짜별 누적) → 반환.
    ⚠️ 호출당 Claude 구독으로 웹검색(수십 초 지연)."""
    q = (body.query or "").strip()
    if not q:
        raise HTTPException(status_code=400, detail="검색어가 비었습니다")
    res = ticker_search.analyze(q)
    if not res or not str(res.get("ticker", "")).strip():
        detail = (res or {}).get("summary") or f"'{q}' 종목을 특정하지 못했습니다"
        raise HTTPException(status_code=404, detail=detail)
    ticker = str(res["ticker"]).strip().upper()
    date = db.save_search(
        ticker, name=res.get("name", ""), market=res.get("market", ""),
        price=res.get("price"), change_pct=res.get("change_pct"),
        summary=res.get("summary", ""), catalyst=res.get("catalyst", ""),
        view=res.get("view", ""), sentiment=res.get("sentiment", "neutral"),
        sources=res.get("sources", []),
    )
    rows = db.get_searches(ticker)
    return next((r for r in rows if r["date"] == date), rows[0] if rows else {})


@app.get("/api/searches")
def searches() -> list[dict]:
    """저장된 모든 검색 분석(티커별·날짜별 누적) — '저장된 데이터 보기'용."""
    return db.list_searches()


# ── 분할매수 추적 ──
@app.get("/api/buys")
def buys(date: str | None = None) -> list[dict]:
    """date 지정 시 그날 매수, 없으면 전체(그래프/누적용)."""
    return db.get_buys(date) if date else db.list_buys()


@app.post("/api/buys")
def record_buy(body: BuyIn) -> dict:
    """그날·종목 매수 기록(구입/미구입 + 매수단가)."""
    db.record_buy(body.ticker, body.amount, bought=body.bought,
                  date=body.date, price=body.price)
    return {"ok": True}
