// 티커 → 매우 짧은 한국어 소개(스캔 후보의 종목 정체 표시용).
// scanner UNIVERSE(28) + 더미 스캔/뉴스 + 보유 ETF 포함.
// 생성: 워크플로(ticker-descriptions) — 2개 렌즈 적대 검증 + 불일치 시 심판.
export const TICKER_DESC: Record<string, string> = {
  NVDA: "AI 반도체",
  AVGO: "통신·AI 칩",
  AMD: "CPU·GPU 반도체",
  MU: "메모리 반도체",
  MRVL: "데이터센터 칩",
  TSM: "대만 파운드리",
  ASML: "EUV 노광장비",
  LRCX: "반도체 식각 장비",
  AMAT: "반도체 장비",
  KLAC: "반도체 검사장비",
  INTC: "CPU 반도체",
  QCOM: "모바일 칩",
  ARM: "칩 설계 IP",
  SMCI: "AI 서버",
  ANET: "클라우드 네트워크",
  DELL: "PC·서버",
  MSFT: "SW·클라우드",
  GOOGL: "검색·광고",
  AMZN: "이커머스·클라우드",
  META: "소셜 광고",
  AAPL: "소비자 전자",
  ORCL: "기업 DB·클라우드",
  PLTR: "데이터 분석",
  CRWD: "엔드포인트 보안",
  NOW: "업무 자동화 SW",
  TXN: "아날로그 칩",
  ADI: "아날로그 칩",
  ON: "전력 반도체",
  SOFI: "핀테크 은행",
  RBLX: "UGC 게임 플랫폼",
  U: "게임 엔진",
  DIS: "종합 엔터테인먼트",
  NKE: "스포츠웨어",
  SMH: "반도체 ETF",
  QLD: "2× 나스닥100",
  SSO: "2× S&P500",
};

// 종목의 한국 통용 이름(인식용). 생성: 워크플로(ticker-names-ko) — 종목별 적대 검증.
export const TICKER_NAME: Record<string, string> = {
  NVDA: "엔비디아",
  AVGO: "브로드컴",
  AMD: "AMD",
  MU: "마이크론",
  MRVL: "마벨",
  TSM: "TSMC",
  ASML: "ASML",
  LRCX: "램리서치",
  AMAT: "어플라이드 머티리얼즈",
  KLAC: "KLA",
  INTC: "인텔",
  QCOM: "퀄컴",
  ARM: "ARM",
  SMCI: "슈퍼마이크로",
  ANET: "아리스타 네트웍스",
  DELL: "델",
  MSFT: "마이크로소프트",
  GOOGL: "구글(알파벳)",
  AMZN: "아마존",
  META: "메타",
  AAPL: "애플",
  ORCL: "오라클",
  PLTR: "팔란티어",
  CRWD: "크라우드스트라이크",
  NOW: "서비스나우",
  TXN: "텍사스 인스트루먼트",
  ADI: "ADI",
  ON: "온세미",
  SOFI: "소파이",
  RBLX: "로블록스",
  U: "유니티",
  DIS: "디즈니",
  NKE: "나이키",
  SMH: "반도체 ETF",
  QLD: "2× 나스닥100",
  SSO: "2× S&P500",
};

// 모르는 티커는 빈 문자열(표시 생략).
export function tickerDesc(ticker: string): string {
  return TICKER_DESC[ticker] ?? "";
}
export function tickerName(ticker: string): string {
  return TICKER_NAME[ticker] ?? "";
}
// '이름 · 섹터' 결합 라벨(둘 다 있고 다르면 결합, 아니면 있는 쪽만).
export function tickerLabel(ticker: string): string {
  const name = TICKER_NAME[ticker] ?? "";
  const desc = TICKER_DESC[ticker] ?? "";
  if (name && desc && name !== desc) return `${name} · ${desc}`;
  return name || desc || "";
}
