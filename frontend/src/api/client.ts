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

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`/api${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} (${path})`);
  return (await res.json()) as T;
}

export const api = {
  dates: () => get<DateEntry[]>("/dates"),
  latestDigest: () => get<Digest | null>("/digests/latest"),
  digest: (date: string) => get<Digest>(`/digests/${date}`),
  scans: (date: string) => get<Scan[]>(`/scans/${date}`),
  newsScans: (date: string) => get<NewsScan[]>(`/news-scans/${date}`),
};
