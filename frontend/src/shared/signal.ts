// 신호등/지표 status → 라벨·색·이모지 매핑 (한 곳에 모아 하드코딩 방지).
// 색은 CSS 변수(index.css)와 짝을 이룬다.
import type { SignalLight, IndicatorStatus } from "../api/client";

export interface SignalMeta {
  label: string;
  cssVar: string; // var(--…) 색
  emoji: string;
}

export const SIGNAL_LIGHT: Record<SignalLight, SignalMeta> = {
  green: { label: "진입/유지", cssVar: "var(--ok)", emoji: "🟢" },
  yellow: { label: "주의", cssVar: "var(--caution)", emoji: "🟡" },
  red: { label: "디리스킹", cssVar: "var(--alert)", emoji: "🔴" },
  unknown: { label: "미상", cssVar: "var(--muted)", emoji: "⚪" },
};

export const INDICATOR_STATUS: Record<IndicatorStatus, SignalMeta> = {
  ok: { label: "양호", cssVar: "var(--ok)", emoji: "🟢" },
  caution: { label: "주의", cssVar: "var(--caution)", emoji: "🟡" },
  alert: { label: "경고", cssVar: "var(--alert)", emoji: "🔴" },
  na: { label: "해당없음", cssVar: "var(--muted)", emoji: "⚪" },
};

export function lightMeta(light: SignalLight | null): SignalMeta {
  return SIGNAL_LIGHT[light ?? "unknown"];
}
