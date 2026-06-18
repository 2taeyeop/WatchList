// dash__main 최상단 - 오늘 다이제스트가 내 보유종목(QLD/SSO/SMH)에 주는 영향
// + 그 신호로 계산한 '오늘의 분할매수 가이드'(투입 강도 + 3종 비율/금액).
import { useEffect, useState } from "react";
import type { Digest, HoldingsNews } from "../api/client";
import type { ConvictionItem } from "../shared/conviction";
import {
  analyzeHoldings,
  buyGuide,
  BUDGET_USD,
  DCA_DAYS,
  SMH_CONSTITUENTS,
} from "../shared/holdings";
import { INDICATOR_STATUS, lightMeta } from "../shared/signal";
import { fmtUSD } from "../shared/format";
import { ICONS } from "../shared/icons";
import BuyTracking from "./BuyTracking";
import "./holdings.css";

interface Props {
  digest: Digest | null;
  candidates?: ConvictionItem[]; // 반등 포착(구성종목 반등을 페이스에 반영)
  holdingsNews?: HoldingsNews[]; // 구성종목 최신 뉴스(양방향 → 페이스)
}

const pct = (x: number) => `${Math.round(x * 100)}%`;
const SENT_COLOR: Record<HoldingsNews["sentiment"], string> = {
  positive: "var(--ok)",
  neutral: "var(--muted)",
  negative: "var(--alert)",
};

// 구성종목 뉴스 목록(인라인 토글 + 카드 클릭 모달에서 재사용).
function newsList(items: HoldingsNews[]) {
  return (
    <ul className="holdings__news-list">
      {items.map((n) => (
        <li key={n.ticker} className="holdings__news-item">
          <span
            className="holdings__news-dot"
            style={{ background: SENT_COLOR[n.sentiment] }}
          />
          <span className="holdings__news-tkr">{n.ticker}</span>
          <span className="holdings__news-head muted">{n.headline}</span>
          {n.source && (
            <a
              className="holdings__news-src"
              href={n.source}
              target="_blank"
              rel="noreferrer"
            >
              출처
            </a>
          )}
        </li>
      ))}
    </ul>
  );
}

export default function HoldingsImpact({
  digest,
  candidates = [],
  holdingsNews = [],
}: Props) {
  // 카드 클릭 → 해당 종목 관련 뉴스 모달(hook 은 early return 앞).
  const [modalTicker, setModalTicker] = useState<string | null>(null);
  useEffect(() => {
    if (!modalTicker) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setModalTicker(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [modalTicker]);

  if (!digest) return null;
  const holdings = analyzeHoldings(digest);
  const guide = buyGuide(
    holdings,
    digest.signal_light,
    candidates,
    holdingsNews,
  );
  const bd = guide.breakdown;
  const light = lightMeta(digest.signal_light);
  const deploying = guide.todayTotal > 0;
  // SMH(반도체 ETF)=반도체 구성종목만, QLD/SSO(광범위 지수)=전체 뉴스.
  const modalNews =
    modalTicker === "SMH"
      ? holdingsNews.filter((n) => SMH_CONSTITUENTS.has(n.ticker))
      : holdingsNews;
  const modalHolding = holdings.find((h) => h.ticker === modalTicker);

  return (
    <section className="holdings">
      <div className="holdings__head">
        <h2>
          <span className="sec-icon">{ICONS.holdings}</span>내 종목 · 분할매수
        </h2>
      </div>

      {/* 오늘 투입 강도 - 헤더 + 요인 + 합계($)를 한 표로 */}
      <div className="buyguide__pace">
        <div className="buyguide__calc">
          <div className="buyguide__row buyguide__row--head">
            <span>투입 강도</span>
            <b style={{ color: light.cssVar }}>
              {light.emoji} {guide.paceLabel} {pct(guide.pace)}
            </b>
          </div>
          <div className="buyguide__row">
            <span className="muted">기본 (신호등)</span>
            <span>{pct(bd.base)}</span>
          </div>
          {bd.adjustments.map((a, i) => (
            <div key={i} className="buyguide__row">
              <span className="muted">{a.label}</span>
              <span
                style={{ color: a.delta >= 0 ? "var(--ok)" : "var(--alert)" }}
              >
                {a.delta >= 0 ? "+" : "-"}
                {pct(Math.abs(a.delta))}
              </span>
            </div>
          ))}
          <div className="buyguide__row buyguide__row--total">
            <span>
              합계
              {bd.capped && <span className="buyguide__cap"> · 🔴 상한</span>}
            </span>
            <b style={{ color: light.cssVar }}>{fmtUSD(guide.todayTotal)}</b>
          </div>
        </div>
        <span className="muted buyguide__basis">
          {fmtUSD(BUDGET_USD)} ÷ {DCA_DAYS}거래일 = {fmtUSD(guide.dailyBase)}/일
        </span>
      </div>

      <div className="holdings__grid">
        {holdings.map((h, i) => {
          const row = guide.rows[i];
          // 해석문을 '소제목 - 내용'으로 분리(없으면 전체가 소제목). 카드 정렬용.
          const [interpHead, ...interpRest] = h.interpretation.split(" - ");
          const interpBody = interpRest.join(" - ");
          return (
            <div
              className="holding"
              key={h.ticker}
              style={{ borderColor: h.meta.cssVar }}
              onClick={() => setModalTicker(h.ticker)}
            >
              <div className="holding__top">
                <span className="holding__ticker">{h.ticker}</span>
                <span className="holding__lev">{h.leverage}</span>
              </div>
              <div className="holding__impact" style={{ color: h.meta.cssVar }}>
                {h.meta.emoji} {h.meta.label}
              </div>
              <div className="holding__interp">
                <span className="holding__interp-head">{interpHead}</span>
                {interpBody && (
                  <span className="holding__interp-body">{interpBody}</span>
                )}
              </div>
              <div className="holding__drivers">
                {h.drivers.map((d, j) => {
                  const m = INDICATOR_STATUS[d.status];
                  return (
                    <span key={j} className="holding__driver">
                      <span style={{ color: m.cssVar }}>{m.emoji}</span>{" "}
                      {d.label}
                    </span>
                  );
                })}
              </div>
              {/* 오늘 매수 */}
              {deploying ? (
                <div className="holding__buy">
                  <span className="holding__buy-label">오늘 매수 </span>
                  <span className="holding__buy-pct">{row.pct}%</span>
                  <span className="holding__buy-sep"> · </span>
                  <b
                    className="holding__buy-usd"
                    style={{ color: h.meta.cssVar }}
                  >
                    {fmtUSD(row.amount)}
                  </b>
                </div>
              ) : (
                <div className="holding__buy holding__buy--wait">
                  오늘은 대기
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* 구성종목 최신 뉴스(페이스 ③ 입력) - 토글 */}
      {holdingsNews.length > 0 && (
        <details className="holdings__news">
          <summary className="holdings__news-label">
            구성종목 최신 뉴스 ({holdingsNews.length})
          </summary>
          {newsList(holdingsNews)}
        </details>
      )}

      <p className="muted holdings__note">
        ※ 신호등·지표를 종목 민감도로 환산한 참고용 가이드입니다. 매매 지시가
        아니며 최종 판단은 본인이.
      </p>

      {/* 분할매수 추적 - 캘린더(구입여부·매수단가) + 전환 그래프.
          오늘 날짜 매수 기록엔 위 가이드의 종목별 추천 금액을 자동입력. */}
      <BuyTracking
        guideAmounts={Object.fromEntries(guide.rows.map((r) => [r.ticker, r.amount]))}
        guideColors={Object.fromEntries(holdings.map((h) => [h.ticker, h.meta.cssVar]))}
        activeDate={digest.date}
      />

      {/* 카드 클릭 → 해당 종목 관련 구성종목 뉴스 모달 */}
      {modalTicker && (
        <div className="hmodal__overlay" onClick={() => setModalTicker(null)}>
          <div
            className="hmodal"
            role="dialog"
            aria-modal="true"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="hmodal__head">
              <h3>
                {modalTicker}
                {modalHolding ? ` · ${modalHolding.name}` : ""} 관련 뉴스
              </h3>
              <button
                className="hmodal__close"
                onClick={() => setModalTicker(null)}
                aria-label="닫기"
              >
                ✕
              </button>
            </div>
            {modalNews.length > 0 ? (
              newsList(modalNews)
            ) : (
              <p className="muted">관련 구성종목 뉴스가 없습니다.</p>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
