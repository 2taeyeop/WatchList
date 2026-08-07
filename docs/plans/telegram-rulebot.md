# 텔레그램 규칙서 집행봇 전면 개편 (뉴스봇 → 집행봇)

> 상태: **구현 완료(커밋 대기)** — 결정: D1=전부 제거, D2=롱폴링, D3=백필 변경분 폐기, D4=규칙서 원문 별도 수령(수령 전까지 `prompts/rulebook.md`는 사전 프롬프트 기반 임시본).
> 검증: pytest 57개 통과 · market 실측 스모크 통과 · 적대적 리뷰 워크플로(25 에이전트)로 확정 결함 12건 발견·전부 수정(손실 수확 수량 산정, /withdraw 가속 인터셉트 제외, 게이트 nonce 바인딩, 전송 성공 후 커밋, null 필수값 차단, 클로드 세션 트랜스크립트 정리, 리마인더 말일 보정, 메시지 분할 등).
> 남은 일: 규칙서 원문 수령 시 rulebook.md 교체 → 커밋 → EC2 배포(사용자와 함께).
> 근거 문서: 사용자 제공 "Claude 지시문 — 투자 규칙 집행 보조" + "작업 지시: 텔레그램 투자봇 전면 개편"

## Context

- 기존 서비스: 뉴스 수집→요약→신호등/분할매수 페이스 추천→텔레그램 푸시(배치 3종) + 날짜별 대시보드(React).
- 새 서비스: **사용자가 텔레그램으로 토스 잔고 스크린샷을 보내면, TQQQ 70:JEPI 30 규칙서에 따라 판정·주문표·기록 로그를 회신**하는 봇. 뉴스·전망·추천은 금지된 입력.
- 설계 철학: 돈 계산은 순수 함수+유닛테스트, 클로드는 ①스크린샷 수치 추출(비전) ②최종 회신 문장 작성만. 시장 데이터(^NDX 2년 최고/최신 종가, TQQQ·JEPI·SGOV 현재가)는 서버가 yfinance로 직접 조회·주입.

### 탐색 결과 (2026-07-22, 워크플로 4-agent 전수 조사)

- **텔레그램은 송신 전용** — `notify.py`가 requests로 sendMessage 직접 호출. 수신(웹훅/폴링) 코드는 리포 어디에도 없음 → 수신부는 전부 신규 구축.
- **헤드리스 클로드**: `digest.run_claude()`가 유일한 진입점(`claude -p --allowedTools WebSearch,WebFetch --output-format json`, 구독 인증 강제 — API 키를 자식 env에서 제거). news_scan·holdings_news·ticker_search가 재사용. **비전 입력은 현 구조로 불가** — 이미지 경로를 프롬프트에 넣고 `--allowedTools Read`를 허용하는 확장 필요.
- **스케줄 이원화**: digest=EC2 systemd(평일 13:00 UTC, 호스트 venv — claude 필요), news_scan=13:05 systemd, scanner=GitHub Actions cron(20:05 UTC) + 동일 시각 systemd 타이머 공존(한쪽만 켜라는 README 경고). holdings_news는 무스케줄(수동).
- **배포**: EC2 단일 호스트, docker-compose 2컨테이너(api=uvicorn 포트 미공개 / web=nginx 8080 공개), 호스트 nginx+certbot HTTPS는 `.example`만 리포에 있어 실제 설정 여부 미확정. CD 없음(수동 배포). 봇은 claude CLI가 필요하므로 **digest처럼 호스트 systemd로 상시 실행**이 자연스러움.
- **테스트·린트 전무** → pytest 신규 도입 필요.
- **미커밋 작업 충돌**: digest/news_scan/scanner.py에 백필(asof) 수정 +54/-25 미커밋, `docs/plans/backfill-0601-0607.md` 미추적 — 세 파일 모두 이번 개편의 삭제 대상.
- 결합 지점 주의: `ticker_search.py`가 `digest.run_claude` import(검색 유지 시 헬퍼 이동 필요), `news_scan`이 `scanner.UNIVERSE` import, 프론트 `BuyTracking`이 `HoldingsImpact`(digest 의존)에 임베드.

## 결정사항

### 사용자 결정 대기

- **D1. 프론트엔드·대시보드 운명**
  - A) **전부 제거** (frontend/ + api.py + 검색·매수추적 포함) — 작업지시 7절 "서버 엔드포인트는 텔레그램 웹훅 외 노출 금지"에 부합. 검색(ticker_search)은 "뉴스 분석"이라 새 철학(뉴스=금지 입력)과 충돌. 매수추적은 구 전략(SMH/QLD/SSO 분할매수)용이라 무의미해짐. **← 추천**
  - B) 코드는 남기고 배포에서만 제외 — 죽은 코드 잔류(CLAUDE.md 원칙 위배), 유지보수 혼란.
  - C) 검색+매수추적만 남긴 축소 대시보드 유지 — 최근 투자한 기능은 살지만, 공개 엔드포인트가 남아 7절과 충돌하고 이중 서비스 유지비 발생.
- **D2. 텔레그램 수신 방식**
  - A) **롱폴링(getUpdates)** — 도메인·인증서 불요, 공개 엔드포인트 0개(7절 취지에 최적), 호스트 systemd 상시 서비스 하나로 완결. 단일 사용자 봇에 충분. **← 추천**
  - B) 웹훅 — EC2에 도메인+certbot HTTPS가 실제 설정돼 있어야 가능. FastAPI에 라우트 추가(D1-A와 충돌: api 컨테이너를 살려야 함).
- **D3. 미커밋 백필 작업(digest/news_scan/scanner asof + plan 문서)**
  - A) **현 브랜치에 커밋해 히스토리 보존 → 새 브랜치에서 개편 착수** — "git 히스토리로만 보존" 지시와 부합. **← 추천** (커밋은 사용자 "커밋해" 명시 시)
  - B) 변경분 폐기 — 백필 작업이 영구 소실.
- **D4. 규칙서 원문** — `TQQQ-JEPI-투자규칙서.md`를 받아 `prompts/rulebook.md`로 저장해야 함. 파일 미수령 상태. 임시로 "Claude 지시문" 사전 프롬프트로 구성할 수도 있으나 원문 수령이 정도.

### 자체 결정 (자명한 기본값)

- **D5. 봇 구현**: 프레임워크 없이 requests 직접 호출 유지(getUpdates 롱폴링 루프 + sendMessage/getFile/answerCallbackQuery). 현 리포의 raw-requests 스타일·최소 의존성 방침과 일관. python-telegram-bot은 도입하지 않음.
- **D6. 상태 저장**: SQLite(`backend/db.py` 재작성) — `state` 1행(phase/entry_week/monthly_day/episode_active/tier1_fired/tier2_fired/skip_december_year/carry_usd) + `logs` append-only(`날짜 | 행동 | 하락률 | 비중 전→후 | 메모`). 기존 스택 그대로.
- **D7. 비전 추출**: `run_claude` 확장 — `allowed_tools` 파라미터화, 이미지 파일 경로를 프롬프트에 포함 + `Read` 허용. 구독 인증 강제(ANTHROPIC_API_KEY 제거)는 그대로 유지. 처리 후 이미지 즉시 삭제.
- **D8. 환율**: 서버가 yfinance `KRW=X`로 조회해 주입(작업지시 3절 "시장 데이터 서버 주입" 준용). 확인 게이트 표에 노출해 사용자가 검증.
- **D9. 노션 동기**: env에 NOTION_TOKEN·DB ID 있으면 로그 행 동기화, 없으면 로컬만(작업지시 명세 그대로 — 선택 기능).

## 변경 대상

### 삭제 (git 히스토리로만 보존)

| 대상 | 사유 |
| --- | --- |
| `backend/jobs/digest.py` | 뉴스 요약·신호등 파이프라인 (run_claude만 신규 모듈로 이식) |
| `backend/jobs/news_scan.py` | 뉴스 반등 후보 |
| `backend/jobs/scanner.py` | 기술 스캔·매일 푸시 배치 |
| `backend/jobs/holdings_news.py` | 구성종목 뉴스 감성(비율 추천 입력) |
| DB 테이블 digests·scans·news_scans·holdings_news | 파이프라인 산출물 |
| `.github/workflows/monitor.yml` | scanner 매일 실행 — 매일 푸시 금지 조항 |
| `deploy/systemd/` digest·news·scanner 6종 | 구 스케줄 전부 |
| (D1-A 시) `frontend/` 전체, `backend/api.py`, `quote.py`·`ticker_search.py`·`buy_fill.py`, searches·buys 테이블, `deploy/Dockerfile.web`·`nginx.conf`·`nginx.host.conf.example`, compose의 web 서비스 | 대시보드 폐기 |

- "비율 추천" 개념이 어떤 산출물에도 남지 않는지 최종 grep 검증(signal_light·pace·guide 등 키워드).

### 신규

| 파일 | 역할 |
| --- | --- |
| `backend/rules.py` | 순수 함수 판정 엔진: A 월간 / B 가속(에피소드 상태머신) / C 12월 / D 공제·손실 수확 / E 인출 + 위기 모드 배너 판정. 입력·출력 모두 값 객체, I/O 없음 |
| `backend/market.py` | yfinance: ^NDX 일별 종가 2년(504거래일) 최고·최신 종가·하락률, TQQQ/JEPI/SGOV 현재가, USDKRW 환율 |
| `backend/db.py` (재작성) | state 1행 + logs append-only + pending 확인 게이트 상태 |
| `backend/claude_runner.py` | 구 run_claude 이식 + allowed_tools 파라미터·이미지 경로 지원 |
| `backend/vision.py` | 스크린샷 → 보유 티커·주수·평가액·원화수익·예수금 추출(불확실=null) |
| `backend/reply.py` | 판정 결과 → 회신 문장(rulebook.md 시스템 프롬프트 + 6절 가드레일) |
| `backend/bot.py` | 롱폴링 루프·chat_id 화이트리스트·명령 라우팅(/monthly /entry /december /withdraw /log /setday /phase)·사진 2단계 게이트(인라인 버튼)·이미지 즉시 삭제 |
| `backend/jobs/reminder.py` | 일 1회 판정: 적립일/12월 셋째 월요일(skip 반영)/ENTRY 월요일 리마인더 발송 |
| `prompts/rulebook.md` | 규칙서 원문(D4) — 자유 질문·회신 작성의 지식원 |
| `prompts/` 추출·회신 프롬프트 | 비전 추출 스펙, 봇 인격 가드레일 |
| `tests/` | pytest — 하단 검증 참조 |
| `deploy/systemd/bot.service` | 호스트 상시 서비스(Restart=always, venv+claude 로그인 재사용) |
| `deploy/systemd/reminder.timer/.service` | 매일 오전 1회 |
| `.github/workflows/ci.yml` | pytest 실행(매일 잡 실행 워크플로 아님) |

`notify.py`의 send_telegram(분할 전송)은 봇 송신부로 재사용. README·CLAUDE.md 프로젝트 절·.env.example(WHITELIST_CHAT_ID, NOTION_* 추가) 갱신.

## 구현 순서

- **Step 0. 안전선**: 백필 작업 커밋(D3, 사용자 승인) → 새 브랜치 `feat/telegram-rulebot`.
- **Step 1. 제거**: 위 삭제 표 실행 + import 0 broken 검증 + "비율 추천" 흔적 grep 전수 검증.
- **Step 2. 판정 엔진**: `rules.py` + `db.py`(state/logs) + pytest 유닛테스트 — 봇 없이 순수 함수만으로 완결·검증.
- **Step 3. 시장 데이터**: `market.py` + 캐시(판정 1회당 1조회) + 실측 스모크.
- **Step 4. 클로드 통합**: `claude_runner.py`(비전 확장) + `vision.py` + `reply.py` + `prompts/`. 샘플 스크린샷으로 추출 스모크.
- **Step 5. 봇**: `bot.py` 롱폴링(또는 D2-B 웹훅) — 화이트리스트, 사진→추출→**확인 게이트(생략 불가)**→판정→로그 저장, 명령어 7종, 규칙서 자유 질문. 불일치 포트폴리오 정지 로직.
- **Step 6. 리마인더**: `reminder.py` + systemd 유닛. ENTRY 5회 완료 시 자동 STEADY 전환.
- **Step 7. 노션 동기(옵션)** + `/log`.
- **Step 8. 수용 기준**: 시나리오 3건 통과 → CI 통과 → 변경 요약·삭제 모듈 목록·사용법 3줄 보고. 배포는 EC2에서 사용자와 함께(로컬 배포 명령 금지).

## 검증

- 유닛테스트(작업지시 8절): 가속 수명주기(1단 발동→잠김→2단→−10% 회복 재장전), 12월 |차이|≤1주 패스, 내림·잔돈 이월, 인출 70:30 산출, skip_december, 같은 날 1단+2단 순차 적용, 위기 배너 on/off 경계(−20/−10).
- 시나리오 3건: ①평시 월간(매수 주수만) ②−26% 최초 확인(1단 주문표+위기 문구) ③규칙서 불일치 스크린샷(게이트 정지).
- 각 Step 후: import 해소·잔존 참조 0(특히 bare import)·(프론트 유지 시) tsc 빌드.

## 비범위

- 증권사 API 자동 매매(주문표 생성까지만 — 실행은 항상 사람).
- 매일 정기 푸시 일체(리마인더 3종 외 금지).
- 기존 EC2 DB의 과거 뉴스 데이터 마이그레이션(테이블은 코드에서 제거, EC2 데이터 파일은 개편 배포 시 백업 후 정리).
- 규칙서 내용 자체의 개선·재설계(집행만).
