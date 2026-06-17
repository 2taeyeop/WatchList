// 기술반등(scans) + 뉴스반등(news_scans)을 종목별로 합쳐 '반등 확신도'로 등급화.
// 프론트에서 결정적으로 계산(추가 API 없음). 같은 날 기준:
//   A = 촉매 + 기술 확인 동반(confluence) · B = 기술만 · C = 촉매만.
// 핵심 관점: '둘 다'는 최고 등급이지 노출 게이트가 아님 - 단독 신호도 등급만 낮춰 보여준다.
import type { Scan, NewsScan } from "../api/client";

export type Grade = "A" | "B" | "C";

export interface GradeMeta {
  grade: Grade;
  label: string; // 짧은 라벨
  cssVar: string;
  headline: string; // 한 줄 의미
  rationale: string; // 왜 이 등급 + 주의
}

const GRADE_META: Record<Grade, GradeMeta> = {
  A: {
    grade: "A",
    label: "동반 확인",
    cssVar: "var(--ok)",
    headline: "촉매 + 기술",
    rationale:
      "이유(촉매)와 가격 확인이 함께 잡힌 최고 확신 구간 - 시장 신호등과 무효화 레벨만 점검하세요.",
  },
  B: {
    grade: "B",
    label: "기술만",
    cssVar: "var(--caution)",
    headline: "기술",
    rationale:
      "가격은 턴했지만 이유가 미확인 - 데드캣 바운스 가능, 촉매·추세 추가 확인을 권장합니다.",
  },
  C: {
    grade: "C",
    label: "촉매만",
    cssVar: "var(--muted)",
    headline: "촉매",
    rationale:
      "호재(이유)는 있으나 시장이 아직 확인 안 함 - 떨어지는 칼날 주의, 이평 회복·거래량 확인을 기다리세요.",
  },
};

export interface ConvictionItem {
  ticker: string;
  meta: GradeMeta;
  tech: Scan | null;
  news: NewsScan | null;
  invalidation: string; // 무효화(손절) 힌트
}

// 되돌린 이동평균선을 기준으로 무효화 레벨을 안내(scanner 의 reason 과 1:1).
function invalidationOf(tech: Scan | null): string {
  if (!tech) return "기술 확인 전 - 50/200일선 회복·거래량 동반 확인 후 진입 권장.";
  const r = tech.reasons.join(" ");
  if (r.includes("200일선")) return "200일선 아래로 재이탈 시 반등 무효.";
  if (r.includes("50일선")) return "50일선 아래로 재이탈 시 반등 무효.";
  return "직전 저점/되돌린 구간 이탈 시 반등 무효.";
}

const ORDER: Record<Grade, number> = { A: 0, B: 1, C: 2 };
const CONF_RANK: Record<string, number> = { high: 3, medium: 2, low: 1 };

export function buildConviction(scans: Scan[], news: NewsScan[]): ConvictionItem[] {
  const byTicker = new Map<string, { tech: Scan | null; news: NewsScan | null }>();
  for (const s of scans) byTicker.set(s.ticker, { tech: s, news: null });
  for (const n of news) {
    const cur = byTicker.get(n.ticker);
    if (cur) cur.news = n;
    else byTicker.set(n.ticker, { tech: null, news: n });
  }

  const items: ConvictionItem[] = [];
  for (const [ticker, { tech, news }] of byTicker) {
    const grade: Grade = tech && news ? "A" : tech ? "B" : "C";
    items.push({ ticker, meta: GRADE_META[grade], tech, news, invalidation: invalidationOf(tech) });
  }

  // 등급 우선 → 같은 등급은 기술 신호 수·뉴스 확신 순으로 강한 것 먼저.
  items.sort((a, b) => {
    const g = ORDER[a.meta.grade] - ORDER[b.meta.grade];
    if (g !== 0) return g;
    const ta = a.tech?.reasons.length ?? 0;
    const tb = b.tech?.reasons.length ?? 0;
    if (tb !== ta) return tb - ta;
    return (CONF_RANK[b.news?.confidence ?? ""] ?? 0) - (CONF_RANK[a.news?.confidence ?? ""] ?? 0);
  });
  return items;
}

export function gradeCounts(items: ConvictionItem[]): Record<Grade, number> {
  const c: Record<Grade, number> = { A: 0, B: 0, C: 0 };
  for (const it of items) c[it.meta.grade]++;
  return c;
}

// 탭 색: 가장 높은 등급의 색(A>B>C, 없으면 muted).
export function topGradeColor(items: ConvictionItem[]): string {
  if (items.some((i) => i.meta.grade === "A")) return "var(--ok)";
  if (items.some((i) => i.meta.grade === "B")) return "var(--caution)";
  return "var(--muted)";
}
