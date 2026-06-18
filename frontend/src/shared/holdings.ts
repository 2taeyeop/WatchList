// 다이제스트 신호(신호등 + 지표)를 내 보유종목(QLD/SSO/SMH) 영향으로 환산.
// 프론트에서 결정적으로 계산 - API 비용 없음. 지표명은 부분일치(키워드)로 매칭한다.
import type { Digest, SignalLight, IndicatorStatus, HoldingsNews } from "../api/client";
import type { ConvictionItem } from "./conviction";

export type Impact = "positive" | "neutral" | "caution" | "negative";

export interface ImpactMeta {
  label: string;
  cssVar: string;
  emoji: string;
}

export const IMPACT_META: Record<Impact, ImpactMeta> = {
  positive: { label: "우호적", cssVar: "var(--ok)", emoji: "▲" },
  neutral: { label: "중립", cssVar: "var(--muted)", emoji: "■" },
  caution: { label: "주의", cssVar: "var(--caution)", emoji: "▽" },
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

// 종목별 민감 지표와 가중치 - 레버리지 ETF는 금리에, 반도체 ETF는 capex/메모리/SMH선에 민감.
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

// 분할매수 추적용 - 보유 3종 티커(매수 캘린더/그래프에서 사용).
export const HOLDING_TICKERS = HOLDINGS.map((h) => h.ticker);

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
      return leveraged ? "레버리지가 상승을 증폭 - 비중 유지/확대 우호적" : "추세 우호적 - 비중 유지";
    case "neutral":
      return "뚜렷한 방향성 없음 - 관망";
    case "caution":
      return leveraged ? "경고 신호 - 2× 레버리지는 하락도 증폭, 신규 진입 신중" : "경고 신호 - 관찰 강화";
    case "negative":
      return leveraged ? "디리스킹 구간 - 2× 레버리지 비중 축소 검토" : "추세 훼손 - 비중 점검";
  }
}

// ── 분할매수 가이드 ──────────────────────────────────────────────
// 자본 $10,000 을 1달(≈21거래일)에 분할. 신호등으로 '오늘 투입 강도'(≤100%)를,
// 종목 영향으로 'SMH:QLD:SSO 비율'을 정한다. 전부 참고용(매매 지시 아님).
// (예산 액수만 바꾸려면 BUDGET_USD 만 수정)
export const BUDGET_USD = 10_000;
export const DCA_DAYS = 21;
export const DAILY_BASE = BUDGET_USD / DCA_DAYS; // ≈ $476/일

// 진입 신호 규칙(base): 신호 양호=정상(100%) / 1경고=절반(50%) / 2경고+=대기(0%).
const PACE: Record<SignalLight, number> = { green: 1.0, yellow: 0.5, red: 0.0, unknown: 0.5 };
// 영향이 좋을수록 비중↑(레버리지는 경고 시 자연히 축소 → SSO/현금 방어).
const IMPACT_WEIGHT: Record<Impact, number> = { positive: 1.2, neutral: 1.0, caution: 0.6, negative: 0.3 };

// ── 페이스 보정 ──────────────────────────────────────────────
// base(신호등)에 ① 다이제스트 종목영향 ② 구성종목 반등 ③ 구성종목 뉴스를 더해 미세조정.
const IMPACT_SCORE: Record<Impact, number> = { positive: 1, neutral: 0, caution: -1, negative: -2 };
// 구성종목 최신 뉴스 감성(양방향).
const SENT_SCORE: Record<HoldingsNews["sentiment"], number> = { positive: 1, neutral: 0, negative: -1 };
// 내 ETF(특히 SMH)의 핵심 구성종목 = 반도체. 반등 포착이 이 종목에 뜨면 페이스 소폭↑.
export const SMH_CONSTITUENTS = new Set([
  "NVDA", "AVGO", "AMD", "MU", "MRVL", "TSM", "ASML", "LRCX", "AMAT", "KLAC",
  "INTC", "QCOM", "ARM", "TXN", "ADI", "ON",
]);
const clamp = (n: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, n));

export interface PaceAdjustment {
  label: string;
  delta: number; // 페이스 가감(0~1 스케일)
}
export interface PaceBreakdown {
  base: number; // 신호등 기본 페이스
  adjustments: PaceAdjustment[];
  pace: number; // 최종(0~1, 클램프)
  capped: boolean; // 🔴 디리스킹 상한(0.25) 적용 여부
}

// 신호등(base) + 다이제스트 종목영향 + 구성종목 반등 + 구성종목 뉴스 → '오늘 투입 강도'.
// 가드: 🔴이면 상한 0.25(추세 역행 과매수 차단), 구성종목 반등 가산은 🟢/🟡에서만.
export function computePace(
  holdings: HoldingImpact[],
  light: SignalLight,
  candidates: ConvictionItem[] = [],
  holdingsNews: HoldingsNews[] = [],
): PaceBreakdown {
  const base = PACE[light] ?? 0.5;
  const adjustments: PaceAdjustment[] = [];

  // ① 내 종목 영향 틸트(다이제스트 지표 → SMH/QLD/SSO 영향 평균)
  if (holdings.length) {
    const mean = holdings.reduce((a, h) => a + IMPACT_SCORE[h.impact], 0) / holdings.length;
    const tilt = clamp(mean * 0.15, -0.25, 0.25);
    if (Math.abs(tilt) >= 0.005) adjustments.push({ label: "내 종목 영향", delta: tilt });
  }

  // ② 구성종목(반도체) 반등 촉매 - 기술 확인된 A/B만, 🔴에선 제외
  if (light !== "red") {
    let boost = 0;
    for (const c of candidates) {
      if (!SMH_CONSTITUENTS.has(c.ticker)) continue;
      if (c.meta.grade === "A") boost += 0.06;
      else if (c.meta.grade === "B") boost += 0.03;
      // C(촉매만)는 기술 미확인 → 가산하지 않음
    }
    boost = Math.min(0.12, boost);
    if (boost > 0) adjustments.push({ label: "구성종목 반등(반도체)", delta: boost });
  }

  // ③ 구성종목 최신 뉴스 감성(양방향) - 호재면 페이스↑, 악재면 페이스↓
  if (holdingsNews.length) {
    const mean = holdingsNews.reduce((a, n) => a + SENT_SCORE[n.sentiment], 0) / holdingsNews.length;
    const tilt = clamp(mean * 0.2, -0.2, 0.2);
    if (Math.abs(tilt) >= 0.005) adjustments.push({ label: "구성종목 뉴스", delta: tilt });
  }

  let pace = clamp(base + adjustments.reduce((a, x) => a + x.delta, 0), 0, 1);
  let capped = false;
  if (light === "red" && pace > 0.25) {
    pace = 0.25;
    capped = true;
  }
  return { base, adjustments, pace, capped };
}

function paceLabelFor(pace: number): string {
  if (pace >= 0.85) return "정상 투입";
  if (pace >= 0.55) return "적극 투입";
  if (pace >= 0.3) return "절반 투입";
  if (pace > 0) return "소액 투입";
  return "대기 (현금 보유)";
}

export interface BuyRow {
  ticker: string;
  pct: number; // 3종 내 비중(%)
  amount: number; // 오늘 매수 금액($)
}
export interface BuyGuide {
  pace: number; // 0~1 (오늘 투입 강도)
  paceLabel: string;
  breakdown: PaceBreakdown; // 페이스 계산 근거
  dailyBase: number;
  todayTotal: number; // 오늘 총 투입액
  rows: BuyRow[]; // holdings 와 같은 순서
}

export function buyGuide(
  holdings: HoldingImpact[],
  light: SignalLight,
  candidates: ConvictionItem[] = [],
  holdingsNews: HoldingsNews[] = [],
): BuyGuide {
  const breakdown = computePace(holdings, light, candidates, holdingsNews);
  const pace = breakdown.pace;
  const todayTotal = DAILY_BASE * pace;
  const weights = holdings.map((h) => IMPACT_WEIGHT[h.impact]);
  const sum = weights.reduce((a, b) => a + b, 0) || 1;
  const rows: BuyRow[] = holdings.map((h, i) => {
    const frac = weights[i] / sum;
    return { ticker: h.ticker, pct: Math.round(frac * 100), amount: todayTotal * frac };
  });
  return { pace, paceLabel: paceLabelFor(pace), breakdown, dailyBase: DAILY_BASE, todayTotal, rows };
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
