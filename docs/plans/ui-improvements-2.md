# UI 개선 2차 요구사항 (사용자 지시 2026-06-17)

> 컴팩트/세션 변경돼도 이 문서만 보면 이어서 실행 가능. 대상 `frontend/`. 빌드 금지(로컬).
> 색은 신호 3색(🟢ok/🟡caution/🔴alert) 유지. 진행 상태는 아래 체크박스.

## 현재 구조 (작업 전)
- `frontend/src/dashboard/` : Dashboard.tsx, Dashboard.css(통짜), HoldingsImpact/DigestView/ScanList/NewsRebound/DateList.tsx
- `frontend/src/shared/` : holdings.ts·signal.ts·format.ts·dateGroup.ts·scanReasons.ts
- `frontend/src/api/client.ts`, `frontend/src/index.css`(:root 색 변수)
- 탭: 보유종목(holdings)/다이제스트(digest)/기술반등(scan)/뉴스반등(news)

## 요구사항 (9개)

- [x] **1. homenav 비선택 항목 회색** — 선택 안 된 탭의 SVG 아이콘+텍스트를 회색(`--text-dim`).
  선택된 탭만 일반색(`--text`). (`.homenav__item` 기본 회색, `.is-active` 일반색)
- [x] **2. 비선택 밑줄 연하게** — 비선택 탭의 border-bottom(밑줄)을 살짝 연하게.
  Dashboard.tsx에서 inline 색을 `is-active ? color : color-mix(in srgb, ${color} 40%, transparent)`.
- [x] **3. color.css 전역 색 관리** — `frontend/src/color.css` 신설, 모든 색 토큰(:root) 이전 +
  하드코딩 색(`#fff`, `rgba(0,0,0,..)` 등)을 토큰화(`--white`,`--overlay`,`--shadow`). index.css/컴포넌트가 토큰 참조.
- [x] **4. 다이제스트 표→평문** — DigestView 지표를 `<table class=indic>` 대신 **평문 리스트**로.
  각 지표: `🟢 **지표명** - 값 · 변화 · 코멘트` 한 줄(자연 줄바꿈). 구 `.indic` 표 CSS 제거.
- [x] **5. datelist__count 삭제** — 사이드바 날짜의 `📈 N` 카운트 제거(DateList.tsx + `.datelist__count` CSS).
- [x] **6. 사이드바 폭 축소** — `.dash` 사이드바 260px → 약 200px(브랜드 텍스트보다 살짝 길게).
- [x] **7. 폴더 구조 nav별 분리 + CSS 분리** — 컴포넌트를 기능 폴더로, Dashboard.css를 컴포넌트별 CSS로.
  - 결정: 폴더명은 **영문**(holdings/digest/scan/news/sidebar) — import·툴링 안전(한글 폴더 회피). 사용자가 한글 원하면 변경.
  - 구조: `dashboard/Dashboard.tsx+css`(셸: dash·sidebar·topbar·homenav·card베이스·muted),
    `holdings/HoldingsImpact.tsx+css`, `digest/DigestView.tsx+css`, `scan/ScanList.tsx+css`,
    `news/NewsRebound.tsx+css`, `sidebar/DateList.tsx+css`. 각 컴포넌트가 자기 css import.
  - `git mv`로 이동, import 전수 갱신, 0 broken 검증(grep + tsc는 사용자 실행).
- [x] **8. 모바일 holding__impact 정렬 통일** — 컴팩트 행에서 holding__lev 길이차로 impact 위치가 어긋남.
  모바일 `.holding` 1열 grid 첫 컬럼을 **고정폭**(예 5rem)으로 → impact 위치 통일. lev는 ellipsis.
- [x] **9. 모바일 holding__buy 세로배치(달러 위)** — 모바일에서 usd(달러)를 위, pct(%)를 아래로 세로 배치.
  JSX에 `.holding__buy-sep`(·) 추가, 모바일 `.holding__buy { flex-direction:column }` + usd `order:-1`, sep/label 숨김.

## 실행 순서(권장)
1. 콘텐츠/CSS 수정(1,2,4,5,6,8,9) — 현재 파일에.
2. color.css(3) — 토큰 신설·치환.
3. 폴더 구조 분리(7) — 파일 이동 + CSS 분리 + import 갱신 + 검증. (가장 큰 작업, 마지막)

## 추가 요청 (2026-06-17 2차 배치)

- [x] **결정: 폴더명 영문** — 사용자 확정(holdings/digest/scan/news/sidebar). req 7 적용.
- [x] **10. nav translateY 제거** — `.homenav__item:hover/.is-active`의 `transform: translateY(-3px)` 삭제.
  hover 시 색만 밝아짐(회색→`--text`)으로 충분. transition도 color만.
- [x] **11. 6/3(수) 더미데이터** — `2026-06-03` 날짜로 digest+scans+news_scans 삽입(디자인 확인용).
  - 지표명은 holdings.ts 매칭 키워드 포함(Fed/메모리/capex/SMH 200/TSMC) → 보유종목 영향 계산되게.
  - scans 사유는 scanReasons 키워드(200일선/50일선/RSI/거래량). news는 high/medium/low 섞기.
  - 로컬 DB 삽입 스크립트(Anthropic 호출 없음). `python` + PYTHONUTF8=1.
- [x] **12. 다이제스트 가독성 개선** — 현재 평문 리스트가 읽기 힘듦. 재디자인:
  결론 콜아웃(신호색 좌측 보더 강조) + 지표를 "한 줄 헤더(이모지·지표명·수치 우측정렬) + 코멘트 아래줄(muted)" 블록으로.

## 실행 순서(권장)
1. 콘텐츠/CSS 수정(1,2,4,5,6,8,9,10,12) — 현재 파일에.
2. color.css(3) — 토큰 신설·치환.
3. 6/3 더미데이터(11) — DB 삽입.
4. 폴더 구조 분리(7) — 파일 이동 + CSS 분리 + import 갱신 + 검증. (가장 큰 작업, 마지막)

## 비범위 / 주의
- 로컬 빌드 금지. 검증은 편집 정확성 + grep(import 0 broken). 사용자가 dev/build 실행.
- 신호색·달러/원화 로직 유지. 데이터/백엔드 불변.
