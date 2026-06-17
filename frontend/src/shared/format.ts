// 날짜/숫자 포매터 (재구현 전 여기 먼저 확인).

export function fmtDate(iso: string): string {
  // "2026-06-16" → "6/16 (화)"
  const [y, m, d] = iso.split("-").map(Number);
  const wd = ["일", "월", "화", "수", "목", "금", "토"][
    new Date(y, m - 1, d).getDay()
  ];
  return `${m}/${d} (${wd})`;
}

export function fmtPrice(n: number): string {
  return `$${n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function fmtPct(n: number): string {
  return `${n >= 0 ? "+" : ""}${n.toFixed(1)}%`;
}

export function fmtKRW(n: number): string {
  return n.toLocaleString("ko-KR") + "원";
}

export function fmtUSD(n: number): string {
  return "$" + Math.round(n).toLocaleString("en-US");
}
