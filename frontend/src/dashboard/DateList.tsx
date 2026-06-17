// 좌측 날짜 목록 — 신호등 점 + 스캔 후보 수.
import type { DateEntry } from "../api/client";
import { lightMeta } from "../shared/signal";
import { fmtDate } from "../shared/format";

interface Props {
  dates: DateEntry[];
  selected: string | null;
  onSelect: (date: string) => void;
}

export default function DateList({ dates, selected, onSelect }: Props) {
  if (dates.length === 0) return <p className="datelist__empty">기록 없음</p>;

  return (
    <ul className="datelist">
      {dates.map((d) => {
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
  );
}
