"""상태 저장소 라운드트립 테스트 — 임시 DB 파일 사용."""
import pytest


@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("WATCHLIST_DB", str(tmp_path / "test.db"))
    from backend import db as db_module
    db_module.init_db()
    return db_module


def test_state_defaults_and_update(db):
    s = db.get_state()
    assert s["phase"] == "SETUP"
    assert s["entry_week"] == 1
    assert s["crisis_active"] is False
    assert s["carry_usd"] == 0

    db.update_state(phase="ENTRY", crisis_active=True, monthly_day=25, carry_usd=12.34)
    s = db.get_state()
    assert (s["phase"], s["monthly_day"]) == ("ENTRY", 25)
    assert s["crisis_active"] is True
    assert s["carry_usd"] == pytest.approx(12.34)


def test_update_state_rejects_unknown_column(db):
    with pytest.raises(ValueError):
        db.update_state(nope=1)


def test_log_append_only_and_format(db):
    db.append_log("월간적립 QLD 13주", "-3.2%", "68.1%→69.4%", "테스트", date="2026-07-22")
    db.append_log("가속 1단 발동", "-26.0%", "55.0%→77.0%", date="2026-07-23")
    logs = db.recent_logs()
    assert len(logs) == 2
    assert logs[0]["action"] == "가속 1단 발동"  # 최신 우선
    assert db.format_log(logs[1]) == "2026-07-22 | 월간적립 QLD 13주 | -3.2% | 68.1%→69.4% | 테스트"


def test_pending_roundtrip(db):
    db.set_pending("monthly", {"cash_usd": 100.5})
    assert db.pop_pending() == ("monthly", {"cash_usd": 100.5})
    assert db.pop_pending() is None  # 게이트는 1회용

    db.set_pending("monthly", {"a": 1})
    db.set_pending("withdraw", {"b": 2})  # 새 사진이 오면 교체
    kind, payload = db.pop_pending()
    assert kind == "withdraw" and payload == {"b": 2}

    db.set_pending("monthly", {"a": 1})
    db.clear_pending()
    assert db.pop_pending() is None
