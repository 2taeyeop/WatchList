// 좌측 날짜 목록 — 월/주차로 묶고, 각 날짜에 신호등 점 + 스캔 후보 수.
import type { DateEntry } from "../api/client";
import { lightMeta } from "../shared/signal";
import { fmtDate } from "../shared/format";
import { groupByWeek } from "../shared/dateGroup";

interface Props {
  dates: DateEntry[];
  selected: string | null;
  onSelect: (date: string) => void;
}

export default function DateList({ dates, selected, onSelect }: Props) {
  if (dates.length === 0) return <p className="datelist__empty">기록 없음</p>;

  const groups = groupByWeek(dates);

  return (
    <div className="datelist">
      {groups.map((g) => (
        <div className="datelist__group" key={g.key}>
          <div className="datelist__week">{g.label}</div>
          <ul className="datelist__items">
            {g.dates.map((d) => {
              const meta = lightMeta(d.signal_light);
              return (
                <li key={d.date}>
                  <button
                    className={`datelist__item${d.date === selected ? " is-active" : ""}`}
                    onClick={() => onSelect(d.date)}
                  >
                    <span className="datelist__dot" style={{ background: meta.cssVar }} />
                    <span className="datelist__date">{fmtDate(d.date)}</span>
                    {d.scan_count > 0 && (
                      <span className="datelist__count">📈 {d.scan_count}</span>
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </div>
  );
}
