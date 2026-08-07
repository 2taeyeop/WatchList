"""규칙서 판정 엔진 — 순수 함수만(I/O·상태 저장·시장 조회 없음).

돈 계산은 전부 여기서 결정적으로 처리한다(작업지시 3절: 계산은 코드, 언어는 클로드).
상태 반영·로그 저장은 호출자(bot)가 Judgment.state_updates 로 수행한다.
금액은 USD 기준, 원화는 *_krw 접미사. 정수 주만, 매수는 내림(floor), 잔돈은 이월.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

TARGET_TQQQ = 0.70            # 목표 비율 TQQQ 70 : JEPI 30
TIER1_DD = -0.25              # 가속 1단 발동 하락률(나스닥100 종가 기준)
TIER2_DD = -0.40              # 가속 2단
EPISODE_RESET_DD = -0.10      # 이 안쪽 회복 확인 = 에피소드 종료·위기 해제
CRISIS_DD = -0.20             # 위기 모드 진입
HARVEST_LIMIT_KRW = 2_500_000  # 해외주식 양도세 기본공제
MONTHLY_KRW = 300_000         # 월 적립 환전액
ENTRY_WEEKS = 5               # 진입기 주간 분할 횟수

ALLOWED_STEADY = {"TQQQ", "JEPI"}
ALLOWED_ENTRY = {"TQQQ", "JEPI", "SGOV"}


@dataclass(frozen=True)
class Order:
    ticker: str
    side: str          # "SELL" | "BUY"
    shares: int
    est_usd: float
    note: str = ""     # 예: "즉시 재매수(취득가 상향)"


@dataclass(frozen=True)
class Snapshot:
    """판정 시점 보유 현황 — 스크린샷 추출 주수 + 서버 조회 현재가."""
    tqqq_shares: int
    jepi_shares: int
    tqqq_price: float
    jepi_price: float

    @property
    def tqqq_value(self) -> float:
        return self.tqqq_shares * self.tqqq_price

    @property
    def jepi_value(self) -> float:
        return self.jepi_shares * self.jepi_price

    @property
    def total_value(self) -> float:
        return self.tqqq_value + self.jepi_value

    @property
    def tqqq_weight(self) -> float:
        total = self.total_value
        return self.tqqq_value / total if total else 0.0


@dataclass(frozen=True)
class Judgment:
    action: str                       # 로그 '행동' 칼럼용 짧은 라벨
    reason: str                       # 판정 근거 숫자(한국어 한두 줄)
    orders: tuple[Order, ...] = ()
    carry_delta_usd: float = 0.0      # 이월 잔돈 증감
    weight_before: float | None = None
    weight_after: float | None = None
    state_updates: dict = field(default_factory=dict)


_EPS = 1e-9


def _floor_div(amount: float, price: float) -> int:
    """이진 부동소수점 오차로 정확히 나누어떨어지는 값이 1주 모자라게 잘리는 것 방지."""
    if price <= 0:
        return 0
    return math.floor(amount / price + _EPS)


def _ceil_div(amount: float, price: float) -> int:
    """올림의 반대 방향 오차(정확히 나누어떨어지는데 1주 초과) 방지."""
    if price <= 0:
        return 0
    return math.ceil(amount / price - _EPS)


def _weight(tqqq_shares: int, jepi_shares: int, tqqq_price: float, jepi_price: float) -> float:
    total = tqqq_shares * tqqq_price + jepi_shares * jepi_price
    return tqqq_shares * tqqq_price / total if total else 0.0


# ---------- A. 월간 적립 ----------
def judge_monthly(snap: Snapshot, avail_usd: float) -> Judgment:
    """비중<70% → 가용달러 전액 TQQQ 내림 매수, 아니면 전액 JEPI. 잔돈은 이월."""
    w = snap.tqqq_weight
    buy_tqqq = w < TARGET_TQQQ
    ticker, price = ("TQQQ", snap.tqqq_price) if buy_tqqq else ("JEPI", snap.jepi_price)
    shares = _floor_div(avail_usd, price)
    spent = shares * price
    after = _weight(snap.tqqq_shares + (shares if buy_tqqq else 0),
                    snap.jepi_shares + (0 if buy_tqqq else shares),
                    snap.tqqq_price, snap.jepi_price)
    orders = (Order(ticker, "BUY", shares, spent),) if shares > 0 else ()
    return Judgment(
        action=f"월간적립 {ticker} {shares}주",
        reason=f"TQQQ 비중 {w:.1%} → {'70% 미만이라 TQQQ' if buy_tqqq else '70% 이상이라 JEPI'} 매수. "
               f"가용 ${avail_usd:,.2f} 중 ${spent:,.2f} 사용",
        orders=orders,
        carry_delta_usd=avail_usd - spent,
        weight_before=w, weight_after=after,
    )


# ---------- B. 가속조항 ----------
def judge_accel(snap: Snapshot, drawdown: float, tier1_fired: bool, tier2_fired: bool,
                year: int) -> Judgment | None:
    """에피소드당 1회씩, 같은 판정일 동시 충족이면 1단→2단 순차 적용. 미발동이면 None."""
    jepi = snap.jepi_shares
    tqqq = snap.tqqq_shares
    orders: list[Order] = []
    carry = 0.0
    updates: dict = {}
    fired: list[str] = []

    for tier, threshold, already in (("1단", TIER1_DD, tier1_fired), ("2단", TIER2_DD, tier2_fired)):
        if already or drawdown > threshold:
            continue
        sell = jepi // 2
        proceeds = sell * snap.jepi_price
        buy = _floor_div(proceeds, snap.tqqq_price)
        orders.append(Order("JEPI", "SELL", sell, sell * snap.jepi_price))
        orders.append(Order("TQQQ", "BUY", buy, buy * snap.tqqq_price))
        carry += proceeds - buy * snap.tqqq_price
        jepi -= sell
        tqqq += buy
        updates[f"tier{tier[0]}_fired"] = True
        fired.append(tier)

    if not fired:
        return None

    updates.update(episode_active=True, skip_december_year=year)
    return Judgment(
        action=f"가속 {'·'.join(fired)} 발동",
        reason=f"하락률 {drawdown:.1%} — {'·'.join(fired)} 기준 충족. "
               f"JEPI 절반 매도 대금 전액 TQQQ 매수, 올해 12월 리밸런싱 스킵",
        orders=tuple(orders),
        carry_delta_usd=carry,
        weight_before=snap.tqqq_weight,
        weight_after=_weight(tqqq, jepi, snap.tqqq_price, snap.jepi_price),
        state_updates=updates,
    )


def episode_reset_updates(drawdown: float, episode_active: bool,
                          tier1_fired: bool, tier2_fired: bool) -> dict:
    """하락률이 −10% 안쪽으로 회복 확인된 판정일 = 에피소드 종료·재장전.
    JEPI 잔량 복원은 12월 리밸런싱의 몫이라 여기선 플래그만 리셋한다."""
    if drawdown <= EPISODE_RESET_DD:
        return {}
    if not (episode_active or tier1_fired or tier2_fired):
        return {}
    return {"episode_active": False, "tier1_fired": False, "tier2_fired": False}


def crisis_update(drawdown: float, crisis_active: bool) -> bool:
    """−20% 이하 진입, −10% 안쪽 회복 확인 시 해제 — 사이 구간은 이력 유지(히스테리시스)."""
    if drawdown <= CRISIS_DD:
        return True
    if drawdown > EPISODE_RESET_DD:
        return False
    return crisis_active


# ---------- C. 12월 셋째 월요일 리밸런싱 ----------
def judge_december(snap: Snapshot, year: int, skip_december_year: int | None) -> Judgment:
    if skip_december_year == year:
        return Judgment(
            action="12월 리밸런싱 스킵",
            reason=f"{year}년 가속 발동 연도 — 바닥에서 TQQQ를 되파는 자기모순 방지 규칙",
            weight_before=snap.tqqq_weight, weight_after=snap.tqqq_weight,
        )

    w = snap.tqqq_weight
    target = _floor_div(snap.total_value * TARGET_TQQQ, snap.tqqq_price)
    diff = target - snap.tqqq_shares
    if abs(diff) <= 1:
        return Judgment(
            action="12월 리밸런싱 패스",
            reason=f"목표 TQQQ {target}주 vs 현재 {snap.tqqq_shares}주 — 차이 {abs(diff)}주(≤1주)",
            weight_before=w, weight_after=w,
        )

    orders: list[Order] = []
    carry = 0.0
    if diff < 0:
        sell = -diff
        proceeds = sell * snap.tqqq_price
        buy = _floor_div(proceeds, snap.jepi_price)
        orders.append(Order("TQQQ", "SELL", sell, proceeds))
        orders.append(Order("JEPI", "BUY", buy, buy * snap.jepi_price))
        carry = proceeds - buy * snap.jepi_price
        after = _weight(target, snap.jepi_shares + buy, snap.tqqq_price, snap.jepi_price)
    else:
        need = diff * snap.tqqq_price
        sell = min(snap.jepi_shares, _ceil_div(need, snap.jepi_price))
        proceeds = sell * snap.jepi_price
        # 목표는 70:30 복원이지 TQQQ 초과 매수가 아니므로 diff 주로 상한.
        buy = min(diff, _floor_div(proceeds, snap.tqqq_price))
        orders.append(Order("JEPI", "SELL", sell, proceeds))
        orders.append(Order("TQQQ", "BUY", buy, buy * snap.tqqq_price))
        carry = proceeds - buy * snap.tqqq_price
        after = _weight(snap.tqqq_shares + buy, snap.jepi_shares - sell,
                        snap.tqqq_price, snap.jepi_price)
    return Judgment(
        action="12월 리밸런싱",
        reason=f"목표 TQQQ {target}주 vs 현재 {snap.tqqq_shares}주 — 차이 {diff:+}주",
        orders=tuple(orders), carry_delta_usd=carry,
        weight_before=w, weight_after=after,
    )


# ---------- D. 공제 수확 (12월, C와 같은 날) ----------
def judge_harvest(net_realized_krw: float,
                  gain_positions: list[tuple[str, float, int]],
                  loss_positions: list[tuple[str, float, int]]) -> Judgment:
    """positions: (ticker, 주당 원화 평가손익, 보유 주수).

    순실현차익 < 250만 → 이익 종목 매도 후 즉시 재매수로 공제 한도 소진(취득가 상향).
    순실현차익 > 250만 + 평가손실 보유 → 손실 수확 제안 먼저(한국은 워시세일 없음)."""
    room = HARVEST_LIMIT_KRW - net_realized_krw
    if room > 0:
        gains = sorted([(t, g, s) for t, g, s in gain_positions if g > 0 and s > 0],
                       key=lambda x: x[1], reverse=True)
        if not gains:
            return Judgment(action="공제 수확 불가",
                            reason=f"공제 여유 {room:,.0f}원이나 이익 종목 없음")
        # 주당 차익 큰 종목부터 남은 한도를 이어서 소진 — 0주면 다음 종목으로 폴백.
        orders: list[Order] = []
        picked: list[tuple[str, int]] = []
        remaining = room
        for ticker, gain_per, held in gains:
            shares = min(held, _floor_div(remaining, gain_per))
            if shares <= 0:
                continue
            orders.append(Order(ticker, "SELL", shares, 0.0, note="공제 수확"))
            orders.append(Order(ticker, "BUY", shares, 0.0, note="즉시 재매수(취득가 상향)"))
            picked.append((ticker, shares))
            remaining -= shares * gain_per
        if not orders:
            return Judgment(action="공제 수확 패스",
                            reason=f"공제 여유 {room:,.0f}원 — 모든 이익 종목의 주당 차익이 여유보다 커 1주도 불가")
        harvested = ", ".join(f"{t} {s}주" for t, s in picked)
        return Judgment(
            action=f"공제 수확 {harvested}",
            reason=f"순실현차익 {net_realized_krw:,.0f}원, 공제 여유 {room:,.0f}원 중 "
                   f"{room - remaining:,.0f}원 소진"
                   + (f" (잔여 {remaining:,.0f}원은 주당 차익 미만)" if remaining > 0 else ""),
            orders=tuple(orders),
        )

    if room == 0:
        return Judgment(action="공제 수확 패스",
                        reason=f"순실현차익이 공제 한도({HARVEST_LIMIT_KRW:,.0f}원)와 정확히 일치 — 조치 없음")

    losses = [(t, g, s) for t, g, s in loss_positions if g < 0 and s > 0]
    if losses:
        # 필요한 만큼만 손실을 실현 — 초과 실현은 이월공제가 없어 상쇄 효과 0, 취득가만 낮아짐.
        need = -room
        ticker, loss_per, held = min(losses, key=lambda x: x[1])
        shares = min(held, _ceil_div(need, abs(loss_per)))
        offset = min(need, shares * abs(loss_per))
        return Judgment(
            action=f"손실 수확 제안 {ticker} {shares}주",
            reason=f"순실현차익 {net_realized_krw:,.0f}원 — 공제 초과 {need:,.0f}원 ÷ 주당 손실 "
                   f"{abs(loss_per):,.0f}원 → {shares}주 매도 후 즉시 재매수로 {offset:,.0f}원 상쇄"
                   + (" (보유 전량으로도 초과분 일부만 상쇄)" if offset < need else "")
                   + " · 한국은 워시세일 규정 없음",
            orders=(Order(ticker, "SELL", shares, 0.0, note="손실 수확"),
                    Order(ticker, "BUY", shares, 0.0, note="즉시 재매수")),
        )
    return Judgment(action="공제 수확 해당 없음",
                    reason=f"순실현차익 {net_realized_krw:,.0f}원 — 공제 한도 초과이나 평가손실 종목 없음")


# ---------- E. 생계 인출 ----------
def judge_withdraw(need_krw: float, fx: float, snap: Snapshot,
                   tqqq_gain_krw_per_share: float | None = None,
                   jepi_gain_krw_per_share: float | None = None) -> Judgment:
    """필요 원화 → 달러 환산 → TQQQ 70 : JEPI 30 금액 비율 매도. 정상 절차."""
    # 음수·0·NaN 방어 — 음수 금액은 _ceil_div 가 음수 주수를 만들어 상한(min)을 무력화한다.
    if not (need_krw > 0) or not (fx > 0):
        return Judgment(action="인출 불가",
                        reason=f"인출 금액이 올바르지 않습니다: {need_krw!r} (양수 원화 금액 필요)")
    need_usd = need_krw / fx
    plans = (("TQQQ", need_usd * TARGET_TQQQ, snap.tqqq_price, snap.tqqq_shares, tqqq_gain_krw_per_share),
             ("JEPI", need_usd * (1 - TARGET_TQQQ), snap.jepi_price, snap.jepi_shares, jepi_gain_krw_per_share))
    orders: list[Order] = []
    realized_notes: list[str] = []
    sold = {"TQQQ": 0, "JEPI": 0}
    for ticker, amount, price, held, gain_per in plans:
        # 필요액을 확보해야 하므로 매도는 올림(부족분 방지), 보유 주수로 상한.
        shares = min(held, _ceil_div(amount, price))
        sold[ticker] = shares
        if shares <= 0:
            continue
        orders.append(Order(ticker, "SELL", shares, shares * price))
        if gain_per is not None:
            realized_notes.append(f"{ticker} 예상 실현손익 {gain_per * shares:+,.0f}원")
    total_usd = sum(o.est_usd for o in orders)
    reason = (f"필요 {need_krw:,.0f}원 = ${need_usd:,.2f} (환율 {fx:,.1f}) → 70:30 매도. "
              f"확보 ${total_usd:,.2f}")
    if realized_notes:
        reason += " · " + ", ".join(realized_notes) + " — 250만 공제 초과분은 22% 과세 대상"
    return Judgment(
        action=f"생계 인출 {need_krw:,.0f}원",
        reason=reason,
        orders=tuple(orders),
        weight_before=snap.tqqq_weight,
        weight_after=_weight(snap.tqqq_shares - sold["TQQQ"], snap.jepi_shares - sold["JEPI"],
                             snap.tqqq_price, snap.jepi_price),
    )


# ---------- 진입기(ENTRY) 주간 루틴 ----------
def judge_entry(sgov_shares: int, entry_week: int, sgov_price: float, tqqq_price: float) -> Judgment:
    """이번 주차의 SGOV 매도 → TQQQ 매수. 5주차는 SGOV 잔량 전부."""
    remaining_weeks = max(1, ENTRY_WEEKS - entry_week + 1)
    sell = sgov_shares if entry_week >= ENTRY_WEEKS else sgov_shares // remaining_weeks
    proceeds = sell * sgov_price
    buy = _floor_div(proceeds, tqqq_price)
    updates: dict = {"entry_week": entry_week + 1}
    if entry_week >= ENTRY_WEEKS:
        updates = {"phase": "STEADY", "entry_week": 1}  # 5회 완료 → 자동 STEADY 전환
    return Judgment(
        action=f"진입 {entry_week}주차",
        reason=f"SGOV 잔량 {sgov_shares}주의 1/{remaining_weeks}"
               + (" (마지막 주 — 전량)" if entry_week >= ENTRY_WEEKS else ""),
        orders=(Order("SGOV", "SELL", sell, proceeds),
                Order("TQQQ", "BUY", buy, buy * tqqq_price)),
        carry_delta_usd=proceeds - buy * tqqq_price,
        state_updates=updates,
    )


# ---------- 포트폴리오 불일치 검사 ----------
def portfolio_mismatch(tickers: list[str], phase: str) -> list[str]:
    """규칙서 포트폴리오와 불일치하는 티커 목록. SETUP 은 가동 전이라 검사 제외."""
    if phase == "SETUP":
        return []
    allowed = ALLOWED_ENTRY if phase == "ENTRY" else ALLOWED_STEADY
    return sorted(set(t.upper() for t in tickers) - allowed)
