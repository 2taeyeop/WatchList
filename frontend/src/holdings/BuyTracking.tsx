// 분할매수 추적 - 헤더 없이 바로 캘린더(날짜별 구입여부·종목별 매수단가).
// 색: 셀 = 그날 신호등(우호/중립/주의), 칩 = 그날 각 종목 영향(analyzeHoldings).
// 우상단 전환 버튼으로 그래프. 전환 시 높이 고정으로 스크롤이 안 튄다.
import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { Buy, SignalLight } from "../api/client";
import {
  HOLDING_TICKERS,
  DAILY_BASE,
  analyzeHoldings,
  buyGuide,
} from "../shared/holdings";
import { buildConviction } from "../shared/conviction";
import { lightMeta } from "../shared/signal";
import BuyChart, { TICKER_COLORS } from "./BuyChart";
import "./buys.css";

const SPLIT = DAILY_BASE / HOLDING_TICKERS.length; // 종목별 1일 분할액(기준액)
const WD = ["일", "월", "화", "수", "목", "금", "토"];
const pad = (n: number) => String(n).padStart(2, "0");

const CHART_ICON = (
  <svg
    viewBox="0 0 24 24"
    width="16"
    height="16"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <polyline points="3 17 9 11 13 15 21 7" />
  </svg>
);
const CAL_ICON = (
  <svg
    viewBox="0 0 24 24"
    width="16"
    height="16"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <rect x="3" y="4" width="18" height="17" rx="2" />
    <line x1="3" y1="9" x2="21" y2="9" />
    <line x1="8" y1="2" x2="8" y2="5" />
    <line x1="16" y1="2" x2="16" y2="5" />
  </svg>
);

const STEP = 10; // 금액 스테퍼 증감 단위($)
const STEP_UP = (
  <svg
    viewBox="0 0 24 24"
    width="16"
    height="16"
    fill="none"
    stroke="currentColor"
    strokeWidth="3"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <polyline points="6 15 12 9 18 15" />
  </svg>
);
const STEP_DOWN = (
  <svg
    viewBox="0 0 24 24"
    width="16"
    height="16"
    fill="none"
    stroke="currentColor"
    strokeWidth="3"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <polyline points="6 9 12 15 18 9" />
  </svg>
);

interface Draft {
  amount: string;
}

interface Props {
  // 위 분할매수 가이드의 종목별 추천 금액·영향색.
  guideAmounts?: Record<string, number>;
  guideColors?: Record<string, string>;
  activeDate?: string; // stepper 에서 선택한 날짜 - 첫 렌더 시 editor 자동 오픈
}

export default function BuyTracking({
  guideAmounts,
  guideColors,
  activeDate,
}: Props) {
  const [buys, setBuys] = useState<Buy[]>([]);
  const [sigs, setSigs] = useState<Map<string, SignalLight | null>>(new Map());
  const [impacts, setImpacts] = useState<Map<string, Record<string, string>>>(
    new Map(),
  );
  const [view, setView] = useState<"cal" | "chart">("cal");
  const now = new Date();
  const todayIso = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
  const [ym, setYm] = useState(() => {
    if (activeDate) {
      const [yy, mm] = activeDate.split("-").map(Number);
      return { y: yy, m: mm };
    }
    return { y: now.getFullYear(), m: now.getMonth() + 1 };
  });
  const [selected, setSelected] = useState<string | null>(null);
  const [draft, setDraft] = useState<Record<string, Draft>>({});
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const swapRef = useRef<HTMLDivElement>(null);
  const [minH, setMinH] = useState<number | undefined>(undefined);
  const [recAmounts, setRecAmounts] = useState<Record<string, number>>({});
  const [loadedOnce, setLoadedOnce] = useState(false);
  const autoOpened = useRef(false);

  const load = () => {
    api
      .buys()
      .then((b) => {
        setBuys(b);
        setLoadedOnce(true);
      })
      .catch(() => setLoadedOnce(true));
  };
  useEffect(() => {
    load();
    // 셀 색 = 그날 신호등.
    api
      .dates()
      .then((ds) => setSigs(new Map(ds.map((d) => [d.date, d.signal_light]))))
      .catch(() => {});
  }, []);

  // 칩 색 = 그날 각 종목 영향(우호/중립/주의) - 매수일 다이제스트에서 계산.
  useEffect(() => {
    const dates = [...new Set(buys.filter((b) => b.bought).map((b) => b.date))];
    if (!dates.length) return;
    Promise.all(
      dates.map((d) =>
        api
          .digest(d)
          .then((dg) => [d, dg] as const)
          .catch(() => [d, null] as const),
      ),
    ).then((pairs) => {
      const m = new Map<string, Record<string, string>>();
      for (const [d, dg] of pairs) {
        const imp: Record<string, string> = {};
        if (dg)
          for (const h of analyzeHoldings(dg)) imp[h.ticker] = h.meta.cssVar;
        m.set(d, imp);
      }
      setImpacts(m);
    });
  }, [buys]);

  // 선택 날짜의 추천 금액 = 그 날짜 디지스트 기준 buyGuide(없으면 기준액).
  useEffect(() => {
    if (!selected) {
      setRecAmounts({});
      return;
    }
    let alive = true;
    Promise.all([
      api.digest(selected).catch(() => null),
      api.scans(selected).catch(() => []),
      api.newsScans(selected).catch(() => []),
      api.holdingsNews(selected).catch(() => []),
    ]).then(([dg, sc, ns, hn]) => {
      if (!alive) return;
      if (!dg) {
        setRecAmounts({});
        return;
      }
      const guide = buyGuide(
        analyzeHoldings(dg),
        dg.signal_light,
        buildConviction(sc, ns),
        hn,
      );
      setRecAmounts(
        Object.fromEntries(guide.rows.map((r) => [r.ticker, r.amount])),
      );
    });
    return () => {
      alive = false;
    };
  }, [selected]);

  const toggleView = () => {
    setMinH(swapRef.current?.offsetHeight);
    setView((v) => (v === "cal" ? "chart" : "cal"));
  };

  // 날짜 → 종목 → Buy.
  const byDate = new Map<string, Map<string, Buy>>();
  for (const b of buys) {
    if (!byDate.has(b.date)) byDate.set(b.date, new Map());
    byDate.get(b.date)!.set(b.ticker, b);
  }

  const openDay = (date: string) => {
    setSelected(date);
    setMsg(null);
    const dayMap = byDate.get(date);
    const d: Record<string, Draft> = {};
    for (const t of HOLDING_TICKERS) {
      const b = dayMap?.get(t);
      // 구입기록 있으면 그 금액, 미구입이면 빈칸, 기록 없으면 자동입력(오늘=추천액·그 외=기준액).
      const amount = b
        ? b.bought
          ? String(Math.round(b.amount))
          : ""
        : String(
            Math.round(
              date === todayIso ? (guideAmounts?.[t] ?? SPLIT) : SPLIT,
            ),
          );
      d[t] = { amount };
    }
    setDraft(d);
  };

  const save = async () => {
    if (!selected) return;
    setSaving(true);
    setMsg(null);
    try {
      for (const t of HOLDING_TICKERS) {
        const a = Number(draft[t].amount);
        // 금액 입력 = 구입, 빈칸/0 = 미구입(토글 없이 금액으로 판정).
        const bought =
          draft[t].amount.trim() !== "" && !Number.isNaN(a) && a > 0;
        // price 미전달 → 기존 단가 유지(COALESCE), buy_fill 잡이 종가로 채움.
        await api.recordBuy({
          ticker: t,
          amount: bought ? a : 0,
          bought,
          date: selected,
        });
      }
      load();
      setMsg({ ok: true, text: "저장됨" });
    } catch (e) {
      setMsg({ ok: false, text: `저장 실패: ${String(e)}` });
    } finally {
      setSaving(false);
    }
  };

  // 금액 스테퍼(±STEP, 0 미만 방지).
  const bump = (t: string, delta: number) => {
    const cur = Number(draft[t]?.amount) || 0;
    setDraft({ ...draft, [t]: { amount: String(Math.max(0, cur + delta)) } });
  };

  // 첫 렌더: stepper 날짜(activeDate)로 editor 자동 오픈(buys 로드 후 1회 - 기존 기록 반영).
  useEffect(() => {
    if (autoOpened.current || !activeDate || !loadedOnce) return;
    autoOpened.current = true;
    openDay(activeDate);
  }, [activeDate, loadedOnce]);

  const cumulative = buys
    .filter((b) => b.bought)
    .reduce((a, b) => a + b.amount, 0);

  const { y, m } = ym;
  const firstWeekday = new Date(y, m - 1, 1).getDay();
  const daysInMonth = new Date(y, m, 0).getDate();
  const cells: (number | null)[] = [
    ...Array(firstWeekday).fill(null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ];
  const iso = (d: number) => `${y}-${pad(m)}-${pad(d)}`;
  const prev = m === 1 ? { y: y - 1, m: 12 } : { y, m: m - 1 };
  const next = m === 12 ? { y: y + 1, m: 1 } : { y, m: m + 1 };

  return (
    <div className="buys">
      <div className="buys__bar">
        <div className="buys__nav">
          <button
            type="button"
            onClick={() => setYm(prev)}
            aria-label="이전 달"
          >
            ‹
          </button>
          <span className="buys__title">
            {y}년 {m}월
          </span>
          <button
            type="button"
            onClick={() => setYm(next)}
            aria-label="다음 달"
          >
            ›
          </button>
        </div>
        <button className="buys__toggle" type="button" onClick={toggleView}>
          {view === "cal" ? CHART_ICON : CAL_ICON}
          {view === "cal" ? "그래프 보기" : "캘린더 보기"}
        </button>
      </div>

      <div
        className="buys__swap"
        ref={swapRef}
        style={minH ? { minHeight: minH } : undefined}
      >
        {view === "chart" ? (
          <BuyChart buys={buys} />
        ) : (
          <>
            <div className="buys__grid buys__weekdays">
              {WD.map((w) => (
                <span key={w} className="buys__wd">
                  {w}
                </span>
              ))}
            </div>
            <div className="buys__grid">
              {cells.map((d, i) => {
                if (d === null)
                  return <span key={i} className="buys__cell is-empty" />;
                const date = iso(d);
                const dayMap = byDate.get(date);
                const bought = HOLDING_TICKERS.filter(
                  (t) => dayMap?.get(t)?.bought,
                );
                // 셀 색 = 신호등(매수일만).
                const sigColor = bought.length
                  ? lightMeta(sigs.get(date) ?? null).cssVar
                  : undefined;
                return (
                  <button
                    type="button"
                    key={i}
                    className={`buys__cell${date === selected ? " is-active" : ""}${
                      bought.length ? " has-buy" : ""
                    }`}
                    style={
                      sigColor
                        ? { color: sigColor, borderColor: sigColor }
                        : undefined
                    }
                    onClick={() => openDay(date)}
                  >
                    <span className="buys__day">{d}</span>
                    {bought.length > 0 && (
                      <span className="buys__chips">
                        {bought.map((t) => {
                          const amt = dayMap!.get(t)!.amount;
                          // 칩 색 = 그날 그 종목 영향(없으면 중립).
                          const impColor =
                            impacts.get(date)?.[t] ?? "var(--muted)";
                          return (
                            <span
                              key={t}
                              className="buys__chip"
                              style={{ color: impColor }}
                            >
                              <span className="buys__chip-tkr">{t}</span>
                              <span className="buys__chip-px">
                                ${Math.round(amt)}
                              </span>
                            </span>
                          );
                        })}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>

            {/* 선택 날짜 매수 입력 - 저장 버튼은 머리말 우측 */}
            {selected && (
              <div className="buys__editor">
                <div className="buys__editor-head">
                  <span>
                    {selected} 매수 기록
                    {selected === todayIso && (
                      <span className="muted"> · 오늘 추천 금액</span>
                    )}
                    {msg && (
                      <span
                        className={`buys__msg buys__msg--${msg.ok ? "ok" : "err"}`}
                      >
                        {" · "}
                        {msg.text}
                      </span>
                    )}
                  </span>
                  <button
                    type="button"
                    className="buys__save"
                    onClick={save}
                    disabled={saving}
                  >
                    {saving ? "저장 중…" : "저장"}
                  </button>
                </div>
                <div className="buys__cards">
                  {HOLDING_TICKERS.map((t) => (
                    <div key={t} className="buys__card">
                      <div
                        className="buys__card-tkr"
                        style={{ color: guideColors?.[t] ?? TICKER_COLORS[t] }}
                      >
                        {t}
                      </div>
                      <div className="buys__field">
                        <span className="buys__num-dollar">$</span>
                        <div className="buys__num">
                          <input
                            className="buys__num-input"
                            type="text"
                            inputMode="numeric"
                            size={(draft[t]?.amount ?? "").length || 1}
                            value={draft[t]?.amount ?? ""}
                            onChange={(e) =>
                              setDraft({
                                ...draft,
                                [t]: {
                                  amount: e.target.value.replace(/[^0-9]/g, ""),
                                },
                              })
                            }
                          />
                          <div className="buys__num-steps">
                            <button
                              type="button"
                              className="buys__num-step"
                              onClick={() => bump(t, STEP)}
                              aria-label="금액 증가"
                            >
                              {STEP_UP}
                            </button>
                            <button
                              type="button"
                              className="buys__num-step"
                              onClick={() => bump(t, -STEP)}
                              aria-label="금액 감소"
                            >
                              {STEP_DOWN}
                            </button>
                          </div>
                        </div>
                      </div>
                      <div className="buys__card-rec">
                        추천 ${Math.round(recAmounts[t] ?? SPLIT)}
                      </div>
                    </div>
                  ))}
                </div>
                <div className="buys__base muted">
                  기준액 ${Math.round(SPLIT)} · 종목별 1일 분할
                </div>
              </div>
            )}

            <div className="buys__summary muted">
              누적 매수 금액{" "}
              <b>${Math.round(cumulative).toLocaleString("en-US")}</b>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
