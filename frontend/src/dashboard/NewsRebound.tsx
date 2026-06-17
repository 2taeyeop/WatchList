// 📰 뉴스 반등 후보 — 약세+전일 하락 종목 중 호재(촉매)가 확인된 종목.
import type { NewsScan } from "../api/client";
import { fmtPct } from "../shared/format";

const CONF: Record<string, { label: string; cssVar: string }> = {
  high: { label: "확신 높음", cssVar: "var(--ok)" },
  medium: { label: "중간", cssVar: "var(--caution)" },
  low: { label: "낮음", cssVar: "var(--muted)" },
};

interface Props {
  items: NewsScan[];
}

export default function NewsRebound({ items }: Props) {
  return (
    <section className="card">
      <div className="card__head">
        <h2>📰 뉴스 반등 후보</h2>
        <span className="muted">{items.length}개</span>
      </div>

      {items.length === 0 ? (
        <p className="muted">약세+하락 종목 중 호재로 잡힌 후보가 없습니다.</p>
      ) : (
        <ul className="news">
          {items.map((n) => {
            const c = CONF[n.confidence] ?? CONF.low;
            return (
              <li key={n.ticker} className="news__item">
                <div className="news__top">
                  <span className="news__ticker">{n.ticker}</span>
                  <span className="news__chg">{fmtPct(n.change_pct)}</span>
                  <span className="news__conf" style={{ color: c.cssVar, borderColor: c.cssVar }}>
                    {c.label}
                  </span>
                </div>
                <p className="news__catalyst">{n.catalyst}</p>
                {n.view && <p className="news__view muted">→ {n.view}</p>}
              </li>
            );
          })}
        </ul>
      )}
      <p className="muted disclaimer">
        ※ 약세+전일 하락 종목의 호재 뉴스 기반. 매수 권유가 아니라 ‘관찰 후보’ — 직접 확인 필요.
      </p>
    </section>
  );
}
