// 다이제스트 신호(신호등 + 지표)를 내 보유종목(QLD/SSO/SMH) 영향으로 환산.
// 프론트에서 결정적으로 계산 — API 비용 없음. 지표명은 부분일치(키워드)로 매칭한다.
import type { Digest, SignalLight, IndicatorStatus } from "../api/client";

export type Impact = "positive" | "neutral" | "caution" | "negative";

export interface ImpactMeta {
  label: string;
  cssVar: string;
  emoji: string;
}

export const IMPACT_META: Record<Impact, ImpactMeta> = {
  positive: { label: "우호적", cssVar: "var(--ok)", emoji: "▲" },
  neutral: { label: "중립", cssVar: "var(--muted)", emoji: "■" },
  caution: { label: "주의", cssVar: "var(--caution)", emoji: "▾" },
  negative: { label: "위험", cssVar: "var(--alert)", emoji: "▼" },
};

const STATUS_SCORE: Record<IndicatorStatus, number> = { ok: 1, caution: -1, alert: -2, na: 0 };
const LIGHT_SCORE: Record<SignalLight, number> = { green: 1, yellow: -1, red: -2, unknown: 0 };

interface Driver {
  match: string; // 지표명 부분일치 키워드
  weight: number;
  label: string;
}

interface HoldingDef {
  ticker: string;
  name: string;
  leverage: string;
  leveraged: boolean;
  drivers: Driver[];
  lightWeight: number; // 시장 전반(신호등)이 이 종목에 주는 영향
}

// 종목별 민감 지표와 가중치 — 레버리지 ETF는 금리에, 반도체 ETF는 capex/메모리/SMH선에 민감.
const HOLDINGS: HoldingDef[] = [
  {
    ticker: "SMH", name: "반도체 ETF", leverage: "반도체(1×)", leveraged: false,
    lightWeight: 1,
    drivers: [
      { match: "capex", weight: 2, label: "하이퍼스케일러 capex" },
      { match: "메모리", weight: 2, label: "메모리 가격" },
      { match: "SMH 200", weight: 3, label: "SMH 200일선" },
      { match: "TSMC", weight: 1, label: "TSMC 매출" },
      { match: "Fed", weight: 0.5, label: "금리" },
    ],
  },
  {
    ticker: "QLD", name: "2× 나스닥100", leverage: "2× 나스닥100", leveraged: true,
    lightWeight: 1.5,
    drivers: [
      { match: "Fed", weight: 2, label: "금리" },
      { match: "SMH 200", weight: 1.5, label: "반도체 추세" },
      { match: "capex", weight: 1.5, label: "빅테크 capex" },
      { match: "메모리", weight: 0.5, label: "메모리" },
    ],
  },
  {
    ticker: "SSO", name: "2× S&P500", leverage: "2× S&P500", leveraged: true,
    lightWeight: 2,
    drivers: [
      { match: "Fed", weight: 2.5, label: "금리" },
      { match: "SMH 200", weight: 0.5, label: "반도체" },
      { match: "capex", weight: 0.5, label: "capex" },
    ],
  },
];

function impactOf(avg: number): Impact {
  if (avg >= 0.5) return "positive";
  if (avg >= -0.25) return "neutral";
  if (avg >= -1.0) return "caution";
  return "negative";
}

export interface HoldingImpact {
  ticker: string;
  name: string;
  leverage: string;
  leveraged: boolean;
  impact: Impact;
  meta: ImpactMeta;
  drivers: { label: string; status: IndicatorStatus }[]; // 영향 큰 동인 상위
  interpretation: string;
}

function interpret(impact: Impact, leveraged: boolean): string {
  switch (impact) {
    case "positive":
      return leveraged ? "레버리지가 상승을 증폭 — 비중 유지/확대 우호적" : "추세 우호적 — 비중 유지";
    case "neutral":
      return "뚜렷한 방향성 없음 — 관망";
    case "caution":
      return leveraged ? "경고 신호 — 2× 레버리지는 하락도 증폭, 신규 진입 신중" : "경고 신호 — 관찰 강화";
    case "negative":
      return leveraged ? "디리스킹 구간 — 2× 레버리지 비중 축소 검토" : "추세 훼손 — 비중 점검";
  }
}

// ── 분할매수 가이드 ──────────────────────────────────────────────
// 자본 1500만원을 1달(≈21거래일)에 분할. 신호등으로 '오늘 투입 강도'(≤100%)를,
// 종목 영향으로 'SMH:QLD:SSO 비율'을 정한다. 전부 참고용(매매 지시 아님).
export const BUDGET_KRW = 15_000_000;
export const DCA_DAYS = 21;
// 환율(고정, 가이드 표시용) — 가끔 갱신. yfinance KRW=X, 2026-06-17 기준 ≈ 1,513.
export const USDKRW = 1513;
const round1k = (n: number) => Math.round(n / 1000) * 1000; // 천원 단위로
const DAILY_BASE = round1k(BUDGET_KRW / DCA_DAYS); // ≈ 714,000

// 진입 신호 규칙: 신호 양호=정상(100%) / 1경고=절반(50%) / 2경고+=대기(0%).
const PACE: Record<SignalLight, number> = { green: 1.0, yellow: 0.5, red: 0.0, unknown: 0.5 };
// 영향이 좋을수록 비중↑(레버리지는 경고 시 자연히 축소 → SSO/현금 방어).
const IMPACT_WEIGHT: Record<Impact, number> = { positive: 1.2, neutral: 1.0, caution: 0.6, negative: 0.3 };

export interface BuyRow {
  ticker: string;
  pct: number;     // 3종 내 비중(%)
  amount: number;  // 오늘 매수 금액(원)
}
export interface BuyGuide {
  pace: number;        // 0~1 (오늘 투입 강도)
  paceLabel: string;
  dailyBase: number;
  todayTotal: number;  // 오늘 총 투입액
  rows: BuyRow[];      // holdings 와 같은 순서
}

export function buyGuide(holdings: HoldingImpact[], light: SignalLight): BuyGuide {
  const pace = PACE[light] ?? 0.5;
  const todayTotal = round1k(DAILY_BASE * pace);
  const weights = holdings.map((h) => IMPACT_WEIGHT[h.impact]);
  const sum = weights.reduce((a, b) => a + b, 0) || 1;
  const rows: BuyRow[] = holdings.map((h, i) => {
    const frac = weights[i] / sum;
    return { ticker: h.ticker, pct: Math.round(frac * 100), amount: round1k(todayTotal * frac) };
  });
  const paceLabel = pace >= 1 ? "정상 투입" : pace > 0 ? "절반 투입" : "대기 (현금 보유)";
  return { pace, paceLabel, dailyBase: DAILY_BASE, todayTotal, rows };
}

export function analyzeHoldings(digest: Digest): HoldingImpact[] {
  return HOLDINGS.map((h) => {
    let score = 0;
    let totalWeight = h.lightWeight;
    const contrib: { label: string; status: IndicatorStatus; impactAbs: number }[] = [];

    for (const d of h.drivers) {
      const ind = digest.indicators.find((i) => i.name.includes(d.match));
      if (!ind) continue;
      const s = STATUS_SCORE[ind.status];
      score += s * d.weight;
      totalWeight += d.weight;
      contrib.push({ label: d.label, status: ind.status, impactAbs: Math.abs(s * d.weight) });
    }
    score += LIGHT_SCORE[digest.signal_light] * h.lightWeight;

    const avg = totalWeight > 0 ? score / totalWeight : 0;
    const impact = impactOf(avg);
    const drivers = contrib
      .filter((c) => c.status !== "na")
      .sort((a, b) => b.impactAbs - a.impactAbs)
      .slice(0, 3)
      .map(({ label, status }) => ({ label, status }));

    return {
      ticker: h.ticker, name: h.name, leverage: h.leverage, leveraged: h.leveraged,
      impact, meta: IMPACT_META[impact], drivers,
      interpretation: interpret(impact, h.leveraged),
    };
  });
}
