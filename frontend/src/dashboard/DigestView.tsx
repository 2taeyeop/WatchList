// 다이제스트 상세 — 신호등 + 지표 표 + 한 줄 결론 + 본문.
import type { Digest } from "../api/client";
import { lightMeta, INDICATOR_STATUS } from "../shared/signal";
import { fmtDate } from "../shared/format";

interface Props {
  date: string;
  digest: Digest | null;
}

export default function DigestView({ date, digest }: Props) {
  if (!digest) {
    return (
      <section className="card">
        <div className="card__head">
          <h2>{fmtDate(date)} 다이제스트</h2>
        </div>
        <p className="muted">이 날짜의 다이제스트가 없습니다(스캔 결과만 있을 수 있음).</p>
      </section>
    );
  }

  const light = lightMeta(digest.signal_light);

  return (
    <section className="card">
      <div className="card__head">
        <h2>{fmtDate(digest.date)} 다이제스트</h2>
        <span className="light" style={{ borderColor: light.cssVar, color: light.cssVar }}>
          {light.emoji} 디리스킹 {light.label}
        </span>
      </div>

      {digest.conclusion && <p className="conclusion">“{digest.conclusion}”</p>}

      {digest.indicators.length > 0 && (
        <table className="indic">
          <thead>
            <tr>
              <th>지표</th>
              <th>상태</th>
              <th>수치</th>
              <th>변화</th>
              <th>코멘트</th>
            </tr>
          </thead>
          <tbody>
            {digest.indicators.map((ind, i) => {
              const m = INDICATOR_STATUS[ind.status] ?? INDICATOR_STATUS.na;
              return (
                <tr key={i}>
                  <td>{ind.name}</td>
                  <td style={{ color: m.cssVar }}>{m.emoji} {m.label}</td>
                  <td>{ind.value || "—"}</td>
                  <td>{ind.change || "—"}</td>
                  <td className="muted">{ind.comment || "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}

      <details className="prose">
        <summary>전체 다이제스트 본문 보기</summary>
        <pre>{digest.prose}</pre>
      </details>
    </section>
  );
}
