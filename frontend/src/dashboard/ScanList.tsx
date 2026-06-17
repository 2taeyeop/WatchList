// 반등 스캔 후보 — watchlist 밖 종목의 기술적 반등 신호 + 왜 반등 신호인지 설명.
import type { Scan } from "../api/client";
import { fmtPrice, fmtPct } from "../shared/format";
import { explainReason } from "../shared/scanReasons";

interface Props {
  scans: Scan[];
}

export default function ScanList({ scans }: Props) {
  return (
    <section className="card">
      <div className="card__head">
        <h2>📈 반등 스캔 후보</h2>
        <span className="muted">{scans.length}건</span>
      </div>

      {scans.length === 0 ? (
        <p className="muted">이 날짜의 반등 후보가 없습니다.</p>
      ) : (
        <ul className="scans">
          {scans.map((s) => (
            <li key={s.ticker} className="scans__item">
              <div className="scans__top">
                <span className="scans__ticker">{s.ticker}</span>
                <span className="scans__price">{fmtPrice(s.price)}</span>
                <span
                  className="scans__chg"
                  style={{ color: s.change_pct >= 0 ? "var(--ok)" : "var(--alert)" }}
                >
                  {fmtPct(s.change_pct)}
                </span>
              </div>
              <div className="scans__reasons">
                {s.reasons.map((r, i) => (
                  <span key={i} className="tag" title={explainReason(r)}>{r}</span>
                ))}
              </div>
              <details className="scans__why">
                <summary>왜 반등 신호인가?</summary>
                <ul className="scans__whylist">
                  {s.reasons.map((r, i) => (
                    <li key={i}>
                      <b>{r}</b> — {explainReason(r)}
                    </li>
                  ))}
                </ul>
              </details>
            </li>
          ))}
        </ul>
      )}
      <p className="muted disclaimer">※ 매수 권유가 아니라 ‘관찰 후보’입니다. 직접 확인 필요.</p>
    </section>
  );
}
