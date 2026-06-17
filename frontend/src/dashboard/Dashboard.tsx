// 대시보드 메인 - 좌측 날짜 사이드바(모바일=드로어) + 상단 날짜 ‹›스테퍼 +
// 가로 탭(보유종목/다이제스트/기술반등/뉴스반등) → 아래 영역 내용을 전환.
import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { DateEntry, Digest, Scan, NewsScan } from "../api/client";
import DateList from "../sidebar/DateList";
import HoldingsImpact from "../holdings/HoldingsImpact";
import DigestView from "../digest/DigestView";
import ScanList from "../scan/ScanList";
import NewsRebound from "../news/NewsRebound";
import { analyzeHoldings, buyGuide } from "../shared/holdings";
import { fmtDate } from "../shared/format";
import { lightMeta } from "../shared/signal";
import { ICONS } from "../shared/icons";
import "./Dashboard.css";

type Tab = "holdings" | "digest" | "scan" | "news";

const TABS: { tab: Tab; title: string }[] = [
  { tab: "holdings", title: "보유종목" },
  { tab: "digest", title: "다이제스트" },
  { tab: "scan", title: "기술반등" },
  { tab: "news", title: "뉴스반등" },
];

// 뉴스반등 탭 테두리 = 후보 중 최고 확신도 색(NewsRebound 의 conf 색과 동일).
function newsConfColor(items: NewsScan[]): string {
  if (items.some((n) => n.confidence === "high")) return "var(--ok)";
  if (items.some((n) => n.confidence === "medium")) return "var(--caution)";
  return "var(--muted)";
}

export default function Dashboard() {
  const [dates, setDates] = useState<DateEntry[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [digest, setDigest] = useState<Digest | null>(null);
  const [scans, setScans] = useState<Scan[]>([]);
  const [newsScans, setNewsScans] = useState<NewsScan[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("holdings");
  const [drawer, setDrawer] = useState(false);

  // 최초: 날짜 목록 → 최신 자동 선택.
  useEffect(() => {
    api
      .dates()
      .then((d) => {
        setDates(d);
        if (d.length > 0) setSelected(d[0].date);
      })
      .catch((e) => setError(String(e)));
  }, []);

  // 선택 날짜 변경 시: 다이제스트 + 스캔 + 뉴스 로드.
  useEffect(() => {
    if (!selected) return;
    setLoading(true);
    setError(null);
    Promise.all([
      api.digest(selected).catch(() => null),
      api.scans(selected),
      api.newsScans(selected),
    ])
      .then(([dg, sc, ns]) => {
        setDigest(dg);
        setScans(sc);
        setNewsScans(ns);
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [selected]);

  // dates[]는 최신순(DESC). ‹ = 과거(idx+1), › = 미래(idx-1).
  const idx = selected ? dates.findIndex((d) => d.date === selected) : -1;
  const goOlder = () => idx >= 0 && idx < dates.length - 1 && setSelected(dates[idx + 1].date);
  const goNewer = () => idx > 0 && setSelected(dates[idx - 1].date);
  const pickDate = (date: string) => {
    setSelected(date);
    setDrawer(false);
  };

  // 탭별 테두리 색(내용 반영).
  const guide = digest ? buyGuide(analyzeHoldings(digest), digest.signal_light) : null;
  const paceColor = !guide
    ? "var(--muted)"
    : guide.pace >= 1
    ? "var(--ok)"
    : guide.pace > 0
    ? "var(--caution)"
    : "var(--alert)";
  const tabColor: Record<Tab, string> = {
    holdings: paceColor, // 투입 강도
    digest: lightMeta(digest?.signal_light ?? null).cssVar, // 다이제스트 신호등
    scan: scans.length ? "var(--ok)" : "var(--muted)", // 후보 있으면 초록
    news: newsConfColor(newsScans), // 뉴스 확신도
  };
  const tabLabel = (t: Tab, title: string) => {
    if (t === "scan") return `${title}(${scans.length}개)`;
    if (t === "news") return `${title}(${newsScans.length}개)`;
    return title;
  };

  return (
    <div className="dash">
      {drawer && <div className="dash__overlay" onClick={() => setDrawer(false)} />}
      <aside className={`dash__side${drawer ? " is-open" : ""}`}>
        <h1 className="dash__brand">📊 WatchList</h1>
        <DateList dates={dates} selected={selected} onSelect={pickDate} />
      </aside>

      <main className="dash__main">
        {/* 상단 바: ☰(모바일) · 날짜 ‹›스테퍼 */}
        <div className="topbar">
          <button className="topbar__menu" onClick={() => setDrawer(true)} aria-label="날짜 목록">
            ☰
          </button>
          {selected && (
            <div className="stepper">
              <button onClick={goOlder} disabled={idx < 0 || idx >= dates.length - 1} aria-label="이전 날짜">
                ‹
              </button>
              <span className="stepper__date">
                {lightMeta(digest?.signal_light ?? null).emoji} {fmtDate(selected)}
              </span>
              <button onClick={goNewer} disabled={idx <= 0} aria-label="다음 날짜">
                ›
              </button>
            </div>
          )}
        </div>

        {/* 가로 탭 - 클릭하면 아래 영역 내용 전환 */}
        {selected && (
          <nav className="homenav">
            {TABS.map((t) => (
              <button
                key={t.tab}
                className={`homenav__item${tab === t.tab ? " is-active" : ""}`}
                onClick={() => setTab(t.tab)}
              >
                <span
                  className="homenav__inner"
                  style={{
                    borderBottomColor:
                      tab === t.tab
                        ? tabColor[t.tab]
                        : `color-mix(in srgb, ${tabColor[t.tab]} 35%, transparent)`,
                  }}
                >
                  <span className="homenav__icon">{ICONS[t.tab]}</span>
                  <span className="homenav__label">{tabLabel(t.tab, t.title)}</span>
                </span>
              </button>
            ))}
          </nav>
        )}

        {error && <div className="dash__error">⚠️ {error}</div>}
        {!selected && !error && (
          <div className="dash__empty">
            아직 저장된 데이터가 없습니다. 파이프라인(<code>backend.jobs.*</code>)을 실행하면 표시됩니다.
          </div>
        )}
        {loading && <div className="dash__empty">불러오는 중…</div>}

        {/* 탭 내용(영역) */}
        {selected && !loading && (
          <>
            {tab === "holdings" && <HoldingsImpact digest={digest} />}
            {tab === "digest" && <DigestView date={selected} digest={digest} />}
            {tab === "scan" && <ScanList scans={scans} />}
            {tab === "news" && <NewsRebound items={newsScans} />}
          </>
        )}
      </main>
    </div>
  );
}
