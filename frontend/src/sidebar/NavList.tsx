// 좌측 사이드바 = 상위 화면(섹션) 내비. 날짜 이동은 stepper/달력으로 분리됨.
// homenav(데일리 모니터링 내부 5탭)와는 별개 — 여기선 어떤 기능 화면을 볼지만 고른다.
import type { IconKey } from "../shared/icons";
import { ICONS } from "../shared/icons";
import "./sidebar.css";

export type Section = "daily" | "search";

const ITEMS: { section: Section; label: string; icon: IconKey }[] = [
  { section: "daily", label: "데일리 모니터링", icon: "digest" },
  { section: "search", label: "종목 검색", icon: "search" },
];

interface Props {
  section: Section;
  onSelect: (section: Section) => void;
}

export default function NavList({ section, onSelect }: Props) {
  return (
    <nav className="navlist">
      <ul className="navlist__items">
        {ITEMS.map((it) => (
          <li key={it.section}>
            <button
              className={`navlist__item${section === it.section ? " is-active" : ""}`}
              onClick={() => onSelect(it.section)}
            >
              <span className="navlist__icon">{ICONS[it.icon]}</span>
              <span className="navlist__label">{it.label}</span>
            </button>
          </li>
        ))}
      </ul>
    </nav>
  );
}
