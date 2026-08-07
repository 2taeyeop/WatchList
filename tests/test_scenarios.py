"""시나리오 테스트 — 작업지시 8절 3건.

봇의 판정 경로(run_judgment)를 텔레그램·클로드 없이 검증한다(임시 DB 사용).
③ 불일치 정지는 게이트에서 쓰는 순수 함수(portfolio_mismatch·needs_retake)로 검증 —
handle_photo 자체는 텔레그램/클로드 I/O 라 유닛 범위 밖.
"""
import pytest

from backend import vision
from backend.rules import portfolio_mismatch


@pytest.fixture()
def bot(tmp_path, monkeypatch):
    monkeypatch.setenv("WATCHLIST_DB", str(tmp_path / "test.db"))
    monkeypatch.delenv("NOTION_TOKEN", raising=False)  # 노션 동기화 무력화
    from backend import bot as bot_module, db as db_module
    db_module.init_db()
    db_module.update_state(phase="STEADY")
    return bot_module


def payload(tq=50, je=100, tp=70.0, jp=55.0, dd=-0.03, cash_usd=1000.0,
            pnl_tq=None, pnl_je=None, fx=1400.0):
    return {
        "extracted": {
            "positions": [
                {"ticker": "TQQQ", "shares": tq, "pnl_krw": pnl_tq},
                {"ticker": "JEPI", "shares": je, "pnl_krw": pnl_je},
            ],
            "cash_usd": cash_usd, "cash_krw": 0, "unclear": [],
        },
        "market": {
            "ndx": {"latest_close": 20000.0, "peak_close": 20000.0 / (1 + dd),
                    "drawdown": dd, "latest_date": "2026-07-21"},
            "prices": {"TQQQ": tp, "JEPI": jp},
            "fx": fx,
        },
        "args": {},
    }


# ① 평시 월간 — 발동 없음, 매수 주수만
def test_scenario_normal_monthly(bot):
    from backend import db
    text = bot.run_judgment("monthly", payload(dd=-0.03))
    assert "월간적립 TQQQ 14주" in text          # floor(1000/70)
    assert "가속" not in text
    state = db.get_state()
    assert state["tier1_fired"] is False
    assert state["crisis_active"] is False
    assert len(db.recent_logs()) == 1


# ② 하락률 −26% 최초 확인 — 1단 주문표 + 위기 모드 진입
def test_scenario_first_tier1_at_minus_26(bot):
    from backend import db
    text = bot.run_judgment("monthly", payload(dd=-0.26, je=100, jp=55.0, tp=70.0))
    assert "가속 1단 발동" in text
    assert "JEPI | 매도 | 50주" in text          # 100//2
    assert "TQQQ | 매수 | 39주" in text          # floor(2750/70)
    state = db.get_state()
    assert state["tier1_fired"] is True
    assert state["tier2_fired"] is False
    assert state["skip_december_year"] is not None
    assert state["crisis_active"] is True        # 배너는 _send 가 모든 회신 상단에 부착
    # 같은 에피소드 재점검 — 1단 잠김, 월간 판정으로 진행
    text2 = bot.run_judgment("monthly", payload(dd=-0.30))
    assert "가속" not in text2
    assert "월간적립" in text2


# ③ 규칙서와 불일치하는 스크린샷 — 게이트에서 정지
def test_scenario_mismatch_stops_at_gate():
    assert portfolio_mismatch(["TQQQ", "JEPI", "AAPL"], "STEADY") == ["AAPL"]
    # 주수를 못 읽은 추출 결과는 재촬영 사유가 되어 게이트 전에 정지
    data = {"positions": [{"ticker": "TQQQ", "shares": None, "name_raw": "TQQQ"}],
            "cash_usd": None, "cash_krw": None, "unclear": []}
    assert vision.needs_retake(data, "monthly") != []


# 판정별 필수값 결손 — '못 읽음'을 0/'없음'으로 단정하지 않고 게이트 전에 차단
def test_null_required_fields_block_at_gate():
    ok_positions = [{"ticker": "TQQQ", "shares": 10, "pnl_krw": None}]
    # monthly: 예수금 null → 재촬영
    data = {"positions": ok_positions, "cash_usd": None, "cash_krw": 0, "unclear": []}
    assert any("예수금" in r for r in vision.needs_retake(data, "monthly"))
    # december: 평가손익 null → 재촬영
    data2 = {"positions": ok_positions, "cash_usd": 100.0, "cash_krw": 0, "unclear": []}
    assert any("평가손익" in r for r in vision.needs_retake(data2, "december"))
    # 값이 다 있으면 통과
    full = {"positions": [{"ticker": "TQQQ", "shares": 10, "pnl_krw": 1000}],
            "cash_usd": 100.0, "cash_krw": 0, "unclear": []}
    assert vision.needs_retake(full, "monthly") == []
    assert vision.needs_retake(full, "december") == []


# 생계 인출은 가속조항에 가로채이지 않는다(E: 즉시 협조, 플래그도 미소진)
def test_scenario_withdraw_not_intercepted_by_accel(bot):
    from backend import db
    p = payload(tq=1000, je=1000, dd=-0.26)
    p["args"]["need_krw"] = 1_400_000
    text = bot.run_judgment("withdraw", p)
    assert "생계 인출" in text
    assert "가속" not in text
    state = db.get_state()
    assert state["tier1_fired"] is False  # 다음 점검일에 발동하도록 보존
    assert state["crisis_active"] is True  # 위기 배너는 그대로 반영


# 보조: 12월 통합(리밸런싱+공제)과 인출 경로도 판정 문자열까지 통증검사
def test_scenario_december_with_harvest(bot):
    p = payload(tq=150, je=20, dd=-0.03, pnl_tq=3_000_000, pnl_je=-200_000)
    p["args"]["realized_krw"] = 1_000_000
    text = bot.run_judgment("december", p)
    assert "12월 리밸런싱" in text
    assert "공제 수확" in text


def test_scenario_withdraw(bot):
    p = payload(tq=1000, je=1000, dd=-0.03, pnl_tq=70_000_000, pnl_je=1_000_000)
    p["args"]["need_krw"] = 1_400_000
    text = bot.run_judgment("withdraw", p)
    assert "생계 인출" in text
    assert "TQQQ | 매도 | 10주" in text
    assert "JEPI | 매도 | 6주" in text
