"""FastAPI — 대시보드용 읽기 API.

파이프라인이 저장한 SQLite(backend.db)를 읽어 JSON으로 제공한다. 쓰기는 하지
않는다(저장은 digest.py/scanner.py 담당). nginx 가 정적 프론트와 함께 /api 를
이 앱(uvicorn :8000)으로 프록시한다.

개발 서버:  uvicorn backend.api:app --reload
"""
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend import db

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
    allow_methods=["GET"],
    allow_headers=["*"],
)


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
