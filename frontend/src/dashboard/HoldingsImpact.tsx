// dash__main 최상단 — 오늘 다이제스트가 내 보유종목(QLD/SSO/SMH)에 주는 영향
// + 그 신호로 계산한 '오늘의 분할매수 가이드'(투입 강도 + 3종 비율/금액).
import type { Digest } from "../api/client";
import { analyzeHoldings, buyGuide, BUDGET_KRW, DCA_DAYS, USDKRW } from "../shared/holdings";
import { INDICATOR_STATUS, lightMeta } from "../shared/signal";
import { fmtUSD } from "../shared/format";

interface Props {
  digest: Digest | null;
}

export default function HoldingsImpact({ digest }: Props) {
  if (!digest) return null;
  const holdings = analyzeHoldings(digest);
  const guide = buyGuide(holdings, digest.signal_light);
  const light = lightMeta(digest.signal_light);
  const deploying = guide.todayTotal > 0;

  return (
    <section className="holdings">
      <div className="holdings__head">
        <h2>내 보유종목 영향 + 오늘 분할매수</h2>
        <span className="muted">{digest.date} 다이제스트 기준</span>
      </div>

      {/* 오늘 투입 강도 */}
      <div className="buyguide__pace">
        <span>오늘 투입 강도:</span>
        <b style={{ color: light.cssVar }}>{light.emoji} {guide.paceLabel}</b>
        {deploying && (
          <span className="buyguide__total">· 합계 {fmtUSD(guide.todayTotal / USDKRW)}</span>
        )}
        <span className="muted buyguide__basis">
          ({(BUDGET_KRW / 10000).toLocaleString("ko-KR")}만원 ÷ {DCA_DAYS}거래일 · $1≈₩
          {USDKRW.toLocaleString("ko-KR")})
        </span>
      </div>

      <div className="holdings__grid">
        {holdings.map((h, i) => {
          const row = guide.rows[i];
          return (
            <div className="holding" key={h.ticker} style={{ borderTopColor: h.meta.cssVar }}>
              <div className="holding__top">
                <span className="holding__ticker">{h.ticker}</span>
                <span className="holding__lev">{h.leverage}</span>
              </div>
              <div className="holding__impact" style={{ color: h.meta.cssVar }}>
                {h.meta.emoji} {h.meta.label}
              </div>
              <p className="holding__interp">{h.interpretation}</p>
              {h.drivers.length > 0 && (
                <div className="holding__drivers">
                  {h.drivers.map((d, j) => {
                    const m = INDICATOR_STATUS[d.status];
                    return (
                      <span key={j} className="holding__driver">
                        <span style={{ color: m.cssVar }}>{m.emoji}</span> {d.label}
                      </span>
                    );
                  })}
                </div>
              )}
              {/* 오늘 매수 */}
              {deploying ? (
                <div className="holding__buy">
                  오늘 매수 <b>{row.pct}%</b> · {fmtUSD(row.amount / USDKRW)}
                </div>
              ) : (
                <div className="holding__buy holding__buy--wait">오늘은 대기</div>
              )}
            </div>
          );
        })}
      </div>

      <p className="muted holdings__note">
        ※ 신호등·지표를 종목 민감도로 환산한 참고용 가이드입니다. 매매 지시가 아니며 최종 판단은 본인이.
      </p>
    </section>
  );
}
