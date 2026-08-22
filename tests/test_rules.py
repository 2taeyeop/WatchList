"""판정 엔진 유닛테스트 — 작업지시 8절 수용 기준."""
import pytest

from backend.rules import (
    Snapshot, judge_monthly, judge_accel, episode_reset_updates, crisis_update,
    judge_december, judge_harvest, judge_withdraw, judge_entry, portfolio_mismatch,
)


def snap(tq=100, je=100, tp=70.0, jp=55.0) -> Snapshot:
    return Snapshot(qld_shares=tq, jepi_shares=je, qld_price=tp, jepi_price=jp)


# ---------- A. 월간 적립: 내림·잔돈 이월 ----------
def test_monthly_buys_qld_below_target_with_floor_and_carry():
    s = snap(tq=50, je=100, tp=73.5, jp=55.0)  # QLD 비중 40% < 70%
    j = judge_monthly(s, avail_usd=1000.0)
    assert len(j.orders) == 1
    order = j.orders[0]
    assert (order.ticker, order.side, order.shares) == ("QLD", "BUY", 13)  # floor(1000/73.5)
    assert order.est_usd == pytest.approx(955.5)
    assert j.carry_delta_usd == pytest.approx(44.5)
    assert j.weight_after > j.weight_before


def test_monthly_buys_jepi_at_or_above_target():
    s = snap(tq=100, je=10, tp=70.0, jp=55.0)  # QLD 비중 92.7% ≥ 70%
    j = judge_monthly(s, avail_usd=500.0)
    assert j.orders[0].ticker == "JEPI"
    assert j.orders[0].shares == 9  # floor(500/55)


def test_monthly_zero_holdings_counts_as_below_target():
    j = judge_monthly(snap(tq=0, je=0), avail_usd=300.0)
    assert j.orders[0].ticker == "QLD"


# ---------- B. 가속 수명주기 ----------
def test_accel_tier1_fires_at_minus_25():
    s = snap(je=101, jp=55.0, tp=50.0)
    j = judge_accel(s, drawdown=-0.26, tier1_fired=False, tier2_fired=False, year=2026)
    assert j is not None
    sell, buy = j.orders
    assert (sell.ticker, sell.side, sell.shares) == ("JEPI", "SELL", 50)   # 101//2
    assert (buy.ticker, buy.side, buy.shares) == ("QLD", "BUY", 55)      # floor(2750/50)
    assert j.state_updates["tier1_fired"] is True
    assert j.state_updates["skip_december_year"] == 2026
    assert j.state_updates["episode_active"] is True


def test_accel_tier1_locked_after_fire():
    s = snap()
    assert judge_accel(s, -0.30, tier1_fired=True, tier2_fired=False, year=2026) is None


def test_accel_tier2_fires_on_remaining_jepi():
    s = snap(je=51)  # 1단 발동 후 잔여
    j = judge_accel(s, -0.41, tier1_fired=True, tier2_fired=False, year=2026)
    assert j.orders[0].shares == 25  # 51//2
    assert j.state_updates["tier2_fired"] is True


def test_accel_both_tiers_same_day_sequential():
    s = snap(je=100, jp=50.0, tp=25.0)
    j = judge_accel(s, -0.45, tier1_fired=False, tier2_fired=False, year=2026)
    assert len(j.orders) == 4
    t1_sell, _, t2_sell, _ = j.orders
    assert t1_sell.shares == 50   # 100//2
    assert t2_sell.shares == 25   # (100-50)//2 — 1단 매도 반영 후 잔여의 절반
    assert j.state_updates["tier1_fired"] is True
    assert j.state_updates["tier2_fired"] is True


def test_accel_no_fire_above_threshold():
    assert judge_accel(snap(), -0.24, False, False, 2026) is None


def test_episode_reset_and_rearm():
    # −10% 안쪽 회복 → 플래그 리셋(재장전)
    updates = episode_reset_updates(-0.09, episode_active=True, tier1_fired=True, tier2_fired=True)
    assert updates == {"episode_active": False, "tier1_fired": False, "tier2_fired": False}
    # 재장전 후 다시 −25% → 1단 재발동 가능
    j = judge_accel(snap(), -0.26, tier1_fired=False, tier2_fired=False, year=2027)
    assert j is not None


def test_episode_reset_not_triggered_while_deep():
    assert episode_reset_updates(-0.12, True, True, False) == {}
    assert episode_reset_updates(-0.05, False, False, False) == {}  # 발동 이력 없으면 무변경


# ---------- 위기 모드 히스테리시스 ----------
def test_crisis_hysteresis():
    assert crisis_update(-0.21, False) is True    # −20% 이하 진입
    assert crisis_update(-0.15, True) is True     # 중간 구간 유지
    assert crisis_update(-0.15, False) is False   # 진입한 적 없으면 계속 꺼짐
    assert crisis_update(-0.09, True) is False    # −10% 안쪽 회복 시 해제


# ---------- C. 12월 리밸런싱 ----------
def test_december_pass_within_one_share():
    # 총평가 12,650, 목표 floor(12650*0.7/70)=126 vs 현재 125 → 차이 1주 패스
    s = snap(tq=125, je=71, tp=70.0, jp=55.0)
    j = judge_december(s, year=2026, skip_december_year=None)
    assert j.action == "12월 리밸런싱 패스"
    assert j.orders == ()


def test_december_sells_excess_qld_into_jepi():
    s = snap(tq=150, je=20, tp=70.0, jp=55.0)  # QLD 과체중
    j = judge_december(s, 2026, None)
    sell, buy = j.orders
    assert sell.ticker == "QLD" and sell.side == "SELL"
    assert buy.ticker == "JEPI" and buy.side == "BUY"
    target = 116  # floor(11600*0.7/70)
    assert sell.shares == 150 - target
    assert j.weight_after == pytest.approx(0.70, abs=0.01)


def test_december_buys_qld_funded_by_jepi():
    s = snap(tq=50, je=200, tp=70.0, jp=55.0)  # QLD 저체중
    j = judge_december(s, 2026, None)
    sell, buy = j.orders
    assert sell.ticker == "JEPI"
    assert buy.ticker == "QLD"
    target = int((50 * 70 + 200 * 55) * 0.7 // 70)
    assert buy.shares == target - 50


def test_december_skipped_in_accel_year():
    j = judge_december(snap(), year=2026, skip_december_year=2026)
    assert j.action == "12월 리밸런싱 스킵"
    assert j.orders == ()


def test_december_not_skipped_next_year():
    j = judge_december(snap(tq=150, je=20), year=2027, skip_december_year=2026)
    assert j.action == "12월 리밸런싱"


# ---------- D. 공제 수확 ----------
def test_harvest_fills_deduction_room():
    j = judge_harvest(1_000_000, gain_positions=[("QLD", 30_000, 100)], loss_positions=[])
    sell, rebuy = j.orders
    assert sell.shares == rebuy.shares == 50  # floor(1_500_000/30_000)
    assert sell.side == "SELL" and rebuy.side == "BUY"


def test_harvest_capped_by_held_shares():
    j = judge_harvest(0, gain_positions=[("QLD", 10_000, 3)], loss_positions=[])
    assert j.orders[0].shares == 3


def test_harvest_proposes_loss_harvest_over_limit():
    # 초과 500,000원 ÷ 주당 손실 5,000원 = 100주 필요하나 보유 40주로 상한
    j = judge_harvest(3_000_000, gain_positions=[("QLD", 30_000, 100)],
                      loss_positions=[("JEPI", -5_000, 40)])
    assert "손실 수확" in j.action
    assert j.orders[0].ticker == "JEPI"
    assert j.orders[0].shares == 40


def test_loss_harvest_sells_only_needed_shares():
    # 초과 500,000원 ÷ 주당 손실 50,000원 = 10주만 — 전량(40주) 매도는 초과 실현
    j = judge_harvest(3_000_000, gain_positions=[],
                      loss_positions=[("JEPI", -50_000, 40)])
    assert j.orders[0].shares == 10
    assert j.orders[1].shares == 10


def test_harvest_exact_limit_boundary_no_action():
    # 정확히 250만원 = 공제 한도 소진 — 손실 수확 분기로 넘어가면 안 됨
    j = judge_harvest(2_500_000, gain_positions=[], loss_positions=[("JEPI", -500, 10)])
    assert j.orders == ()
    assert "패스" in j.action


def test_harvest_falls_back_to_second_gain_ticker():
    # 여유 60,000원 < QLD 주당 90,000원 → JEPI(20,000원)로 폴백해 3주 수확
    j = judge_harvest(2_440_000, gain_positions=[("QLD", 90_000, 100), ("JEPI", 20_000, 50)],
                      loss_positions=[])
    assert "JEPI 3주" in j.action
    assert len(j.orders) == 2


def test_harvest_continues_across_tickers():
    # QLD 3주(9만) 소진 후 잔여 241만을 JEPI 로 이어서 수확
    j = judge_harvest(0, gain_positions=[("QLD", 30_000, 3), ("JEPI", 10_000, 200)],
                      loss_positions=[])
    assert "QLD 3주" in j.action and "JEPI 200주" in j.action
    assert len(j.orders) == 4


def test_harvest_no_gain_positions():
    j = judge_harvest(0, gain_positions=[], loss_positions=[])
    assert j.orders == ()


# ---------- E. 생계 인출 70:30 ----------
def test_withdraw_ratio_and_ceiling():
    s = snap(tq=1000, je=1000, tp=70.0, jp=55.0)
    j = judge_withdraw(1_400_000, fx=1400.0, snap=s)  # $1,000 필요
    qld, jepi = j.orders
    assert qld.shares == 10  # ceil(700/70)
    assert jepi.shares == 6   # ceil(300/55)
    raised = qld.est_usd + jepi.est_usd
    assert raised >= 1000.0   # 필요액 이상 확보(매도는 올림)


def test_withdraw_capped_by_holdings():
    s = snap(tq=2, je=1, tp=70.0, jp=55.0)
    j = judge_withdraw(10_000_000, fx=1000.0, snap=s)
    assert j.orders[0].shares == 2
    assert j.orders[1].shares == 1


def test_withdraw_rejects_non_positive_amounts():
    s = snap(tq=100, je=80)
    for bad in (-3_000_000, 0, float("nan")):
        j = judge_withdraw(bad, fx=1400.0, snap=s)
        assert j.orders == ()
        assert j.action == "인출 불가"


def test_withdraw_reports_realized_pnl():
    s = snap(tq=1000, je=1000, tp=70.0, jp=55.0)
    j = judge_withdraw(1_400_000, 1400.0, s,
                       qld_gain_krw_per_share=50_000, jepi_gain_krw_per_share=-1_000)
    assert "+500,000원" in j.reason   # 10주 × 5만원
    assert "-6,000원" in j.reason     # 6주 × −1천원


# ---------- 진입기 주간 루틴 ----------
def test_entry_week1_sells_fifth():
    j = judge_entry(sgov_shares=100, entry_week=1, sgov_price=100.0, qld_price=70.0)
    assert j.orders[0].shares == 20  # 100//5
    assert j.state_updates == {"entry_week": 2}


def test_entry_week5_sells_all_and_transitions_steady():
    j = judge_entry(sgov_shares=23, entry_week=5, sgov_price=100.0, qld_price=70.0)
    assert j.orders[0].shares == 23
    assert j.state_updates == {"phase": "STEADY", "entry_week": 1}


# ---------- 포트폴리오 불일치 ----------
def test_mismatch_detects_foreign_tickers():
    assert portfolio_mismatch(["QLD", "JEPI", "AAPL"], "STEADY") == ["AAPL"]


def test_mismatch_allows_sgov_only_in_entry():
    assert portfolio_mismatch(["QLD", "JEPI", "SGOV"], "ENTRY") == []
    assert portfolio_mismatch(["QLD", "JEPI", "SGOV"], "STEADY") == ["SGOV"]


def test_mismatch_setup_phase_exempt():
    assert portfolio_mismatch(["AAPL", "TSLA"], "SETUP") == []
