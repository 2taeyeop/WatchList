// 대시보드 메인 — 좌측 날짜 목록 + 우측 상세(다이제스트 신호/지표/본문 + 스캔 후보).
import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { DateEntry, Digest, Scan } from "../api/client";
import DateList from "./DateList";
import DigestView from "./DigestView";
import ScanList from "./ScanList";
import "./Dashboard.css";

export default function Dashboard() {
  const [dates, setDates] = useState<DateEntry[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [digest, setDigest] = useState<Digest | null>(null);
  const [scans, setScans] = useState<Scan[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 최초: 날짜 목록 로드 → 가장 최근 날짜 자동 선택.
  useEffect(() => {
    api
      .dates()
      .then((d) => {
        setDates(d);
        if (d.length > 0) setSelected(d[0].date);
      })
      .catch((e) => setError(String(e)));
  }, []);

  // 선택 날짜 변경 시: 다이제스트 + 스캔 로드.
  useEffect(() => {
    if (!selected) return;
    setLoading(true);
    setError(null);
    Promise.all([
      api.digest(selected).catch(() => null), // 그날 다이제스트가 없을 수도(스캔만)
      api.scans(selected),
    ])
      .then(([dg, sc]) => {
        setDigest(dg);
        setScans(sc);
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [selected]);

  return (
    <div className="dash">
      <aside className="dash__side">
        <h1 className="dash__brand">📊 WatchList</h1>
        <DateList dates={dates} selected={selected} onSelect={setSelected} />
      </aside>

      <main className="dash__main">
        {error && <div className="dash__error">⚠️ {error}</div>}
        {!selected && !error && (
          <div className="dash__empty">
            아직 저장된 데이터가 없습니다. <code>python digest.py</code> /{" "}
            <code>python scanner.py</code> 를 실행하면 여기에 표시됩니다.
          </div>
        )}
        {loading && <div className="dash__empty">불러오는 중…</div>}
        {selected && !loading && (
          <>
            <DigestView date={selected} digest={digest} />
            <ScanList scans={scans} />
          </>
        )}
      </main>
    </div>
  );
}
