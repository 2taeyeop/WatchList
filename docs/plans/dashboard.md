# Plan — 투자 모니터링 대시보드 (저장 + API + 프론트)

> CLAUDE.md 규칙에 따라 코드 변경을 추적하는 plan 문서. 빌드 중 갱신.

## Context

기존 파이프라인은 결과를 텔레그램으로 **쏘고 끝**(저장 없음). 사용자가
"날짜별 뉴스 + 매수/매도 신호" 대시보드를 원함. EC2(m6i.large)에 서브도메인으로
배포 예정. 평소 스택: GitHub Actions CI/CD, Docker, nginx 리버스 프록시.

## 결정사항 (확정)

- **저장소**: SQLite (`data/watchlist.db`) — 인프라 0, 하루 한두 번 쓰기/대시보드 읽기에 충분.
- **스케줄러**: EC2(systemd timer / cron) — DB 직접 저장 + 텔레그램 유지.
- **프론트**: Vite + React + TS (SPA) — 개인 대시보드라 SSR/SEO 불필요, nginx 정적+`/api` 프록시 패턴에 부합.
- **백엔드**: FastAPI(Python) — 파이프라인 코드/데이터 재사용, 단일 런타임.
- **범위**: 풀스택 전체 빌드.

## 변경 대상

| 영역 | 파일 |
|------|------|
| 저장소 | `backend/db.py` (SQLite 스키마+헬퍼) |
| 파이프라인 | `digest.py`(구조화 신호+DB저장), `scanner.py`(DB저장) |
| API | `backend/api.py` (FastAPI) |
| 프론트 | `frontend/` (Vite+React+TS 대시보드) |
| 배포 | `deploy/` (Dockerfile·compose·nginx·systemd) |
| 의존성 | `requirements.txt` (+fastapi, +uvicorn) |
| 문서 | `README.md` 배포 섹션 |

## 구현 순서 (각 단계 뒤 검증)

- [x] 7-1 `backend/db.py` — 스키마+헬퍼 ✅ 스모크 테스트 통과
- [x] 7-2 `digest.py` — 구조화 신호 추출(`extract_signal`, haiku 강제 도구호출) + DB 저장 ✅
- [x] 7-3 `scanner.py` — 스캔 결과 DB 저장(`db.save_scans`) ✅
- [x] 7-4 `backend/api.py` — FastAPI ✅ TestClient + 실제 HTTP(uvicorn) 검증(전 엔드포인트 + 404)
- [x] 7-5 `frontend/` — Vite+React ✅ npm install + 타입체크 + 프로덕션 빌드 통과(tsconfig 단일화)
- [x] 7-6 `deploy/` — Dockerfile.api/web + compose + nginx(컨테이너/호스트) + systemd timer 4종 ✅
- [x] 7-7 통합 테스트 ✅ 브라우저→Vite 프록시(:5173)→FastAPI(:8000)→SQLite 전 경로 검증
- [x] 7-8 README — 대시보드 로컬(섹션6) + EC2 배포(섹션7) 가이드 ✅

> **✅ 전체 완료 (2026-06-16).** 커밋 대기 상태(아직 미커밋). 남은 건 사용자 본인 키로
> `digest.py` 1회 실행해 `extract_signal` 신호 채워지는지 확인 + EC2 실제 배포뿐.

---

## 🔖 RESUME HERE — 다음 세션 진입점 (2026-06-16 중단)

### 지금까지 끝난 것
- 원래 요청 1~6 전부 완료(구조정리, `.gitignore`, `.env.example`, 로컬 테스트, README 세팅, 보안검증).
- `CLAUDE.md` 프로젝트 섹션 채움 + 이 plan 문서 작성.
- **백엔드 저장+API+파이프라인 연동 코드 작성 완료**(7-1~7-4).
- **프론트 전체 파일 작성 완료**(7-5) — 아직 의존성 설치/빌드 전.
- 의존성 설치됨(파이썬): anthropic, yfinance, pandas, requests, **fastapi, uvicorn**.
- `.gitignore`에 node/data 산출물 제외 추가.

### 작성된 파일 트리 (현재)
```
backend/__init__.py, backend/db.py, backend/api.py
digest.py(확장), scanner.py(확장), notify.py(그대로)
frontend/package.json, vite.config.ts, tsconfig.json, tsconfig.node.json, index.html
frontend/src/main.tsx, App.tsx, index.css
frontend/src/api/client.ts
frontend/src/shared/signal.ts, format.ts
frontend/src/dashboard/Dashboard.tsx, DateList.tsx, DigestView.tsx, ScanList.tsx, Dashboard.css
docs/plans/dashboard.md
```

### 다음에 할 일 (순서대로)

**① 7-4 검증 — FastAPI 실제 실행 (키 불필요)**
```bash
# 샘플 데이터 seed 후 서버 띄워 엔드포인트 확인
WATCHLIST_DB=data/watchlist.db PYTHONUTF8=1 python -c "
from backend import db
db.init_db()
db.save_digest(prose='샘플 본문', signal_light='yellow',
  indicators=[{'name':'SMH 200일선','status':'caution','value':'위 2%','change':'둔화','comment':'이격','source':'예시'}],
  conclusion='관망', date='2026-06-16')
db.save_scans([('NVDA',123.45,2.1,['200일선 회복'])], date='2026-06-16')
print('seeded')"
uvicorn backend.api:app --port 8000   # 다른 터미널에서: curl localhost:8000/api/dates 등
```
확인: `/api/health`, `/api/dates`, `/api/digests/2026-06-16`, `/api/scans/2026-06-16` 가 200 + 스키마 일치.

**② 7-5 검증 — 프론트 빌드/실행**
```bash
cd frontend
npm install
npm run build          # 타입/빌드 무에러 확인 (CLAUDE.md '검증' 규칙)
npm run dev            # localhost:5173 — /api 는 vite proxy 로 :8000 백엔드 호출
```
확인: 좌측 날짜 클릭 → 우측 다이제스트 신호등/지표/본문 + 스캔 후보 렌더.
(⚠️ 네트워크 불안정 시 `npm install`이 느릴 수 있음 — 재시도.)

**③ 7-6 deploy/ 작성 (아직 없음)** — 결정: SQLite + EC2 스케줄러.
- `deploy/Dockerfile.api` — python:3.12-slim, requirements 설치, `uvicorn backend.api:app --host 0.0.0.0 --port 8000`.
- `deploy/Dockerfile.web`(또는 멀티스테이지) — node 빌드 → nginx 정적 서빙.
- `deploy/docker-compose.yml` — api(8000) + web(nginx) + **공유 볼륨 `./data`**(SQLite 파일 공유).
- `deploy/nginx.conf` — 서브도메인 `watch.<도메인>`: `/` 정적 프론트, `/api` → `api:8000` 프록시.
- **스케줄러**: 호스트 cron 또는 systemd timer 가 `docker compose run --rm api python digest.py` / `scanner.py` 실행 → 같은 `./data/watchlist.db`에 기록. (컨테이너 내부 cron 대신 호스트 timer 권장.)
  - `deploy/systemd/digest.service`+`digest.timer`(13:00 UTC), `scanner.service`+`scanner.timer`(20:05 UTC) 예시 작성.
- env: EC2의 `.env`(커밋 금지)로 주입. **(이후 전환됨)** digest 는 Anthropic API 키 대신
  Claude Code 구독 인증(`CLAUDE_CODE_OAUTH_TOKEN`)을 호스트에서 사용 — `ANTHROPIC_API_KEY` 미사용.
  컨테이너 scanner 는 `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` 만.

**④ 7-7 통합 테스트** — compose 로컬 기동 → 프론트에서 seed 데이터 보이는지.

**⑤ 7-8 README** — "5. 대시보드 배포(EC2)" 섹션: 서브도메인 DNS, compose 기동, nginx, systemd timer, GitHub Actions(선택)와의 관계.

### 미해결/주의
- `digest.py`의 `extract_signal`은 **실 API 키로만** 검증 가능(유료) — 사용자 본인 키로 1회 실행해 신호등/지표 채워지는지 확인 필요.
- 프론트는 **실행 검증 전** — 타입/렌더 버그 가능성 있음. `npm run build` 로 먼저 잡을 것.
- `@app.on_event("startup")` 는 최신 FastAPI에서 deprecated 경고 가능 → 추후 `lifespan` 으로 교체 고려(동작엔 무방).
- 결정됨이지만 미구현: 스케줄러를 EC2로 옮기면 기존 `.github/workflows/monitor.yml`은 수동 트리거/백업용으로 둘지 정리 필요.

## 검증

- 파이프라인: import 해소, 키 없이 import OK, DB 저장 라운드트립.
- API: 샘플 데이터로 각 엔드포인트 200 + 스키마 일치.
- 프론트: `npm run build` 무에러, API 응답 필드와 타입 일치.

## 비범위 (이번엔 안 함)

- Postgres 이전(나중에 가능), 인증/로그인, 멀티유저, 실시간 푸시(WebSocket),
  과거 데이터 백필. 텔레그램 발송 로직 변경 없음(유지).

## API 계약 (프론트가 따를 스키마)

- `GET /api/health` → `{"ok": true}`
- `GET /api/dates` → `[{date, signal_light, scan_count}]` (최신순)
- `GET /api/digests/latest` → digest | null
- `GET /api/digests/{date}` → digest | 404
- `GET /api/scans/{date}` → `[{ticker, price, change_pct, reasons[]}]`
- digest = `{date, created_at, prose, signal_light, indicators[], conclusion}`
- indicator = `{name, status(ok|caution|alert|na), value?, change?, comment?, source?}`
