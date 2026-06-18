"""SQLite 저장소 — 다이제스트/스캔 결과를 날짜별로 보관.

- 파이프라인(digest.py / scanner.py)이 결과를 여기에 저장하고,
- FastAPI(api.py)가 같은 파일을 읽어 프론트로 제공합니다.

DB 파일 경로는 환경변수 WATCHLIST_DB 로 바꿀 수 있고, 기본값은 data/watchlist.db
(data/ 는 .gitignore 로 커밋 제외). 동시 읽기/간헐적 쓰기에 안전하도록 WAL 모드.
"""
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

_DEFAULT_PATH = os.path.join("data", "watchlist.db")
_ET = ZoneInfo("America/New_York")


def db_path() -> str:
    return os.environ.get("WATCHLIST_DB", _DEFAULT_PATH)


def trading_day() -> str:
    """미국 동부 기준 오늘 날짜(YYYY-MM-DD). 다이제스트는 개장 전, 스캐너는
    마감 후 실행되므로 둘 다 '그날 ET 날짜'로 묶입니다."""
    return datetime.now(_ET).strftime("%Y-%m-%d")


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connect():
    path = db_path()
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS digests (
                date         TEXT PRIMARY KEY,   -- YYYY-MM-DD (ET 거래일)
                created_at   TEXT NOT NULL,      -- 저장 시각(UTC ISO)
                prose        TEXT NOT NULL,      -- 한국어 다이제스트 전문
                signal_light TEXT,               -- 'green' | 'yellow' | 'red' | 'unknown'
                indicators   TEXT,               -- JSON 배열 [{name,status,value,change,comment,source}]
                conclusion   TEXT                -- 한 줄 결론
            );
            CREATE TABLE IF NOT EXISTS scans (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                date       TEXT NOT NULL,        -- YYYY-MM-DD (ET 거래일)
                created_at TEXT NOT NULL,
                ticker     TEXT NOT NULL,
                price      REAL,
                change_pct REAL,
                reasons    TEXT,                 -- JSON 배열(반등 사유)
                UNIQUE(date, ticker)
            );
            CREATE INDEX IF NOT EXISTS idx_scans_date ON scans(date);
            CREATE TABLE IF NOT EXISTS news_scans (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                date       TEXT NOT NULL,        -- YYYY-MM-DD (ET 거래일)
                created_at TEXT NOT NULL,
                ticker     TEXT NOT NULL,
                change_pct REAL,                 -- 전일 하락률
                catalyst   TEXT,                 -- 호재 요약
                view       TEXT,                 -- 반등 관점
                confidence TEXT,                 -- high | medium | low
                sources    TEXT,                 -- JSON 배열(출처 URL)
                UNIQUE(date, ticker)
            );
            CREATE INDEX IF NOT EXISTS idx_news_scans_date ON news_scans(date);
            CREATE TABLE IF NOT EXISTS holdings_news (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                date       TEXT NOT NULL,        -- YYYY-MM-DD (ET 거래일)
                created_at TEXT NOT NULL,
                ticker     TEXT NOT NULL,        -- 내 ETF 구성종목
                sentiment  TEXT,                 -- positive | neutral | negative
                headline   TEXT,                 -- 최신 핵심 뉴스 한 줄
                source     TEXT,                 -- 출처 URL
                UNIQUE(date, ticker)
            );
            CREATE INDEX IF NOT EXISTS idx_holdings_news_date ON holdings_news(date);
            CREATE TABLE IF NOT EXISTS searches (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker     TEXT NOT NULL,        -- 심볼(US) 또는 6자리코드(KR)
                date       TEXT NOT NULL,        -- 분석 날짜(YYYY-MM-DD)
                created_at TEXT NOT NULL,
                name       TEXT,                 -- 정식 종목명
                market     TEXT,                 -- KR | US
                price      REAL,
                change_pct REAL,
                summary    TEXT,                 -- 핵심 요약
                catalyst   TEXT,                 -- 호재/촉매
                view       TEXT,                 -- 단기 관점
                sentiment  TEXT,                 -- positive | neutral | negative
                sources    TEXT,                 -- JSON 배열(출처 URL)
                UNIQUE(ticker, date)             -- 같은 날 재검색 시 갱신
            );
            CREATE INDEX IF NOT EXISTS idx_searches_ticker ON searches(ticker);
            CREATE TABLE IF NOT EXISTS buys (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                date       TEXT NOT NULL,        -- YYYY-MM-DD (ET 거래일)
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                ticker     TEXT NOT NULL,        -- SMH | QLD | SSO
                amount     REAL,                 -- 그날 매수 금액(USD)
                price      REAL,                 -- 매수단가(종가) — buy_fill 잡이 채움
                bought     INTEGER DEFAULT 0,    -- 구입(1)/미구입(0)
                UNIQUE(date, ticker)
            );
            CREATE INDEX IF NOT EXISTS idx_buys_date ON buys(date);
            """
        )


# ---------- 쓰기 ----------
def save_digest(prose: str, signal_light: str = "unknown",
                indicators: list | None = None, conclusion: str = "",
                date: str | None = None) -> str:
    date = date or trading_day()
    with connect() as conn:
        conn.execute(
            """INSERT INTO digests (date, created_at, prose, signal_light, indicators, conclusion)
               VALUES (?,?,?,?,?,?)
               ON CONFLICT(date) DO UPDATE SET
                 created_at=excluded.created_at, prose=excluded.prose,
                 signal_light=excluded.signal_light, indicators=excluded.indicators,
                 conclusion=excluded.conclusion""",
            (date, _now_utc(), prose, signal_light,
             json.dumps(indicators or [], ensure_ascii=False), conclusion),
        )
    return date


def save_scans(hits: list[tuple], date: str | None = None) -> str:
    """hits: scanner.scan_one 의 (ticker, price, chg, reasons) 튜플 리스트."""
    date = date or trading_day()
    now = _now_utc()
    with connect() as conn:
        conn.execute("DELETE FROM scans WHERE date=?", (date,))  # 그날 결과 갱신
        conn.executemany(
            """INSERT INTO scans (date, created_at, ticker, price, change_pct, reasons)
               VALUES (?,?,?,?,?,?)""",
            [(date, now, t, float(p), float(c), json.dumps(r, ensure_ascii=False))
             for (t, p, c, r) in hits],
        )
    return date


# ---------- 읽기 ----------
def _digest_row(row: sqlite3.Row) -> dict:
    return {
        "date": row["date"],
        "created_at": row["created_at"],
        "prose": row["prose"],
        "signal_light": row["signal_light"],
        "indicators": json.loads(row["indicators"] or "[]"),
        "conclusion": row["conclusion"],
    }


def list_dates() -> list[dict]:
    """달력/사이드바용 — 날짜 + 신호등 + 스캔 후보 수."""
    with connect() as conn:
        rows = conn.execute(
            """SELECT d.date AS date, d.signal_light AS signal_light,
                      (SELECT COUNT(*) FROM scans s WHERE s.date = d.date) AS scan_count
               FROM digests d ORDER BY d.date DESC"""
        ).fetchall()
        # 다이제스트는 없고 스캔만 있는 날짜도 포함
        scan_only = conn.execute(
            """SELECT date, NULL AS signal_light, COUNT(*) AS scan_count
               FROM scans WHERE date NOT IN (SELECT date FROM digests)
               GROUP BY date ORDER BY date DESC"""
        ).fetchall()
    out = [dict(r) for r in rows] + [dict(r) for r in scan_only]
    out.sort(key=lambda x: x["date"], reverse=True)
    return out


def get_digest(date: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM digests WHERE date=?", (date,)).fetchone()
    return _digest_row(row) if row else None


def latest_digest() -> dict | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM digests ORDER BY date DESC LIMIT 1").fetchone()
    return _digest_row(row) if row else None


def get_scans(date: str) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM scans WHERE date=? ORDER BY ticker", (date,)).fetchall()
    return [{
        "ticker": r["ticker"], "price": r["price"], "change_pct": r["change_pct"],
        "reasons": json.loads(r["reasons"] or "[]"),
    } for r in rows]


# ---------- 뉴스 반등 후보 ----------
def save_news_scans(items: list[dict], date: str | None = None) -> str:
    """items: [{ticker, change_pct, catalyst, view, confidence, sources}]."""
    date = date or trading_day()
    now = _now_utc()
    with connect() as conn:
        conn.execute("DELETE FROM news_scans WHERE date=?", (date,))
        conn.executemany(
            """INSERT OR REPLACE INTO news_scans
                 (date, created_at, ticker, change_pct, catalyst, view, confidence, sources)
               VALUES (?,?,?,?,?,?,?,?)""",
            [(date, now, it["ticker"], float(it.get("change_pct") or 0),
              it.get("catalyst", ""), it.get("view", ""), it.get("confidence", ""),
              json.dumps(it.get("sources", []), ensure_ascii=False))
             for it in items],
        )
    return date


def get_news_scans(date: str) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM news_scans WHERE date=? ORDER BY ticker", (date,)).fetchall()
    return [{
        "ticker": r["ticker"], "change_pct": r["change_pct"],
        "catalyst": r["catalyst"], "view": r["view"], "confidence": r["confidence"],
        "sources": json.loads(r["sources"] or "[]"),
    } for r in rows]


# ---------- 보유 ETF 구성종목 최신 뉴스(양방향) ----------
def save_holdings_news(items: list[dict], date: str | None = None) -> str:
    """items: [{ticker, sentiment, headline, source}]. 그날 결과를 통째로 갱신."""
    date = date or trading_day()
    now = _now_utc()
    with connect() as conn:
        conn.execute("DELETE FROM holdings_news WHERE date=?", (date,))
        conn.executemany(
            """INSERT OR REPLACE INTO holdings_news
                 (date, created_at, ticker, sentiment, headline, source)
               VALUES (?,?,?,?,?,?)""",
            [(date, now, it["ticker"], it.get("sentiment", "neutral"),
              it.get("headline", ""), it.get("source", ""))
             for it in items],
        )
    return date


def get_holdings_news(date: str) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM holdings_news WHERE date=? ORDER BY ticker", (date,)).fetchall()
    return [{
        "ticker": r["ticker"], "sentiment": r["sentiment"],
        "headline": r["headline"], "source": r["source"],
    } for r in rows]


# ---------- 검색 분석(티커별·날짜별 누적) ----------
def _search_row(row: sqlite3.Row) -> dict:
    return {
        "ticker": row["ticker"], "date": row["date"], "created_at": row["created_at"],
        "name": row["name"], "market": row["market"], "price": row["price"],
        "change_pct": row["change_pct"], "summary": row["summary"],
        "catalyst": row["catalyst"], "view": row["view"], "sentiment": row["sentiment"],
        "sources": json.loads(row["sources"] or "[]"),
    }


def save_search(ticker: str, name: str = "", market: str = "",
                price: float | None = None, change_pct: float | None = None,
                summary: str = "", catalyst: str = "", view: str = "",
                sentiment: str = "neutral", sources: list | None = None,
                date: str | None = None) -> str:
    """검색 분석 1건 저장(같은 날·종목은 갱신, 날짜가 다르면 누적)."""
    date = date or trading_day()
    with connect() as conn:
        conn.execute(
            """INSERT INTO searches
                 (ticker, date, created_at, name, market, price, change_pct,
                  summary, catalyst, view, sentiment, sources)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(ticker, date) DO UPDATE SET
                 created_at=excluded.created_at, name=excluded.name, market=excluded.market,
                 price=excluded.price, change_pct=excluded.change_pct, summary=excluded.summary,
                 catalyst=excluded.catalyst, view=excluded.view, sentiment=excluded.sentiment,
                 sources=excluded.sources""",
            (ticker, date, _now_utc(), name, market, price, change_pct,
             summary, catalyst, view, sentiment,
             json.dumps(sources or [], ensure_ascii=False)),
        )
    return date


def get_searches(ticker: str) -> list[dict]:
    """한 종목의 분석 이력(최신 날짜 순)."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM searches WHERE ticker=? ORDER BY date DESC", (ticker,)).fetchall()
    return [_search_row(r) for r in rows]


def list_searches() -> list[dict]:
    """저장된 모든 분석(티커·날짜 순) — '저장된 데이터 보기'에서 티커별 그룹핑."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM searches ORDER BY ticker, date DESC").fetchall()
    return [_search_row(r) for r in rows]


# ---------- 분할매수 추적 ----------
def _buy_row(row: sqlite3.Row) -> dict:
    return {
        "date": row["date"], "ticker": row["ticker"], "amount": row["amount"],
        "price": row["price"], "bought": bool(row["bought"]),
    }


def record_buy(ticker: str, amount: float, bought: bool = True,
               date: str | None = None, price: float | None = None) -> str:
    """그날·종목 매수 기록(구입/미구입 + 매수단가). price 를 주면 그 값으로,
    안 주면 기존 price 유지(buy_fill 잡이 종가로 채울 수 있게)."""
    date = date or trading_day()
    now = _now_utc()
    with connect() as conn:
        conn.execute(
            """INSERT INTO buys (date, created_at, updated_at, ticker, amount, bought, price)
               VALUES (?,?,?,?,?,?,?)
               ON CONFLICT(date, ticker) DO UPDATE SET
                 updated_at=excluded.updated_at, amount=excluded.amount,
                 bought=excluded.bought,
                 price=COALESCE(excluded.price, buys.price)""",
            (date, now, now, ticker, float(amount), int(bool(bought)),
             None if price is None else float(price)),
        )
    return date


def get_buys(date: str) -> list[dict]:
    """그날 매수 기록(캘린더용)."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM buys WHERE date=? ORDER BY ticker", (date,)).fetchall()
    return [_buy_row(r) for r in rows]


def list_buys(ticker: str | None = None) -> list[dict]:
    """그래프/누적용 — 전체(또는 종목별) 매수를 날짜 오름차순으로."""
    with connect() as conn:
        if ticker:
            rows = conn.execute(
                "SELECT * FROM buys WHERE ticker=? ORDER BY date", (ticker,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM buys ORDER BY date, ticker").fetchall()
    return [_buy_row(r) for r in rows]


def fill_buy_price(date: str, ticker: str, price: float) -> None:
    """buy_fill 잡 — 마감 후 종가를 매수단가로 채움."""
    with connect() as conn:
        conn.execute(
            "UPDATE buys SET price=?, updated_at=? WHERE date=? AND ticker=?",
            (float(price), _now_utc(), date, ticker),
        )


def buys_missing_price() -> list[dict]:
    """종가 미채움(구입했는데 price NULL) — buy_fill 대상."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM buys WHERE bought=1 AND price IS NULL ORDER BY date").fetchall()
    return [_buy_row(r) for r in rows]
