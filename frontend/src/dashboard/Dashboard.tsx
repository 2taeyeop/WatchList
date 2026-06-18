// 대시보드 셸 - 좌측 섹션 사이드바(모바일=드로어) + 섹션별 화면.
//   daily : 날짜 ‹›스테퍼/달력 + 가로 탭(보유종목/다이제스트/반등포착/기술반등/뉴스반등)
//   search: 종목 검색 분석
//   buys  : 분할매수 추적
import { Fragment, useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type {
  DateEntry,
  Digest,
  Scan,
  NewsScan,
  HoldingsNews,
} from "../api/client";
import NavList from "../sidebar/NavList";
import type { Section } from "../sidebar/NavList";
import DateCalendar from "../sidebar/DateCalendar";
import HoldingsImpact from "../holdings/HoldingsImpact";
import DigestView from "../digest/DigestView";
import Conviction from "../conviction/Conviction";
import ScanList from "../scan/ScanList";
import NewsRebound from "../news/NewsRebound";
import SearchView from "../search/SearchView";
import { analyzeHoldings, buyGuide } from "../shared/holdings";
import { buildConviction, topGradeColor } from "../shared/conviction";
import { fmtDate } from "../shared/format";
import { lightMeta } from "../shared/signal";
import { ICONS } from "../shared/icons";
import "./Dashboard.css";

type Tab = "holdings" | "digest" | "conviction" | "scan" | "news";

const TABS: { tab: Tab; title: string }[] = [
  { tab: "holdings", title: "보유종목" },
  { tab: "digest", title: "다이제스트" },
  { tab: "conviction", title: "반등포착" },
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
  const [holdingsNews, setHoldingsNews] = useState<HoldingsNews[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [section, setSection] = useState<Section>("daily");
  const [tab, setTab] = useState<Tab>("holdings");
  const [drawer, setDrawer] = useState(false);
  const [calOpen, setCalOpen] = useState(false);

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
      api.holdingsNews(selected).catch(() => []),
    ])
      .then(([dg, sc, ns, hn]) => {
        setDigest(dg);
        setScans(sc);
        setNewsScans(ns);
        setHoldingsNews(hn);
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [selected]);

  // dates[]는 최신순(DESC). ‹ = 과거(idx+1), › = 미래(idx-1).
  const idx = selected ? dates.findIndex((d) => d.date === selected) : -1;
  const goOlder = () =>
    idx >= 0 && idx < dates.length - 1 && setSelected(dates[idx + 1].date);
  const goNewer = () => idx > 0 && setSelected(dates[idx - 1].date);
  const pickDate = (date: string) => {
    setSelected(date);
    setDrawer(false);
    setCalOpen(false);
  };
  const pickSection = (s: Section) => {
    setSection(s);
    setDrawer(false);
  };

  // 콘텐츠 가로 스와이프로 탭 이동(daily 전용, 왼쪽=다음·오른쪽=이전).
  const swipeStart = useRef<{ x: number; y: number } | null>(null);
  const applySwipe = (dx: number, dy: number) => {
    if (Math.abs(dx) < 50 || Math.abs(dx) < Math.abs(dy) * 1.5) return; // 수평 스와이프만
    const i = TABS.findIndex((t) => t.tab === tab);
    if (dx < 0 && i < TABS.length - 1) setTab(TABS[i + 1].tab);
    if (dx > 0 && i > 0) setTab(TABS[i - 1].tab);
  };

  // 반등 포착 후보(구성종목 반등을 분할매수 페이스에 반영) + 탭별 테두리 색.
  const convItems = buildConviction(scans, newsScans);
  const guide = digest
    ? buyGuide(
        analyzeHoldings(digest),
        digest.signal_light,
        convItems,
        holdingsNews,
      )
    : null;
  const paceColor = !guide
    ? "var(--muted)"
    : guide.pace >= 0.7
      ? "var(--ok)"
      : guide.pace > 0
        ? "var(--caution)"
        : "var(--alert)";
  const tabColor: Record<Tab, string> = {
    holdings: paceColor, // 투입 강도
    digest: lightMeta(digest?.signal_light ?? null).cssVar, // 다이제스트 신호등
    conviction: convItems.length ? topGradeColor(convItems) : "var(--muted)", // 최고 등급 색
    scan: scans.length ? "var(--ok)" : "var(--muted)", // 후보 있으면 초록
    news: newsConfColor(newsScans), // 뉴스 확신도
  };

  const isDaily = section === "daily";

  return (
    <div className="dash">
      {drawer && (
        <div className="dash__overlay" onClick={() => setDrawer(false)} />
      )}
      <aside className={`dash__side${drawer ? " is-open" : ""}`}>
        <h1 className="dash__brand">
          <span>WatchList</span>
          <button
            className="dash__close"
            onClick={() => setDrawer(false)}
            aria-label="사이드바 닫기"
          >
            ✕
          </button>
        </h1>
        <NavList section={section} onSelect={pickSection} />
      </aside>

      <main
        className="dash__main"
        onTouchStart={(e) => {
          swipeStart.current = { x: e.touches[0].clientX, y: e.touches[0].clientY };
        }}
        onTouchEnd={(e) => {
          const s = swipeStart.current;
          if (!s) return;
          swipeStart.current = null;
          if (isDaily)
            applySwipe(
              e.changedTouches[0].clientX - s.x,
              e.changedTouches[0].clientY - s.y,
            );
        }}
      >
        {/* 상단 바: ☰(모바일) · 날짜 ‹›스테퍼(daily 전용, 날짜 클릭 시 달력) */}
        <div className={`topbar${isDaily ? " has-stepper" : ""}`}>
          <button
            className="topbar__menu"
            onClick={() => setDrawer(true)}
            aria-label="메뉴"
          >
            <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor"
              strokeWidth="2" strokeLinecap="round">
              <line x1="3" y1="6" x2="21" y2="6" />
              <line x1="3" y1="12" x2="21" y2="12" />
              <line x1="3" y1="18" x2="21" y2="18" />
            </svg>
          </button>
          {isDaily && selected && (
            <div className="stepper">
              <button
                onClick={goOlder}
                disabled={idx < 0 || idx >= dates.length - 1}
                aria-label="이전 날짜"
              >
                ‹
              </button>
              <button className="stepper__date" onClick={() => setCalOpen(true)}>
                {lightMeta(digest?.signal_light ?? null).emoji} {fmtDate(selected)}
              </button>
              <button onClick={goNewer} disabled={idx <= 0} aria-label="다음 날짜">
                ›
              </button>
              {/* 날짜 클릭 시 stepper 바로 아래에 달력 팝오버 */}
              {calOpen && (
                <DateCalendar
                  dates={dates}
                  selected={selected}
                  onPick={pickDate}
                  onClose={() => setCalOpen(false)}
                />
              )}
            </div>
          )}
        </div>

        {/* daily: 가로 탭 - 클릭하면 아래 영역 내용 전환 */}
        {isDaily && selected && (
          <nav className="homenav">
            {TABS.map((t) => (
              <Fragment key={t.tab}>
                {/* 1축(보유·다이제스트) / 2축(반등 포착·기술·뉴스) 구분선 */}
                {t.tab === "conviction" && (
                  <span className="homenav__divider" aria-hidden="true" />
                )}
                <button
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
                    <span className="homenav__label">{t.title}</span>
                  </span>
                </button>
              </Fragment>
            ))}
          </nav>
        )}

        {isDaily && error && <div className="dash__error">⚠️ {error}</div>}

        {/* daily 콘텐츠 */}
        {isDaily && !selected && !error && (
          <div className="dash__empty">
            아직 저장된 데이터가 없습니다. 파이프라인(
            <code>backend.jobs.*</code>)을 실행하면 표시됩니다.
          </div>
        )}
        {isDaily && loading && <div className="dash__empty">불러오는 중…</div>}
        {isDaily && selected && !loading && (
          <div className="dash__content">
            {tab === "holdings" && (
              <HoldingsImpact
                digest={digest}
                candidates={convItems}
                holdingsNews={holdingsNews}
              />
            )}
            {tab === "digest" && <DigestView date={selected} digest={digest} />}
            {tab === "conviction" && (
              <Conviction scans={scans} news={newsScans} digest={digest} />
            )}
            {tab === "scan" && <ScanList scans={scans} />}
            {tab === "news" && <NewsRebound items={newsScans} />}
          </div>
        )}

        {/* search 섹션 */}
        {section === "search" && <SearchView />}
      </main>
    </div>
  );
}
