// 백엔드(backend/api.py·db.py)와 1:1로 맞춘 타입 + fetch 래퍼.
// 프론트는 항상 상대경로 /api 사용 (개발=Vite 프록시, 운영=nginx 프록시).

export type SignalLight = "green" | "yellow" | "red" | "unknown";
export type IndicatorStatus = "ok" | "caution" | "alert" | "na";

export interface Indicator {
  name: string;
  status: IndicatorStatus;
  value?: string;
  change?: string;
  comment?: string;
  source?: string;
}

export interface Digest {
  date: string; // YYYY-MM-DD
  created_at: string;
  prose: string;
  signal_light: SignalLight;
  indicators: Indicator[];
  conclusion: string;
}

export interface DateEntry {
  date: string;
  signal_light: SignalLight | null;
  scan_count: number;
}

export interface Scan {
  ticker: string;
  price: number;
  change_pct: number;
  reasons: string[];
}

export interface NewsScan {
  ticker: string;
  change_pct: number; // 전일 하락률
  catalyst: string; // 호재 요약
  view: string; // 반등 관점
  confidence: string; // high | medium | low
  sources: string[];
}

export type Sentiment = "positive" | "neutral" | "negative";

export interface HoldingsNews {
  ticker: string; // 내 ETF 구성종목
  sentiment: Sentiment;
  headline: string; // 최신 핵심 뉴스 한 줄
  source: string;
}

// ── 검색 1단계: yfinance 기본정보 ──
export interface Quote {
  ticker: string;
  name: string;
  market: string; // KR | US
  price: number | null;
  change_pct: number | null;
  currency: string;
}

// ── 검색 분석(티커별·날짜별 누적) ──
export interface SearchAnalysis {
  ticker: string;
  date: string; // 분석 날짜
  created_at: string;
  name: string;
  market: string; // KR | US
  price: number | null;
  change_pct: number | null;
  summary: string;
  catalyst: string;
  view: string;
  sentiment: Sentiment;
  sources: string[];
}

// ── 분할매수 추적 ──
export interface Buy {
  date: string;
  ticker: string;
  amount: number;
  price: number | null; // 매수단가(종가) — buy_fill 잡이 채움
  bought: boolean;
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`/api${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} (${path})`);
  return (await res.json()) as T;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} (${path})`);
  return (await res.json()) as T;
}

export const api = {
  dates: () => get<DateEntry[]>("/dates"),
  latestDigest: () => get<Digest | null>("/digests/latest"),
  digest: (date: string) => get<Digest>(`/digests/${date}`),
  scans: (date: string) => get<Scan[]>(`/scans/${date}`),
  newsScans: (date: string) => get<NewsScan[]>(`/news-scans/${date}`),
  holdingsNews: (date: string) => get<HoldingsNews[]>(`/holdings-news/${date}`),
  // 검색 1단계: yfinance 기본정보(빠름). 2단계 search: Claude 웹검색 분석·저장(느림).
  quote: (query: string) => get<Quote>(`/quote?q=${encodeURIComponent(query)}`),
  search: (query: string) => post<SearchAnalysis>("/search", { query }),
  searches: () => get<SearchAnalysis[]>("/searches"),
  // 매수추적: date 지정 시 그날, 없으면 전체(그래프/누적용).
  buys: (date?: string) =>
    get<Buy[]>(date ? `/buys?date=${date}` : "/buys"),
  recordBuy: (b: {
    ticker: string;
    amount: number;
    bought: boolean;
    date?: string;
    price?: number | null;
  }) => post<{ ok: boolean }>("/buys", b),
};
