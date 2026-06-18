// 매수단가 선형 그래프(SVG, 의존성 0) - 보유 3종(SMH/QLD/SSO)의 날짜별 매수단가.
import type { Buy } from "../api/client";
import { HOLDING_TICKERS } from "../shared/holdings";

// 종목별 색(color.css 토큰) - 그래프 선·범례 + 캘린더 칩이 공유.
export const TICKER_COLORS: Record<string, string> = {
  SMH: "var(--ok)",
  QLD: "var(--caution)",
  SSO: "var(--accent)",
};
const W = 600;
const H = 260;
const PAD = { l: 48, r: 12, t: 12, b: 28 };

interface Props {
  buys: Buy[];
}

export default function BuyChart({ buys }: Props) {
  // 구입 + 단가 있는 것만 그린다.
  const pts = buys.filter((b) => b.bought && b.price != null);
  if (pts.length === 0) {
    return <div className="dash__empty">매수단가 데이터가 없습니다.</div>;
  }

  const dates = [...new Set(pts.map((b) => b.date))].sort();
  const prices = pts.map((b) => b.price as number);
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const span = max - min || 1;

  const innerW = W - PAD.l - PAD.r;
  const innerH = H - PAD.t - PAD.b;
  const x = (date: string) =>
    PAD.l +
    (dates.length === 1
      ? innerW / 2
      : (dates.indexOf(date) / (dates.length - 1)) * innerW);
  const y = (price: number) => PAD.t + innerH - ((price - min) / span) * innerH;

  const series = HOLDING_TICKERS.map((t) => ({
    ticker: t,
    points: pts
      .filter((b) => b.ticker === t)
      .sort((a, b) => a.date.localeCompare(b.date)),
  })).filter((s) => s.points.length > 0);

  return (
    <div className="buychart">
      <svg viewBox={`0 0 ${W} ${H}`} className="buychart__svg" role="img" aria-label="매수단가 그래프">
        {/* y축(최대/최소가) */}
        <text x={PAD.l - 8} y={PAD.t + 8} className="buychart__axis" textAnchor="end">
          ${max.toFixed(0)}
        </text>
        <text x={PAD.l - 8} y={PAD.t + innerH} className="buychart__axis" textAnchor="end">
          ${min.toFixed(0)}
        </text>
        {/* x축(처음/끝 날짜) */}
        <text x={PAD.l} y={H - 8} className="buychart__axis" textAnchor="start">
          {dates[0].slice(5)}
        </text>
        {dates.length > 1 && (
          <text x={W - PAD.r} y={H - 8} className="buychart__axis" textAnchor="end">
            {dates[dates.length - 1].slice(5)}
          </text>
        )}
        {/* 종목별 폴리라인 + 점(g 의 color → currentColor 상속) */}
        {series.map((s) => (
          <g key={s.ticker} style={{ color: TICKER_COLORS[s.ticker] ?? "var(--text)" }}>
            {s.points.length > 1 && (
              <polyline
                className="buychart__line"
                points={s.points
                  .map((b) => `${x(b.date)},${y(b.price as number)}`)
                  .join(" ")}
              />
            )}
            {s.points.map((b) => (
              <circle
                key={b.date}
                cx={x(b.date)}
                cy={y(b.price as number)}
                r={3}
                className="buychart__dot"
              />
            ))}
          </g>
        ))}
      </svg>
      <div className="buychart__legend">
        {series.map((s) => (
          <span key={s.ticker} className="buychart__leg">
            <span
              className="buychart__swatch"
              style={{ background: TICKER_COLORS[s.ticker] }}
            />
            {s.ticker}
          </span>
        ))}
      </div>
    </div>
  );
}
