# 투자 모니터링 파이프라인 (개장 전 다이제스트 + 반등 스캐너)

세 개의 자동화로 구성됩니다.

- **`digest.py`** — ① 매일 개장 전, Claude가 어젯밤~오늘 프리마켓 뉴스/신호를
  종합해 텔레그램으로 보냄.
- **`scanner.py`** — ② 장 마감 후, 내 watchlist 밖 종목을 **기술적** 반등 조건으로
  스크리닝해 **후보가 있을 때만** 텔레그램으로 보냄(트리거형).
- **`news_scan.py`** — ③ 개장 전, '약세+전일 하락' 종목 중 **호재 뉴스로 반등 가능성**이
  있는 종목을 Claude 웹검색으로 골라 보냄. (기술 스캐너와 별개·보완)
- **대시보드** — 두 파이프라인 결과를 SQLite에 날짜별로 저장하고, FastAPI + React
  화면으로 **날짜별 뉴스/신호등/반등 후보**를 볼 수 있음(섹션 6).

스케줄: 운영 시 **scanner 는 GitHub Actions**, **digest 는 EC2 systemd**(Claude Code 구독 인증)가
담당합니다. 로컬에선 수동 실행.

---

## 폴더 구조

```
WatchList/
├─ .github/workflows/monitor.yml   ← 스케줄러(GitHub Actions — scanner 전용)
├─ requirements.txt     ← 파이썬 의존성
├─ backend/             ← 파이썬 백엔드 전부
│  ├─ db.py             ← SQLite 저장소(공유)
│  ├─ api.py            ← FastAPI(읽기 API)
│  ├─ notify.py         ← 텔레그램/디스코드 발송 헬퍼
│  └─ jobs/             ← 배치 잡(스케줄 실행)
│     ├─ digest.py      ← ① 개장 전 다이제스트
│     ├─ scanner.py     ← ② 기술적 반등 스캐너
│     └─ news_scan.py   ← ③ 뉴스 반등 후보(Claude 웹검색)
├─ frontend/            ← Vite + React 대시보드
├─ deploy/              ← Dockerfile·compose·nginx·systemd timer
├─ data/               ← SQLite 파일(런타임 생성, 커밋 제외)
├─ .env.example         ← 필요한 환경변수 목록(복사해서 .env 로)
└─ .gitignore           ← .env / __pycache__ / node_modules / data 등 제외
```

> 🔐 **비밀값 원칙**: 키는 **`.env`(로컬·EC2, 커밋 안 됨) 또는 GitHub Secrets**로만.
> 코드·커밋·`.env.example` 어디에도 실제 키를 적지 않습니다.

## 1. 텔레그램 봇 만들기 (5분)

1. 텔레그램에서 **@BotFather** 검색 → `/newbot` → 봇 토큰 받기
   (`TELEGRAM_BOT_TOKEN`).
2. 내 봇에게 아무 메시지나 한 번 보낸 뒤, 브라우저에서
   `https://api.telegram.org/bot<토큰>/getUpdates` 열기 →
   `chat.id` 값이 내 `TELEGRAM_CHAT_ID`.

## 2. Claude Code 구독 인증 (digest 용 — API 키 대신)

`digest.py` 는 Anthropic API 키 대신 **Claude Code(`claude -p`)를 구독 인증**으로 호출해
Claude 구독(Max 등) 한도에서 차감합니다(별도 API 종량 과금 없음).

1. Claude Code 설치(`npm i -g @anthropic-ai/claude-code`) 후 `claude` 로그인.
2. 헤드리스/서버용 1년짜리 토큰 발급:
   ```bash
   claude setup-token   # 출력된 토큰을 .env 의 CLAUDE_CODE_OAUTH_TOKEN 에 붙여넣기
   ```
3. ⚠️ **`ANTHROPIC_API_KEY` 는 설정하지 마세요.** 있으면 Claude Code 가 구독보다 API 키를
   우선해 종량 과금됩니다(`digest.py` 가 자식 프로세스에서 강제 제외하지만, 아예 두지 않는 게 안전).

## 3. 로컬에서 먼저 테스트 (키는 `.env`로만 주입)

GitHub에 올리기 전에 내 PC에서 동작을 확인합니다. **키는 코드가 아니라 환경변수로**
주입합니다.

```bash
# 1) 가상환경 + 의존성
python -m venv .venv
# Windows(PowerShell):  .\.venv\Scripts\Activate.ps1
# macOS/Linux:          source .venv/bin/activate
pip install -r requirements.txt

# 2) .env 만들기 (실제 키 채우기 — 이 파일은 .gitignore 로 커밋 안 됨)
cp .env.example .env      # Windows: copy .env.example .env
```

`.env`에 값을 채운 뒤, 셸에 환경변수로 올려서 실행합니다.

```bash
# macOS/Linux — .env 를 현재 셸로 로드
set -a; source .env; set +a
python -m backend.jobs.digest      # 다이제스트 1회 → 텔레그램 발송
python -m backend.jobs.scanner     # 기술적 반등 스캔 1회 (후보 있을 때만)
python -m backend.jobs.news_scan   # 뉴스 반등 후보 1회 (호재 있을 때만)
```

```powershell
# Windows PowerShell — .env 한 줄씩 환경변수로 주입
Get-Content .env | Where-Object { $_ -match '=' -and $_ -notmatch '^\s*#' } |
  ForEach-Object { $k,$v = $_ -split '=',2; [Environment]::SetEnvironmentVariable($k.Trim(), $v.Trim()) }
$env:PYTHONUTF8 = "1"   # 콘솔 한글/특수문자 인코딩 (Windows 권장)
python -m backend.jobs.digest
python -m backend.jobs.scanner
python -m backend.jobs.news_scan
```

> 💡 `digest.py`는 Claude Code(`claude -p`)를 구독 인증으로 불러 다이제스트를 만들고(구독
> 한도 차감, 별도 API 과금 없음 — 로컬에 `claude` 설치/로그인 필요), `scanner.py`는 후보가
> 있을 때만 텔레그램으로 발송합니다(없으면 `반등 후보 없음`만 출력하고 종료 — 정상).

## 4. GitHub Secrets 등록 (scanner 용 — 2개)

GitHub Actions 로는 **scanner(②)만** 돌립니다(digest 는 구독 인증이라 EC2 에서 — 섹션 7).
레포 → **Settings → Secrets and variables → Actions → New repository secret** 로 2개 등록:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

## 5. scanner 배포 & 테스트 (GitHub Actions)

1. 레포에 푸시(`monitor.yml`은 `.github/workflows/` 안에).
2. **Actions 탭 → market-monitor → Run workflow** 로 scanner 수동 실행 → 텔레그램 확인.
3. 이후 평일 20:05 UTC 스케줄로 자동 실행됩니다. (digest 는 섹션 7 의 EC2 systemd)

---

## 6. 대시보드: 로컬 실행 (DB + API + 프론트)

흐름: `digest.py`/`scanner.py` → **SQLite `data/watchlist.db`** 저장 → **FastAPI**가 읽어 JSON →
**React** 화면. 프론트는 항상 상대경로 `/api` 호출 → 개발은 Vite 프록시(:8000), 운영은 nginx.

```bash
# 터미널 A — 백엔드 API (키 불필요: 읽기 전용)
uvicorn backend.api:app --reload          # http://localhost:8000/api/health

# 터미널 B — 프론트
cd frontend && npm install && npm run dev  # http://localhost:5173
```

데이터가 없으면 빈 화면입니다 → `python -m backend.jobs.digest` / `... scanner`(섹션 3)로 채우면
좌측에 날짜가 나타나고, 클릭하면 신호등·지표 표·본문·반등 후보가 보입니다.

API 엔드포인트:

| 메서드 | 경로 | 설명 |
| ----- | ---- | ---- |
| GET | `/api/health` | 헬스체크 |
| GET | `/api/dates` | 날짜 목록(신호등·스캔수, 최신순) |
| GET | `/api/digests/latest` | 최신 다이제스트 |
| GET | `/api/digests/{date}` | 날짜별 다이제스트(신호등·지표·본문) |
| GET | `/api/scans/{date}` | 날짜별 반등 후보 |

## 7. 대시보드 배포 (EC2 + Docker + nginx)

`deploy/docker-compose.yml` 이 **`api`(uvicorn) + `web`(nginx: 정적 + `/api` 프록시)** 두
컨테이너를 띄우고, SQLite는 `./data` 볼륨으로 공유합니다. 호스트 nginx가 서브도메인 →
`web`(:8080)로 프록시, 스케줄은 호스트 **systemd timer**가 담당합니다.

```bash
# EC2에서
git clone <repo> /opt/watchlist && cd /opt/watchlist
cp .env.example .env && vi .env        # CLAUDE_CODE_OAUTH_TOKEN·TELEGRAM_* 채우기 (.env 커밋 안 됨)

docker compose -f deploy/docker-compose.yml up -d --build
# 우선 http://<EC2-IP>:8080 으로 화면 확인
```

**서브도메인 + HTTPS** (호스트 nginx):

1. DNS: `watch.<도메인>` A레코드 → EC2 퍼블릭 IP
2. `deploy/nginx.host.conf.example` 참고해 호스트 nginx에 server 블록 추가 →
   `sudo nginx -t && sudo systemctl reload nginx`
3. `sudo certbot --nginx -d watch.<도메인>` 로 인증서 자동 설정

**스케줄러** (systemd timer):

- **scanner** 는 컨테이너에서 실행(`docker compose run --rm api python -m backend.jobs.scanner`).
- **digest·news** 는 Claude Code(Node)가 필요해 **호스트에서 실행**합니다 → 호스트 사전 준비:
  ```bash
  npm i -g @anthropic-ai/claude-code        # 호스트에 Claude Code
  claude setup-token                         # 토큰 → /opt/watchlist/.env 의 CLAUDE_CODE_OAUTH_TOKEN
  python3 -m venv /opt/watchlist/.venv       # 호스트 python venv (digest 가 backend/notify import)
  /opt/watchlist/.venv/bin/pip install -r requirements.txt
  ```
  `deploy/systemd/digest.service` 가 `python -m backend.jobs.digest` 를 호스트에서
  실행하고 같은 `data/watchlist.db` 에 기록합니다. **⚠️ 호스트 환경에 `ANTHROPIC_API_KEY` 금지.**

```bash
sudo cp deploy/systemd/*.service deploy/systemd/*.timer /etc/systemd/system/
# 각 .service 의 WorkingDirectory=/opt/watchlist 경로 확인/수정
sudo systemctl daemon-reload
sudo systemctl enable --now digest.timer news.timer scanner.timer
systemctl list-timers | grep -E 'digest|news|scanner'   # 다음 실행시각 확인
```

> ⚠️ **중복 실행 주의** — `monitor.yml` 은 이제 **scanner 만** 돌립니다(digest 잡 제거됨).
> EC2 의 `scanner.timer` 를 켰다면 GitHub Actions 의 scanner cron 과 겹쳐 텔레그램이 두 번 올 수
> 있으니 한쪽만 쓰세요. **digest 는 EC2 전용**입니다(GitHub Actions 에선 구독 인증 불가).

---

## 커스터마이즈

- **발송 채널 교체** — `notify.py`에 `send_discord()`가 이미 있습니다.
  각 스크립트에서 `send_telegram` → `send_discord`로 바꾸고
  `DISCORD_WEBHOOK_URL` 시크릿을 추가하면 됩니다. (이메일은 SMTP/SendGrid 버전 별도.)
- **스캔 유니버스/조건** — `scanner.py`의 `UNIVERSE` 리스트와 반등 조건(200/50일선,
  RSI, 거래량)을 자유롭게 수정.
- **다이제스트 내용** — `digest.py`의 `PROMPT` 문자열만 고치면 됩니다.
- **실행 시간** — scanner 는 `monitor.yml` cron, digest 는 `deploy/systemd/digest.timer` 를
  수정. 개장 30분 전 = `09:00 ET`(= 13:00 UTC, 서머타임 기준).

---

## ⚠️ 꼭 알아둘 점

- **GitHub cron은 UTC + DST 미반영.** 미국 서머/겨울 전환 때 cron 시각을 1시간
  옮겨야 합니다(yml 주석 참고). 또 **무료 Actions는 스케줄이 5~15분 지연**될 수
  있어요. *정밀한 시간*이 필요하면 **AWS EventBridge → Lambda**(너희 인프라)로
  옮기면 정확하고 안정적입니다.
- **yfinance는 비공식·무료**라 가끔 막히거나 지연될 수 있습니다. 안정성이
  중요하면 Polygon·Finnhub·Alpha Vantage 등 **유료 데이터 API로 교체** 권장.
- **반등 스캐너 vs TradingView** — 더 안정적·정교한 스크리닝을 원하면
  스캐너 대신 **TradingView 스크리너 + 알림(웹훅 → 텔레그램/디스코드)**을 쓰는 게
  편합니다. 코드는 ①만 두고 ②는 TradingView로 분리해도 됩니다.
- **비용** — `digest.py`·`news_scan.py`는 Claude Code를 **구독 인증**으로 호출해 **Claude
  구독(Max 등) 한도에서 차감**됩니다(별도 API 종량 과금 없음). 둘 다 하루 1회라 한도 영향은
  미미. `scanner.py`·텔레그램·GitHub Actions·yfinance는 무료. (※ `ANTHROPIC_API_KEY`를 두면
  구독 대신 API로 과금되니 두지 말 것.)
- **보안** — 키는 반드시 **GitHub Secrets/환경변수**로만. 코드에 하드코딩 금지.
  이 파이프라인은 *뉴스 읽기·발송만* 하며 시스템·계정 접근권이 없습니다.

---

*이 산출물은 정보 정리 목적이며 투자 자문이 아닙니다. 반등 후보·총평은 '관찰/관점'
이지 매매 지시가 아닙니다.*
