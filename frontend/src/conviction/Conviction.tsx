// 반등 포착 - 기술반등 + 뉴스반등을 종목별로 합쳐 A/B/C 확신도로 등급화하고
// 판단 근거(촉매·기술·시장 신호등·무효화 레벨)를 한 화면에 모아 go/no-go 를 돕는다.
import type { Scan, NewsScan, Digest } from "../api/client";
import { buildConviction, gradeCounts } from "../shared/conviction";
import { explainReason } from "../shared/scanReasons";
import { tickerLabel } from "../shared/tickers";
import { lightMeta } from "../shared/signal";
import { fmtPrice, fmtPct } from "../shared/format";
import { ICONS } from "../shared/icons";
import styles from "./conviction.module.css";

interface Props {
  scans: Scan[];
  news: NewsScan[];
  digest: Digest | null;
}

const CONF_LABEL: Record<string, string> = { high: "확신 높음", medium: "중간", low: "낮음" };

export default function Conviction({ scans, news, digest }: Props) {
  const items = buildConviction(scans, news);
  const counts = gradeCounts(items);
  const light = lightMeta(digest?.signal_light ?? null);

  return (
    <section className="card">
      <div className="card__head">
        <h2><span className="sec-icon">{ICONS.conviction}</span>반등 포착</h2>
        <span className="muted">{items.length}건</span>
      </div>

      {/* 등급 요약 + 시장 레짐 */}
      <div className={styles.conv__summary}>
        <span className={styles.conv__legend}>
          <span className={styles.conv__leg} style={{ color: "var(--ok)" }}>
            <b>A</b> 동반 {counts.A}
          </span>
          <span className={styles.conv__leg} style={{ color: "var(--caution)" }}>
            <b>B</b> 기술 {counts.B}
          </span>
          <span className={styles.conv__leg} style={{ color: "var(--muted)" }}>
            <b>C</b> 촉매 {counts.C}
          </span>
        </span>
        <span className={styles.conv__market} style={{ color: light.cssVar }}>
          시장 {light.emoji} {light.label}
        </span>
      </div>
      {digest?.signal_light === "red" && (
        <p className={styles.conv__warn}>⚠ 시장 신호등 🔴 — 추세 역행 반등은 승률이 낮습니다. 비중을 보수적으로.</p>
      )}

      {items.length === 0 ? (
        <p className="muted">이 날짜의 반등 후보가 없습니다.</p>
      ) : (
        <ul className={styles.conv}>
          {items.map((it) => (
            <li key={it.ticker} className={styles.conv__item} style={{ borderColor: it.meta.cssVar }}>
              <div className={styles.conv__top}>
                <span className={styles.conv__grade} style={{ background: it.meta.cssVar }}>
                  {it.meta.grade}
                </span>
                <span className={styles.conv__ticker}>{it.ticker}</span>
                {tickerLabel(it.ticker) && (
                  <span className={styles.conv__name}>{tickerLabel(it.ticker)}</span>
                )}
                <span className={styles.conv__headline} style={{ color: it.meta.cssVar }}>
                  {it.meta.headline}
                </span>
              </div>
              <p className={styles.conv__rationale}>{it.meta.rationale}</p>

              {/* 촉매(왜) */}
              {it.news && (
                <div className={styles.conv__block}>
                  <span className={styles["conv__block-label"]}>촉매</span>
                  <p className={styles.conv__catalyst}>{it.news.catalyst}</p>
                  {it.news.view && <p className={`${styles.conv__view} muted`}>→ {it.news.view}</p>}
                  <div className={styles.conv__meta}>
                    <span>전일 {fmtPct(it.news.change_pct)}</span>
                    <span>확신 {CONF_LABEL[it.news.confidence] ?? it.news.confidence}</span>
                    {it.news.sources.length > 0 && (
                      <a href={it.news.sources[0]} target="_blank" rel="noreferrer">출처</a>
                    )}
                  </div>
                </div>
              )}

              {/* 기술 */}
              {it.tech && (
                <div className={styles.conv__block}>
                  <span className={styles["conv__block-label"]}>기술</span>
                  <div className={styles.conv__metarow}>
                    <span className={styles.conv__price}>{fmtPrice(it.tech.price)}</span>
                    <span
                      className={styles.conv__chg}
                      style={{ color: it.tech.change_pct >= 0 ? "var(--ok)" : "var(--alert)" }}
                    >
                      {fmtPct(it.tech.change_pct)}
                    </span>
                  </div>
                  <ul className={styles.conv__reasons}>
                    {it.tech.reasons.map((r, i) => (
                      <li key={i}>
                        <b className={styles["conv__reason-name"]}>{r}</b>
                        <span className={styles["conv__reason-desc"]}>{explainReason(r)}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* 무효화(손절) */}
              <p className={styles.conv__inval}>무효화 · {it.invalidation}</p>
            </li>
          ))}
        </ul>
      )}

      <p className="muted disclaimer">
        ※ A=촉매+기술 동반 · B=기술만(데드캣 주의) · C=촉매만(칼날 주의). 참고용 정리이며 매수 권유가 아닙니다. 직접 확인 필요.
      </p>
    </section>
  );
}
