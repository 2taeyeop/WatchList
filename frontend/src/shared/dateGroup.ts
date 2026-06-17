// 사이드바 날짜를 '월/주차'로 묶는다 (예: "6월 3주차"). 월요일 시작 주 기준.
import type { DateEntry } from "../api/client";

export interface DateGroup {
  key: string;
  label: string; // "6월 3주차"
  dates: DateEntry[];
}

// 그 달에서 d일이 몇 번째 주(월요일 시작)에 속하는지.
function weekOfMonth(y: number, m: number, d: number): number {
  const firstWeekday = new Date(y, m - 1, 1).getDay(); // 0=일
  const mondayOffset = (firstWeekday + 6) % 7; // 1일이 월요일 기준 며칠째인지
  return Math.floor((d - 1 + mondayOffset) / 7) + 1;
}

// 입력은 최신순(DESC) 가정 → 그룹·그룹내 날짜 모두 최신순 유지.
export function groupByWeek(dates: DateEntry[]): DateGroup[] {
  const groups: DateGroup[] = [];
  const index = new Map<string, DateGroup>();
  for (const entry of dates) {
    const [y, m, d] = entry.date.split("-").map(Number);
    const w = weekOfMonth(y, m, d);
    const key = `${y}-${m}-${w}`;
    let g = index.get(key);
    if (!g) {
      g = { key, label: `${m}월 ${w}주차`, dates: [] };
      index.set(key, g);
      groups.push(g);
    }
    g.dates.push(entry);
  }
  return groups;
}
