"""SQLite 저장소 — 봇 상태(state 1행) + 기록 로그(append-only) + 확인 게이트(pending).

경로는 WATCHLIST_DB 환경변수(기본 data/watchlist.db). 날짜 기준은 KST —
적립일·리마인더·로그가 전부 사용자(한국) 생활 시간에 묶이기 때문.
"""
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

_KST = timezone(timedelta(hours=9))

STATE_COLUMNS = {
    "phase", "entry_week", "monthly_day", "episode_active",
    "tier1_fired", "tier2_fired", "skip_december_year", "carry_usd", "crisis_active",
}
_BOOL_COLUMNS = {"episode_active", "tier1_fired", "tier2_fired", "crisis_active"}


def db_path() -> str:
    return os.environ.get("WATCHLIST_DB", os.path.join("data", "watchlist.db"))


def today_kst() -> str:
    return datetime.now(_KST).strftime("%Y-%m-%d")


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
            CREATE TABLE IF NOT EXISTS state (
                id                 INTEGER PRIMARY KEY CHECK (id = 1),
                phase              TEXT NOT NULL DEFAULT 'SETUP',  -- SETUP | ENTRY | STEADY
                entry_week         INTEGER NOT NULL DEFAULT 1,     -- 진입기 주차(1~5)
                monthly_day        INTEGER,                        -- 적립일(일). NULL=미설정
                episode_active     INTEGER NOT NULL DEFAULT 0,     -- 가속 에피소드 진행 중
                tier1_fired        INTEGER NOT NULL DEFAULT 0,
                tier2_fired        INTEGER NOT NULL DEFAULT 0,
                skip_december_year INTEGER,                        -- 가속 발동 연도(그해 12월 스킵)
                carry_usd          REAL NOT NULL DEFAULT 0,        -- 이월 잔돈($) 장부값
                crisis_active      INTEGER NOT NULL DEFAULT 0      -- 위기 모드(히스테리시스)
            );
            CREATE TABLE IF NOT EXISTS logs (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                date       TEXT NOT NULL,   -- YYYY-MM-DD (KST)
                action     TEXT NOT NULL,
                drawdown   TEXT NOT NULL,   -- 표시용 문자열(예: -12.3%)
                weights    TEXT NOT NULL,   -- 비중 전→후(예: 68.2%→70.1%)
                memo       TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS pending (
                id         INTEGER PRIMARY KEY CHECK (id = 1),
                created_at TEXT NOT NULL,
                kind       TEXT NOT NULL,   -- monthly | entry | december | withdraw
                payload    TEXT NOT NULL    -- 추출값+시장값 JSON(확인 게이트 통과 전)
            );
            CREATE TABLE IF NOT EXISTS kv (
                key   TEXT PRIMARY KEY,     -- 예: last_snapshot(마지막 확인 잔고)
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS chat_log (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,   -- UTC ISO
                role       TEXT NOT NULL,   -- user | bot
                content    TEXT NOT NULL    -- 채팅방에 오간 메시지 전문(명령·회신·사진 알림 포함)
            );
            """
        )
        conn.execute("INSERT OR IGNORE INTO state (id) VALUES (1)")


# ---------- 상태 ----------
def get_state() -> dict:
    with connect() as conn:
        row = conn.execute("SELECT * FROM state WHERE id=1").fetchone()
    state = dict(row)
    for col in _BOOL_COLUMNS:
        state[col] = bool(state[col])
    return state


def update_state(**kwargs) -> None:
    unknown = set(kwargs) - STATE_COLUMNS
    if unknown:
        raise ValueError(f"알 수 없는 state 컬럼: {unknown}")
    if not kwargs:
        return
    cols = ", ".join(f"{k}=?" for k in kwargs)
    values = [int(v) if isinstance(v, bool) else v for v in kwargs.values()]
    with connect() as conn:
        conn.execute(f"UPDATE state SET {cols} WHERE id=1", values)


# ---------- 기록 로그 (append-only) ----------
def append_log(action: str, drawdown: str, weights: str, memo: str = "",
               date: str | None = None) -> dict:
    row = {"created_at": _now_utc(), "date": date or today_kst(),
           "action": action, "drawdown": drawdown, "weights": weights, "memo": memo}
    with connect() as conn:
        conn.execute(
            "INSERT INTO logs (created_at, date, action, drawdown, weights, memo) "
            "VALUES (:created_at, :date, :action, :drawdown, :weights, :memo)", row)
    return row


def recent_logs(limit: int = 10) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM logs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def format_log(row: dict) -> str:
    return f"{row['date']} | {row['action']} | {row['drawdown']} | {row['weights']} | {row['memo']}"


# ---------- 범용 key-value ----------
def kv_get(key: str) -> str | None:
    with connect() as conn:
        row = conn.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
    return row["value"] if row else None


def kv_set(key: str, value: str) -> None:
    with connect() as conn:
        conn.execute("INSERT OR REPLACE INTO kv (key, value) VALUES (?, ?)", (key, value))


def kv_delete(key: str) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM kv WHERE key=?", (key,))


# ---------- 채팅방 대화 기록 (비서의 기억 — /newchat 으로 초기화) ----------
def chat_append(role: str, content: str) -> None:
    with connect() as conn:
        conn.execute("INSERT INTO chat_log (created_at, role, content) VALUES (?, ?, ?)",
                     (_now_utc(), role, content))


def chat_history(max_chars: int = 40_000) -> tuple[list[dict], bool]:
    """최신부터 거슬러 max_chars 이내의 기록을 (시간순, 잘림 여부)로 반환.
    비서 프롬프트에 통째로 들어가므로 상한으로 폭주를 막는다."""
    with connect() as conn:
        rows = conn.execute("SELECT * FROM chat_log ORDER BY id DESC").fetchall()
    picked, total = [], 0
    truncated = False
    for r in rows:
        total += len(r["content"])
        if picked and total > max_chars:
            truncated = True
            break
        picked.append(dict(r))
    picked.reverse()
    return picked, truncated


def chat_clear() -> None:
    with connect() as conn:
        conn.execute("DELETE FROM chat_log")


# ---------- 확인 게이트 ----------
def set_pending(kind: str, payload: dict) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO pending (id, created_at, kind, payload) VALUES (1, ?, ?, ?)",
            (_now_utc(), kind, json.dumps(payload, ensure_ascii=False)))


def get_pending() -> tuple[str, dict] | None:
    """삭제 없이 조회(peek) — 회신 전송 성공 후에만 지우는 커밋 순서를 위해."""
    with connect() as conn:
        row = conn.execute("SELECT * FROM pending WHERE id=1").fetchone()
    if row is None:
        return None
    return row["kind"], json.loads(row["payload"])


def pop_pending() -> tuple[str, dict] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM pending WHERE id=1").fetchone()
        if row is None:
            return None
        conn.execute("DELETE FROM pending WHERE id=1")
    return row["kind"], json.loads(row["payload"])


def clear_pending() -> None:
    with connect() as conn:
        conn.execute("DELETE FROM pending WHERE id=1")
