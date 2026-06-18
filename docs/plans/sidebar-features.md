# 사이드바 개편 + 검색분석 + 매수추적 + 날짜 달력모달 (2026-06-18 지시)

> 설계: 워크플로(sidebar-feature-design, 5에이전트 병렬+통합) 결과 + 사용자 확정.
> 컴팩트/세션 변경돼도 이 문서로 이어서 실행.
> 규칙: 로컬 빌드/Claude 잡 직접 실행 금지(사용자), 색은 color.css 토큰, 기능 단위 co-locate, 기존 패턴 재사용.

## 개정 2 (2026-06-18 추가지시 — 구현·검증 완료)
- **사이드바**: 그룹 태그 제거 → **데일리 모니터링 · 종목 검색** 2개만. 매수추적은 사이드바에서 뺌.
- **매수추적**: 별도 섹션 폐기 → **보유종목(HoldingsImpact) 화면 하단**에 `BuyTracking`(헤더 없이 캘린더: 날짜별 구입여부·종목별 매수단가) + 우상단 전환버튼 → `BuyChart`(SVG, 날짜별 매수단가). `holdings/` 에 co-locate.
- **달력**: 중앙 모달 → **stepper 바로 아래 앵커드 팝오버**(`.cal` absolute, `.cal__backdrop` 투명 fixed).
- **검색(2단계)**: ① **검색→yfinance 기본정보**(`quote.lookup`: Search+fast_info, 티커·영문명·한국코드 해석, 빠름·무료) ② **분석하기→Claude 웹검색**(`ticker_search.analyze`, run_claude) → `searches` 테이블 **날짜별 누적** 저장. 한글명은 yfinance가 못 잡아 기본정보 생략 후 바로 분석(Claude가 해석). "저장된 데이터 보기" → 티커별 테이블(날짜 누적). **NVDA·삼성전자·005930 실호출 테스트 통과**.
- **DB**: `search_tech`/`search_news`(ticker PK) 폐기 → `searches(ticker,date 누적)` 1테이블. `buys.price`(직접 입력/COALESCE).
- **폐기**: `ticker_resolve.py`, `scanner.analyze_one`(되돌림), `search/tech`·`search/news`·`resolve` 엔드포인트, `DateList`/`dateGroup`(NavList/DateCalendar로 대체).
- **제약 해제**: 사용자가 CLAUDE.md의 "검색 시 Claude 직접 웹검색=구독 차감" 금지 제약 삭제 → API 동기 Claude 호출 채택(호출당 구독 차감·수십초 지연).

## 확정 구조 — 사이드바 ≠ homenav (2단 내비)

사이드바는 **상위 화면(섹션) 전환**, homenav는 그 중 "데일리 모니터링" 화면 *내부* 날짜별 5탭.
homenav 5탭을 사이드바에 낱개로 미러링하지 **않는다**(이전 ★1-(a) 폐기).

```
WatchList
──────────────────────
현재 구현된 기능
  └ 데일리 모니터링      → section="daily" : 날짜 stepper/달력 + homenav(보유종목·다이제스트·반등포착·기술반등·뉴스반등)
새로 구현할 기능
  └ 종목 검색           → section="search": 티커/이름 검색 → 분석 카드
  └ 매수 추적           → section="buys"  : 매수 캘린더(구입/미구입·누적) + 매수단가 SVG 그래프
```

- 셸 상태: 신규 `section: "daily" | "search" | "buys"`(사이드바 선택) + 기존 `tab`(daily 내부 하위탭).
- 날짜 stepper/달력 모달·homenav는 `section==="daily"`일 때만 렌더. search/buys는 날짜 비종속.
- 보유종목 head 우측 설정(톱니) 버튼 = `section="buys"`로 가는 단축(매수추적은 별도 섹션이 정본).

## 목표 4개 서브시스템
1. **날짜 달력모달 + 데스크탑 stepper** — stepper 날짜 클릭 시 달력 모달로 날짜 선택, stepper를 웹에서도 표시(daily 화면 헤더).
2. **사이드바 = 섹션 내비** — 날짜목록 제거 → 2그룹(현재 구현=데일리 모니터링 / 새 기능=종목 검색·매수 추적).
3. **검색 분석** — 티커/이름 검색 → 뉴스·반등포착·기술반등·뉴스반등 분석 → DB 캐시.
4. **매수추적(별도 섹션)** — 매수 캘린더(구입/미구입·누적금액), 매수단가 선형 그래프. 보유종목 설정버튼=단축.

## 핵심 결정 (추천 = 채택)
| # | 질문 | 결정 | 이유(요약) |
|---|------|------|-----------|
| 1 | 사이드바 vs homenav 관계 | **확정: 2단 내비. 사이드바=section(daily/search/buys), homenav=daily 내부 하위탭. 미러링 안 함** | 사용자 확정("별도야"). tab/tabColor/ICONS/스와이프는 daily 내부에서 그대로 재사용 |
| 1b | 매수추적 위치 | **확정: 사이드바 별도 섹션(buys)** | 사용자 확정. 보유종목 head 설정버튼은 단축 |
| 2 | search를 스와이프 배열(TABS)에 포함? | **B: 미포함, daily 하위탭 아님(별도 섹션)** | 입력 기반 화면, 날짜 비종속 |
| 3 | on-demand 뉴스분석 API 직접 Claude vs 잡 분리 | **B: 기술분석만 API 즉시(yfinance), 뉴스는 ticker_analyze 잡(사용자 실행)** | CLAUDE.md '구독 임의 실행 금지' + 웹검색 지연 |
| 4 | 검색/매수 캐시 기존 테이블 합침 vs 신규 | **B: search_tech/search_news(ticker PK)+buys(date,ticker) 신규** | 날짜별 유니버스 집계 오염 방지 |
| 5 | 매수단가 그래프 라이브러리 vs SVG | **B: 커스텀 SVG 폴리라인** | 의존성 0 유지(프로젝트 방침), 데이터 소규모, 토큰 색 강제 |
| 6 | 신규 라이브러리 추가? | **A: 0개** | 달력=자체구현, 차트=SVG |
| 7 | 매수 쓰기 경로 | **A: POST /api/buys (CORS POST 허용)** | 영속+잡 종가채움 위해 백엔드 필요(localStorage 부적합) |
| 8 | 종가(price) 채움 | **B: 마감 후 buy_fill.py 잡(yfinance)** | '장 마감 시 저장' 요구, 결정적, 구독 아님 |

## 교차 관심사
- **상단 셸 통합(섹션·달력·stepper가 같은 헤더 건드림)** → Step 5 한 묶음에서 데스크탑/모바일 동시 검증.
  `.topbar`(모바일 ☰·dash__close) 유지, **stepper는 daily 화면 헤더로 이동해 데스크탑에도 표시**,
  homenav는 daily에서만, 달력 모달 z-index≥50(sticky homenav 위), stepper__date span→button.
- **DB**: 기존 컨벤션(connect/_now_utc/trading_day/ON CONFLICT/_*_row) 그대로. 신규 3테이블(아래).
- **Claude 호출 경계**: 구독 호출은 `ticker_analyze.py` 하나뿐 → **코드만 작성, 사용자가 실행**. API는 Claude 직접호출 금지.
- **이름→티커 단일 출처**: 프론트 TICKER_NAME 기준, 백엔드 ticker_resolve가 yfinance로 유니버스 밖 검증.
- **비파괴**: HoldingsImpact `onOpenBuys?` optional, section 추가 시 기존 tab 분기 보존.

## 신규 DB 테이블 (backend/db.py init_db)
- `search_tech(ticker PK, created_at, name, price, change_pct, reasons JSON, weak INT)` — 종목별 최신 기술분석.
- `search_news(ticker PK, created_at, change_pct, catalyst, view, confidence, sentiment, headline, sources JSON)` — 종목별 최신 뉴스/촉매.
- `buys(id PK, date, created_at, updated_at, ticker, amount, price NULL, bought INT, UNIQUE(date,ticker), idx_buys_date)` — 그날·종목 매수 1행.

## 구현 순서 (안전·독립 → 결정필요·위험)
- [x] **Step 0** 공유 아이콘: icons.tsx `search`(돋보기)·`settings`(톱니) 추가 — 완료(IconKey 확장 + SVG 2종).
- [x] **Step 1** DB 스키마 3테이블 + 헬퍼 — 완료. buys/search_tech/search_news + save/get/record/list/fill/missing 헬퍼, 임시DB 라운드트립 검증 통과.
- [ ] **Step 2** 결정적 백엔드: scanner.analyze_one(ticker) · ticker_resolve.py · buy_fill.py (yfinance, 첫 실행 사용자 권장).
- [ ] **Step 3** 프론트 데이터: client.ts `post<T>`+타입(Buy/SearchTech/SearchNews/Resolve)+api 메서드, tickers.ts 역매핑/searchTickers.
- [ ] **Step 4** search/ 폴더 골격(SearchView+search.css, dash__empty 패턴) — 렌더 전이라 무해.
- [ ] **Step 5 ★** 셸 재배치 통합: section 상태 · NavList(사이드바 2그룹) · DateCalendar.tsx · stepper를 daily 헤더로(데스크탑+모바일) · Dashboard 섹션 분기. 데스크탑/모바일 동시 검증.
- [ ] **Step 6** SearchView 본배선(자동완성→resolve→searchTech→searchOf→buildConviction 카드 재사용).
- [ ] **Step 7 ★** 쓰기 경로: api.py allow_methods POST + docstring 갱신 + search/buys 엔드포인트.
- [ ] **Step 8** 매수추적 섹션 UI: BuyTracking.tsx(캘린더+구입/미구입+누적) · BuyChart.tsx(SVG) · 보유종목 설정버튼=단축 · Dashboard buys 로드/주입/refetch.
- [ ] **Step 9** ticker_analyze.py(Claude 구독, **코드만**) — 사용자 `python -m backend.jobs.ticker_analyze NVDA …`.
- [ ] **Step 10** 죽은코드 정리(DateList/groupByWeek 사용처 확인 후)·전수 검증(grep import 0, 사용자 build).

## 비범위 / 주의
- Claude 잡(digest/news_scan/holdings_news/ticker_analyze) 직접 실행, npm build/dev·tsc·vite 실행 → **사용자**.
- yfinance 외부호출(buy_fill/ticker_resolve/analyze_one) 첫 실행 → 사용자 권장.
- 배포·운영 SQLite 마이그레이션, git push → 사용자.
- search UI 고도화·BuyChart 툴팁/축 미세디자인은 MVP 이후.
