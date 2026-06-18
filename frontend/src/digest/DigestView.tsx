// 다이제스트 상세 - 신호등 + 지표 목록(평문) + 한 줄 결론 + 본문.
import type { Digest } from "../api/client";
import { lightMeta, INDICATOR_STATUS } from "../shared/signal";
import { fmtDate } from "../shared/format";
import { ICONS } from "../shared/icons";
import styles from "./digest.module.css";

interface Props {
  date: string;
  digest: Digest | null;
}

export default function DigestView({ date, digest }: Props) {
  if (!digest) {
    return (
      <section className="card">
        <div className="card__head">
          <h2><span className="sec-icon">{ICONS.digest}</span>{fmtDate(date)} 다이제스트</h2>
        </div>
        <p className="muted">이 날짜의 다이제스트가 없습니다(스캔 결과만 있을 수 있음).</p>
      </section>
    );
  }

  const light = lightMeta(digest.signal_light);

  return (
    <section className="card">
      <div className="card__head">
        <h2><span className="sec-icon">{ICONS.digest}</span>{fmtDate(digest.date)} 다이제스트</h2>
        <span className={styles.light} style={{ borderColor: light.cssVar, color: light.cssVar }}>
          {light.emoji} 디리스킹 {light.label}
        </span>
      </div>

      {digest.conclusion && (
        <p className={styles.conclusion} style={{ borderLeftColor: light.cssVar }}>
          {digest.conclusion}
        </p>
      )}

      {digest.indicators.length > 0 && (
        <>
          <h3 className={styles.indic__title}>주요 지표</h3>
          <ul className={styles.indic}>
            {digest.indicators.map((ind, i) => {
              const m = INDICATOR_STATUS[ind.status] ?? INDICATOR_STATUS.na;
              const nums = [ind.value, ind.change].filter(Boolean).join(" · ");
              return (
                <li className={styles.indic__item} key={i}>
                  <div className={styles.indic__head}>
                    <span className={styles.indic__status} style={{ color: m.cssVar }} title={m.label}>
                      {m.emoji}
                    </span>
                    <span className={styles.indic__name}>{ind.name}</span>
                    {nums && <span className={styles.indic__nums}>{nums}</span>}
                  </div>
                  {ind.comment && <p className={styles.indic__comment}>{ind.comment}</p>}
                </li>
              );
            })}
          </ul>
        </>
      )}

      <details className={styles.prose}>
        <summary>전체 다이제스트 본문 보기</summary>
        <pre>{digest.prose}</pre>
      </details>
    </section>
  );
}
