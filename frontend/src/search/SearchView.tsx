// 종목 검색 화면(섹션) — 2단계.
//   ① 검색: yfinance 로 기본정보(티커·현재가·등락률) 즉시 표시(빠름·무료).
//   ② 분석하기: API 가 Claude 웹검색으로 심층 분석 → DB 에 날짜별 누적 저장(느림·구독).
// 한글 종목명은 yfinance 가 못 잡을 수 있어, 그 경우 기본정보 없이 바로 분석하기로 진행.
// '저장된 데이터 보기' = DB 누적 분석을 티커별 테이블(날짜 누적)로 표시.
import { useState } from "react";
import { api } from "../api/client";
import type { Quote, SearchAnalysis } from "../api/client";
import { searchTickers, tickerLabel } from "../shared/tickers";
import { fmtPct } from "../shared/format";
import { ICONS } from "../shared/icons";
import "./search.css";

const SENT_LABEL: Record<string, string> = {
  positive: "호재",
  neutral: "중립",
  negative: "악재",
};
const SENT_COLOR: Record<string, string> = {
  positive: "var(--ok)",
  neutral: "var(--muted)",
  negative: "var(--alert)",
};

function priceLabel(market: string, price: number | null): string {
  if (price == null) return "—";
  return market === "KR"
    ? `₩${price.toLocaleString("ko-KR")}`
    : `$${price.toLocaleString("en-US", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      })}`;
}

// 저장된 분석을 티커별로 묶는다(입력은 이미 ticker·date DESC 순).
function groupByTicker(list: SearchAnalysis[]): SearchAnalysis[][] {
  const map = new Map<string, SearchAnalysis[]>();
  for (const s of list) {
    const arr = map.get(s.ticker) ?? [];
    arr.push(s);
    map.set(s.ticker, arr);
  }
  return [...map.values()];
}

export default function SearchView() {
  const [query, setQuery] = useState("");
  const [term, setTerm] = useState(""); // 마지막으로 검색한 말(분석하기에 사용)
  const [open, setOpen] = useState(false);
  const [searched, setSearched] = useState(false);
  const [quote, setQuote] = useState<Quote | null>(null);
  const [loadingQuote, setLoadingQuote] = useState(false);
  const [result, setResult] = useState<SearchAnalysis | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedMode, setSavedMode] = useState(false);
  const [saved, setSaved] = useState<SearchAnalysis[]>([]);
  const [savedLoading, setSavedLoading] = useState(false);

  const suggestions = searchTickers(query);

  // ① 검색 → yfinance 기본정보.
  const doQuote = async (q: string) => {
    const t = q.trim();
    if (!t) return;
    setTerm(t);
    setQuery(t);
    setOpen(false);
    setSavedMode(false);
    setSearched(true);
    setError(null);
    setQuote(null);
    setResult(null);
    setLoadingQuote(true);
    try {
      setQuote(await api.quote(t));
    } catch {
      // 기본정보 못 찾음(한글명 등) — 하드 에러 대신 '바로 분석하기' 유도.
      setQuote(null);
    } finally {
      setLoadingQuote(false);
    }
  };

  // ② 분석하기 → Claude 웹검색(해석된 티커 우선, 없으면 검색어).
  const doAnalyze = async () => {
    const aq = quote?.ticker || term;
    if (!aq) return;
    setAnalyzing(true);
    setError(null);
    try {
      setResult(await api.search(aq));
    } catch (e) {
      setError(String(e));
    } finally {
      setAnalyzing(false);
    }
  };

  const toggleSaved = async () => {
    if (savedMode) {
      setSavedMode(false);
      return;
    }
    setSavedMode(true);
    setSavedLoading(true);
    setError(null);
    try {
      setSaved(await api.searches());
    } catch (e) {
      setError(String(e));
    } finally {
      setSavedLoading(false);
    }
  };

  const groups = groupByTicker(saved);

  return (
    <div className="search">
      <div className="search__bar">
        <div className="search__box">
          <span className="search__icon">{ICONS.search}</span>
          <input
            className="search__input"
            value={query}
            placeholder="티커·종목명 (예: NVDA, 005930, Samsung)"
            onChange={(e) => {
              setQuery(e.target.value);
              setOpen(true);
            }}
            onFocus={() => setOpen(true)}
            onBlur={() => setOpen(false)}
            onKeyDown={(e) => {
              if (e.key === "Enter") doQuote(query);
            }}
          />
          {open && suggestions.length > 0 && (
            <ul className="search__suggest">
              {suggestions.map((t) => (
                <li key={t}>
                  <button
                    className="search__opt"
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={() => {
                      setQuery(t);
                      doQuote(t);
                    }}
                  >
                    <span className="search__opt-ticker">{t}</span>
                    <span className="search__opt-name">{tickerLabel(t)}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        <button
          className="search__btn"
          onClick={() => doQuote(query)}
          disabled={loadingQuote}
        >
          검색
        </button>
        <button
          className={`search__saved-btn${savedMode ? " is-active" : ""}`}
          onClick={toggleSaved}
        >
          저장된 데이터 보기
        </button>
      </div>

      {error && <div className="dash__error">⚠️ {error}</div>}

      {/* 저장된 데이터 보기: 티커별 테이블(날짜 누적) */}
      {savedMode ? (
        savedLoading ? (
          <div className="dash__empty">불러오는 중…</div>
        ) : groups.length === 0 ? (
          <div className="dash__empty">저장된 분석이 없습니다.</div>
        ) : (
          <div className="search__saved">
            {groups.map((rows) => (
              <div className="card" key={rows[0].ticker}>
                <div className="card__head">
                  <h2>
                    {rows[0].ticker}
                    {rows[0].name && (
                      <span className="search__name"> · {rows[0].name}</span>
                    )}
                  </h2>
                  {rows[0].market && <span className="muted">{rows[0].market}</span>}
                </div>
                <table className="search__table">
                  <thead>
                    <tr>
                      <th>날짜</th>
                      <th>분석</th>
                      <th>감성</th>
                      <th>가격</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((s) => (
                      <tr key={s.date}>
                        <td className="search__td-date">{s.date.slice(5)}</td>
                        <td className="search__td-sum">
                          {s.summary}
                          {s.catalyst && (
                            <div className="muted search__td-cat">촉매: {s.catalyst}</div>
                          )}
                        </td>
                        <td style={{ color: SENT_COLOR[s.sentiment] }}>
                          {SENT_LABEL[s.sentiment] ?? s.sentiment}
                        </td>
                        <td className="search__td-price">
                          {priceLabel(s.market, s.price)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}
          </div>
        )
      ) : (
        <>
          {loadingQuote && <div className="dash__empty">기본정보 불러오는 중…</div>}
          {!searched && !loadingQuote && (
            <div className="dash__empty">
              티커·종목명을 검색하면 기본정보를 불러옵니다. ‘분석하기’를 누르면 Claude가
              웹에서 최신 정보를 분석합니다.
            </div>
          )}

          {/* ① 기본정보(yfinance) + 분석하기 버튼 */}
          {searched && !loadingQuote && (
            <div className="card">
              {quote ? (
                <div className="card__head">
                  <h2>
                    {quote.ticker}
                    {quote.name && <span className="search__name"> · {quote.name}</span>}
                  </h2>
                  <span className="search__quote">
                    <span className="muted">{quote.market} </span>
                    {priceLabel(quote.market, quote.price)}
                    {quote.change_pct != null && (
                      <span
                        style={{
                          color: quote.change_pct >= 0 ? "var(--ok)" : "var(--alert)",
                        }}
                      >
                        {" "}
                        {fmtPct(quote.change_pct)}
                      </span>
                    )}
                  </span>
                </div>
              ) : (
                <p className="muted">
                  기본정보를 찾지 못했어요(한글명은 코드/영문명으로 검색). ‘{term}’ 그대로
                  분석할 수 있습니다.
                </p>
              )}
              <button
                className="search__analyze"
                onClick={doAnalyze}
                disabled={analyzing}
              >
                {analyzing ? "Claude 분석 중… (수십 초)" : "분석하기"}
              </button>
            </div>
          )}

          {/* ② Claude 심층 분석 결과 */}
          {result && !analyzing && (
            <div className="card">
              <div className="card__head">
                <h2>
                  {result.ticker}
                  {result.name && <span className="search__name"> · {result.name}</span>}
                  <span className="muted search__asof"> · 분석 {result.date}</span>
                </h2>
                <span
                  className="search__badge"
                  style={{ color: SENT_COLOR[result.sentiment] }}
                >
                  {SENT_LABEL[result.sentiment] ?? result.sentiment}
                </span>
              </div>
              <div className="search__news">
                {result.summary && <p className="search__headline">{result.summary}</p>}
                {result.catalyst && (
                  <p>
                    <strong>촉매</strong> {result.catalyst}
                  </p>
                )}
                {result.view && (
                  <p>
                    <strong>관점</strong> {result.view}
                  </p>
                )}
                {result.sources.length > 0 && (
                  <ul className="search__sources">
                    {result.sources.map((s) => (
                      <li key={s}>
                        <a href={s} target="_blank" rel="noreferrer">
                          {s}
                        </a>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
