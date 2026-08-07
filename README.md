# WatchList — TQQQ/JEPI 규칙서 집행봇

텔레그램으로 증권앱(토스) 잔고 스크린샷을 보내면, 사전 정의된 투자 규칙서
(`prompts/rulebook.md`)에 따라 **판정·주문표·기록 로그**를 회신하는 봇입니다.

이 봇은 조언자가 아니라 **집행자**입니다. 뉴스·전망·추천은 금지된 입력이며, 허용된
입력은 ①잔고 스크린샷 ②시장 데이터(나스닥100 종가, 티커 현재가 — 서버가 yfinance로
직접 조회) ③규칙서뿐입니다. **주문 실행 자동화는 범위 밖** — 봇은 주문표만 만들고
실행은 항상 사람이 합니다.

## 동작

1. **사진 수신** → Claude 비전으로 보유 종목·주수·평가손익·예수금 추출
   (흐릿한 값은 추측하지 않고 재촬영 요청, 이미지는 처리 후 즉시 삭제)
2. **1차 회신 = 확인 게이트(생략 불가)** — 추출값 + 서버 조회값(NDX 하락률·현재가·환율)
   요약 + [✅ 맞음] [❌ 다시] 버튼
3. ✅ 시 **2차 회신 = 판정** — ①판정 ②근거 숫자 ③주문표 ④실행 후 예상 비중
   ⑤로그 한 줄(자동 저장, 노션 동기화는 선택)

돈 계산은 전부 순수 함수(`backend/rules.py`) + 유닛테스트로 결정적으로 처리하고,
클로드는 **스크린샷 추출**과 **자유 질문 답변**에만 씁니다.

## 명령어

| 명령 | 동작 |
| --- | --- |
| (사진만 전송) | `/monthly` 와 동일 |
| `/monthly` | 월간 적립 판정 (비중<70% → TQQQ, 아니면 JEPI) |
| `/entry` | 진입기 주간 루틴 (SGOV→TQQQ 5주 분할) |
| `/december` | 12월 셋째 월요일 리밸런싱 + 공제·손실 수확 |
| `/withdraw <원화>` | 생계 인출 70:30 매도 산출 — 가드레일 없이 즉시 협조 |
| `/log` | 최근 기록 10줄 |
| `/setday <일>` | 적립일 설정 |
| `/phase <SETUP\|ENTRY\|STEADY>` | 단계 전환 |
| `/newchat` | 자유 질문 대화 초기화 |

명령어도 사진도 아닌 일반 텍스트는 **개인 주식 비서** 대화입니다: 봇이 **채팅방의
모든 내용**(사용자 메시지·명령어·봇의 판정 회신·사진 전송·게이트 버튼)을 DB(`chat_log`)에
기록하고, 매 대화 호출 때 전문을 시스템 프롬프트로 주입합니다 — 비서는 이 방에서
일어난 일을 전부 기억합니다(`/newchat` 으로 초기화, DB 기반이라 재배포에도 유지).
규칙서·봇 사용법·**현재 운용 상태**(마지막 확인 잔고·비중·가속 플래그·최근 기록)도
함께 알고 답하며, 웹 검색으로 뉴스·시장 정보도 종합해줍니다. 잡담도 됩니다. 단 집행
가드레일은 유지 — 뉴스를 근거로 한 매매 제안, 규칙 밖 매매 상담, 새로운 돈 계산은
하지 않습니다(`backend/reply.py`).

리마인더는 셋뿐입니다(그 외 정기 푸시 금지): 매월 적립일 아침, 12월 셋째 월요일
(가속 발동 연도면 스킵 안내), ENTRY 단계 매주 월요일.

## 폴더 구조

```
WatchList/
├─ backend/
│  ├─ bot.py            ← 텔레그램 롱폴링 봇(수신·게이트·판정 오케스트레이션)
│  ├─ rules.py          ← 판정 엔진(순수 함수: 월간/가속/12월/공제/인출/진입)
│  ├─ market.py         ← 시장 데이터(yfinance: ^NDX·현재가·환율)
│  ├─ vision.py         ← 스크린샷 수치 추출(Claude 비전)
│  ├─ reply.py          ← 회신 조립 + 자유 질문(규칙서 시스템 프롬프트)
│  ├─ claude_runner.py  ← claude -p 헤드리스 호출(구독 인증 강제)
│  ├─ db.py             ← SQLite(state 1행 + 로그 append-only + 확인 게이트)
│  ├─ notify.py         ← 텔레그램 Bot API 클라이언트
│  ├─ notion.py         ← 노션 로그 동기화(선택)
│  └─ jobs/reminder.py  ← 매일 아침 리마인더 잡
├─ prompts/rulebook.md  ← 투자 규칙서(개정 시 이 파일 갱신 = 봇 지식 갱신)
├─ tests/               ← 유닛·시나리오 테스트(pytest)
├─ deploy/              ← Dockerfile + compose(로컬 빌드용 / 서버 pull용 .server.yml)
├─ .github/workflows/ci.yml ← CI/CD(전 브랜치 테스트 + main 머지 시 이미지 발행)
└─ data/                ← SQLite 파일(런타임 생성, 커밋 제외)
```

## 배포 (EC2 — Docker Hub pull, 리포 clone 불필요)

```
작업 브랜치 커밋 → main 머지 → CI: pytest → 통과 시 watchlist-bot:latest·:sha 발행
→ 서버: docker compose pull && docker compose up -d
```

이미지 발행은 **main 머지(push)에서만** 실행됩니다 (GitHub Secrets:
`DOCKERHUB_USERNAME`·`DOCKERHUB_TOKEN` 필요). 다른 브랜치 push 는 테스트만 돕니다.

```bash
# 서버 최초 1회 셋업
mkdir -p ~/watchlist-bot && cd ~/watchlist-bot
# deploy/docker-compose.server.yml 내용을 docker-compose.yml 로 저장
# .env 작성: TELEGRAM_BOT_TOKEN·TELEGRAM_CHAT_ID·CLAUDE_CODE_OAUTH_TOKEN 필수

# 배포(이후 갱신도 동일)
docker compose pull && docker compose up -d
docker logs -f watchlist-bot   # "규칙서 집행봇 시작 — 롱폴링" 확인

# 리마인더(매일 아침 1회) — 호스트 crontab (서버 TZ=UTC 기준 23:00 = 08:00 KST)
# 0 23 * * * cd $HOME/watchlist-bot && docker compose run --rm bot python -m backend.jobs.reminder >> data/reminder.log 2>&1
```

로컬 빌드가 필요하면 `docker compose -f deploy/docker-compose.yml up -d --build`.

- 봇은 **롱폴링**이라 도메인·인증서·공개 포트가 전혀 필요 없습니다
  (노출 엔드포인트 0개 — compose 에 ports 없음).
- **`CLAUDE_CODE_OAUTH_TOKEN` 은 컨테이너에서 필수**입니다 — 호스트의 claude 로그인이
  컨테이너 안에는 없으므로, 로컬에서 `claude setup-token` 으로 발급해 .env 에 넣으세요.
- ⚠️ `ANTHROPIC_API_KEY` 는 설정 금지 — 구독 인증 대신 API 종량 과금됩니다
  (`claude_runner.py` 가 자식 프로세스에서 강제 제외).
- 화이트리스트: `TELEGRAM_CHAT_ID` 하나만 응답, 그 외 발신자는 무응답.
- SQLite(state·로그)는 `data/` 볼륨으로 호스트에 남아 컨테이너 재빌드에도 유지됩니다.

## 로컬 개발

```bash
pip install -r requirements.txt
python -m pytest tests/ -q     # 판정 엔진 테스트
python -m backend.bot          # 봇 실행(.env 값이 프로세스 환경에 있어야 함)
```

윈도우 로컬에서 `.env` 를 쓰려면 dotenv 러너(`c:/tmp/run_job.py` 방식)로 환경을
적재한 뒤 실행하세요. 비밀값을 셸에 echo 하지 않습니다.
