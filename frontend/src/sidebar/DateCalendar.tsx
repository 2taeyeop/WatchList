// 날짜 선택 달력 모달 — stepper 의 날짜를 클릭하면 열린다.
// 데이터(다이제스트/스캔) 있는 날짜만 선택 가능(신호등 점 표시), 그 외엔 비활성.
import { useEffect, useState } from "react";
import type { DateEntry } from "../api/client";
import { lightMeta } from "../shared/signal";
import "./sidebar.css";

interface Props {
  dates: DateEntry[];
  selected: string | null;
  onPick: (date: string) => void;
  onClose: () => void;
}

const WD = ["일", "월", "화", "수", "목", "금", "토"];
const pad = (n: number) => String(n).padStart(2, "0");

export default function DateCalendar({ dates, selected, onPick, onClose }: Props) {
  // 표시 월 — 선택 날짜(없으면 최신 데이터) 기준.
  const base = selected ?? dates[0]?.date ?? null;
  const [ym, setYm] = useState(() => {
    if (!base) return { y: 2026, m: 1 };
    const [y, m] = base.split("-").map(Number);
    return { y, m };
  });

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  // 데이터 있는 날짜 → 엔트리(신호등) 매핑.
  const byDate = new Map(dates.map((d) => [d.date, d]));

  const { y, m } = ym;
  const firstWeekday = new Date(y, m - 1, 1).getDay(); // 0=일
  const daysInMonth = new Date(y, m, 0).getDate();
  const cells: (number | null)[] = [
    ...Array(firstWeekday).fill(null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ];
  const iso = (d: number) => `${y}-${pad(m)}-${pad(d)}`;

  const prev = m === 1 ? { y: y - 1, m: 12 } : { y, m: m - 1 };
  const next = m === 12 ? { y: y + 1, m: 1 } : { y, m: m + 1 };

  return (
    <>
      {/* 투명 백드롭 - 바깥 클릭 닫기 */}
      <div className="cal__backdrop" onClick={onClose} />
      <div className="cal" role="dialog" aria-modal="true">
        <div className="cal__head">
          <button
            className="cal__nav"
            onClick={() => setYm(prev)}
            aria-label="이전 달"
          >
            ‹
          </button>
          <span className="cal__title">
            {y}년 {m}월
          </span>
          <button
            className="cal__nav"
            onClick={() => setYm(next)}
            aria-label="다음 달"
          >
            ›
          </button>
        </div>
        <div className="cal__grid cal__weekdays">
          {WD.map((w) => (
            <span key={w} className="cal__wd">
              {w}
            </span>
          ))}
        </div>
        <div className="cal__grid">
          {cells.map((d, i) => {
            if (d === null) return <span key={i} className="cal__cell is-empty" />;
            const date = iso(d);
            const entry = byDate.get(date);
            const meta = lightMeta(entry?.signal_light ?? null);
            return (
              <button
                key={i}
                className={`cal__cell${date === selected ? " is-active" : ""}`}
                disabled={!entry}
                onClick={() => entry && onPick(date)}
              >
                <span
                  className="cal__day"
                  style={entry ? { color: meta.cssVar } : undefined}
                >
                  {d}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </>
  );
}
