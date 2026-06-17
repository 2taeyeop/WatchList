# UI 개선 요구사항 (사용자 지시 2026-06-17)

> 컴팩트되더라도 이 문서만 보면 정확히 구현할 수 있도록 작성. 대상은 `frontend/`만.
> 신호 3색(🟢ok/🟡caution/🔴alert)·달러 표기·기존 데이터/백엔드는 그대로 둔다.

## 현재 상태 (구현 전 기준선)
- 대시보드: 좌측 사이드바(날짜 목록) + 우측 `dash__main`에 4영역을 **세로로 모두** 표시
  - 4영역 컴포넌트: `HoldingsImpact`(보유종목 영향+분할매수) · `DigestView`(다이제스트) ·
    `ScanList`(기술 반등 스캔) · `NewsRebound`(📰 뉴스 반등) — [Dashboard.tsx](../../frontend/src/dashboard/Dashboard.tsx)
- 테마: 슬레이트/네이비. CSS 변수는 [index.css](../../frontend/src/index.css) `:root`
  (`--bg:#0f172a`, `--panel:#1e293b`, `--panel-2:#273449`, `--border:#334155`, `--text:#e2e8f0`,
   `--text-dim:#94a3b8`, `--accent:#38bdf8`; 신호색 `--ok/--caution/--alert/--muted`).
- 컴포넌트 스타일은 [Dashboard.css](../../frontend/src/dashboard/Dashboard.css).

## 요구사항 (6개)

### 1. `.holding` 카드 테두리 = 전체 border (top/left만 쓰는 것 금지)
- **현재**: `.holding { border:1px solid var(--border); border-top:3px solid var(--muted); }`
  + `HoldingsImpact.tsx`에서 `style={{ borderTopColor: h.meta.cssVar }}`.
- **목표**: **전체 4면 border**로 눈에 띄게 (예: `border: 2px solid <impact색>`).
  `HoldingsImpact.tsx`의 `borderTopColor` → `borderColor`로.
- **추가**: `.conclusion`은 border 불필요 → 현재 `border-left:3px solid var(--accent)` **제거**.

### 2. `.indic`(지표 표) status 셀 = 이모지만
- **현재**: [DigestView.tsx](../../frontend/src/dashboard/DigestView.tsx)에서 `{m.emoji} {m.label}`
  (예 "🟢 양호").
- **목표**: **`{m.emoji}`만** (예 "🟢"). 라벨 텍스트 제거. (원하면 `title={m.label}` 툴팁으로 유지)

### 3. 모바일 반응형
- **현재**: `.dash { grid-template-columns: 260px 1fr }` 고정. 반응형은 holdings grid 720px 하나뿐.
- **목표**: 좁은 화면(≤~640px)에서 레이아웃 세로 스택 — 사이드바(날짜)를 **상단 드로어/셀렉트**로,
  `dash__main` 전체폭. 카드·지표 표(`.indic`)·holdings grid 모두 좁은 폭에서 깨지지 않게.
- breakpoint 제안: 모바일 ≤640px, 태블릿 ≤960px.

### 4. 첫 화면 = 4개 카드(랜딩) → 클릭하면 해당 영역으로
- **목표**: 첫 화면에 4영역을 **진입 카드 4개**로 보여주고, 카드를 누르면 그 영역 상세만 표시
  (+ 뒤로가기). 4영역 = ① 보유종목 영향+분할매수 ② 다이제스트 ③ 기술 반등 스캔 ④ 뉴스 반등.
- 구현: `Dashboard`에 `view` 상태(`'home' | 'holdings' | 'digest' | 'scan' | 'news'`).
  home이면 4카드 그리드, 그 외엔 해당 컴포넌트 + 뒤로가기. 날짜 선택은 유지.

### 5. 랜딩 4카드 상단에 분할매수 요약
- **목표**: 4카드 **위**에 간략 요약 — 분할매수 종목명 + 비율 + 금액 + 색(초록/중립 등).
- 데이터: `buyGuide()`([holdings.ts](../../frontend/src/shared/holdings.ts))로 이미 계산됨
  (SMH/QLD/SSO 비율·달러·각 종목 impact 색). 한 줄 칩 형태 예:
  `SMH 38% $177 🟢 · QLD 31% $147 ⚪ · SSO 31% $147 ⚪` + 오늘 투입 강도/합계.

### 6. 디자인 컨셉 = 블랙 그레이톤
- **목표**: 슬레이트/네이비 → **블랙-그레이 중립톤**. [index.css](../../frontend/src/index.css) `:root`
  팔레트만 교체(컴포넌트는 변수 참조라 대부분 자동 반영). 신호 3색은 유지.
- 제안 팔레트(조정 가능): `--bg:#0a0a0a` · `--panel:#161616` · `--panel-2:#1f1f1f` ·
  `--border:#2a2a2a` · `--text:#e6e6e6` · `--text-dim:#8a8a8a` · `--accent:#d4d4d4`(또는 포인트색).

## 열린 결정 (구현 전 확인하면 좋음)
- 네비(4): 뒤로가기 버튼 위치 / 모바일 사이드바를 드로어 vs 상단 셀렉트 중 무엇으로?
- 색(6): accent를 회색 계열로 완전 무채색? 아니면 한 가지 포인트색(예 흰색/엷은 청회색) 허용?
- 5의 요약 칩: home에서 날짜 바꾸기 허용할지(요약은 선택 날짜의 다이제스트 기준).

## 구현 순서(권장)
1. (6) 블랙그레이 팔레트 교체 — 변수만, 영향 광범위하니 먼저.
2. (1)(2) 작은 컴포넌트 수정(holding border, indic 이모지).
3. (4)(5) 랜딩 4카드 + 상단 분할매수 요약 + 뷰 전환.
4. (3) 모바일 반응형 마무리.
5. `npm run build`로 타입/빌드 검증.

## 비범위
- 백엔드·데이터·라우팅 라이브러리 추가 없음(상태 기반 뷰 전환). 신호 색/달러 로직 유지.
