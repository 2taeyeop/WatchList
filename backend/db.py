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
