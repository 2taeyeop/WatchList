"""텔레그램 규칙서 집행봇 — 롱폴링(getUpdates) 상시 프로세스.

플로우: 사진 수신 → 비전 추출 + 시장 데이터 서버 주입 → 확인 게이트(생략 불가,
nonce 바인딩) → ✅ 시 판정(rules 순수 함수) → 회신 전송 성공 후에만 상태·로그 커밋.
주문 실행 자동화는 범위 밖 — 봇은 주문표만 만들고 실행은 항상 사람이 한다(작업지시 3절).

실행: python -m backend.bot  (TELEGRAM_BOT_TOKEN·TELEGRAM_CHAT_ID 필수)
"""
import glob
import math
import os
import secrets
import shutil
import tempfile
import time
import traceback

from backend import db, market, notify, notion, rules, vision
from backend import reply as reply_mod

# /help 와 자유 질문 지식원이 같은 원본을 쓰게 reply 쪽 상수를 사용.
USAGE = reply_mod.USAGE

_KIND_KR = {"monthly": "월간 루틴", "entry": "진입기 주간", "december": "12월 리밸런싱",
            "withdraw": "생계 인출"}

# 단일 사용자 봇이라 명령→사진 사이 문맥은 메모리로 충분(확인 게이트는 DB pending).
_session = {"next_kind": "monthly", "args": {}, "await_input": None}


def _send(text: str, reply_markup: dict | None = None) -> None:
    """공통 발신 — 위기 모드면 모든 회신 상단에 고정 문구(작업지시 5절)."""
    if db.get_state()["crisis_active"]:
        text = reply_mod.CRISIS_BANNER + "\n\n" + text
    notify.send(text, reply_markup=reply_markup)


def _reset_session() -> None:
    _session.update(next_kind="monthly", args={}, await_input=None)


# ---------- 업데이트 라우팅 ----------
def handle_update(u: dict) -> None:
    cb = u.get("callback_query")
    if cb:
        # 화이트리스트 밖 발신자는 무응답(보안 7절)
        if str(cb["from"]["id"]) != notify.owner_chat_id():
            return
        handle_callback(cb)
        return
    msg = u.get("message")
    if not msg or str(msg["chat"]["id"]) != notify.owner_chat_id():
        return
    if "photo" in msg:
        handle_photo(msg)
        return
    text = (msg.get("text") or "").strip()
    if not text:
        return
    if text.startswith("/"):
        handle_command(text)
    else:
        handle_text(text)


# ---------- 명령어 ----------
def handle_command(text: str) -> None:
    cmd, *args = text.split()
    if cmd in ("/start", "/help"):
        _send(USAGE)
    elif cmd == "/monthly":
        _session.update(next_kind="monthly", args={}, await_input=None)
        _send("월간 루틴 — 잔고 스크린샷을 보내주세요.")
    elif cmd == "/entry":
        if db.get_state()["phase"] != "ENTRY":
            _send("진입기(ENTRY)가 아닙니다. /phase ENTRY 로 전환 후 사용하세요.")
            return
        _session.update(next_kind="entry", args={}, await_input=None)
        _send(f"진입기 {db.get_state()['entry_week']}주차 — 잔고 스크린샷을 보내주세요.")
    elif cmd == "/december":
        _session.update(next_kind="december", args={}, await_input="realized_krw")
        _send("올해 실현손익 합계를 원 단위 숫자로 입력해주세요 (예: 1200000, 손실이면 -300000).")
    elif cmd == "/withdraw":
        krw = _parse_krw(args[0]) if args else None
        if krw is None or krw <= 0:
            _send("사용법: /withdraw <원화금액>  (예: /withdraw 3000000 — 양수만)")
            return
        _session.update(next_kind="withdraw", args={"need_krw": krw}, await_input=None)
        _send(f"생계 인출 {krw:,.0f}원 — 정상 절차입니다. 잔고 스크린샷을 보내주세요.")
    elif cmd == "/log":
        logs = db.recent_logs(10)
        _send("\n".join(db.format_log(r) for r in logs) if logs else "기록이 없습니다.")
    elif cmd == "/newchat":
        reply_mod.reset_chat_session()
        _send("대화를 초기화했습니다. 다음 질문부터 새 대화로 시작합니다.")
    elif cmd == "/setday":
        day = int(args[0]) if args and args[0].isdigit() else None
        if day is None or not 1 <= day <= 31:
            _send("사용법: /setday <일>  (1~31)")
            return
        db.update_state(monthly_day=day)
        _send(f"적립일을 매월 {day}일로 설정했습니다."
              + (" (해당 일이 없는 달은 말일에 알립니다)" if day >= 29 else ""))
    elif cmd == "/phase":
        phase = args[0].upper() if args else ""
        if phase not in ("SETUP", "ENTRY", "STEADY"):
            _send("사용법: /phase <SETUP|ENTRY|STEADY>\n"
                  "SETUP=가동 전 · ENTRY=SGOV→TQQQ 5주 분할 진입기 · STEADY=정상 운용(TQQQ/JEPI)")
            return
        updates = {"phase": phase}
        if phase == "ENTRY":
            updates["entry_week"] = 1
        db.update_state(**updates)
        _send(f"단계를 {phase} 로 전환했습니다.")
    else:
        _send("알 수 없는 명령입니다.\n\n" + USAGE)


def _parse_krw(raw: str) -> float | None:
    try:
        value = float(raw.replace(",", "").replace("원", ""))
    except ValueError:
        return None
    return value if math.isfinite(value) else None


# ---------- 일반 텍스트: 대기 입력 or 자유 질문 ----------
def handle_text(text: str) -> None:
    if _session["await_input"] == "realized_krw":
        krw = _parse_krw(text)
        if krw is None:
            _send("숫자로 입력해주세요 (예: 1200000, 손실이면 -300000).")
            return
        _session["args"]["realized_krw"] = krw
        _session["await_input"] = None
        _send(f"실현손익 {krw:+,.0f}원 확인. 이제 잔고 스크린샷을 보내주세요.")
        return
    # 자유 질문 — 규칙서를 지식원으로 클로드에 위임(가드레일 포함, 작업지시 4-4)
    _send("규칙서 기준으로 확인 중입니다… (수십 초)")
    _send(reply_mod.answer_freeform(text))


# ---------- 사진: 추출 → 확인 게이트 ----------
def handle_photo(msg: dict) -> None:
    state = db.get_state()
    if state["phase"] == "SETUP":
        _send("아직 가동 전(SETUP)입니다. /phase ENTRY 또는 /phase STEADY 로 전환하고 "
              "/setday <일> 로 적립일을 설정한 뒤 다시 보내주세요.")
        return
    kind = _session["next_kind"]
    if kind == "december" and "realized_krw" not in _session["args"]:
        _send("/december 는 실현손익 합계 입력이 먼저입니다. /december 를 다시 실행해주세요.")
        return

    _send("스크린샷에서 수치를 추출하는 중입니다… (수십 초)")
    tmp_dir = tempfile.mkdtemp(prefix="rulebot_")
    try:
        path = notify.download_photo(msg["photo"][-1]["file_id"], tmp_dir)
        data = vision.extract(path)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)  # 수신 이미지는 처리 후 즉시 삭제(보안 7절)

    retake = vision.needs_retake(data, kind)
    if retake:
        _send("다음 값을 확실히 읽지 못했습니다 — 추측하지 않습니다. 다시 촬영해 보내주세요:\n- "
              + "\n- ".join(retake))
        return

    tickers = [p["ticker"] for p in data["positions"]]
    mismatch = rules.portfolio_mismatch(tickers, state["phase"])
    if mismatch:
        _send(f"⛔ 규칙서 포트폴리오(TQQQ/JEPI{'/SGOV' if state['phase'] == 'ENTRY' else ''})와 "
              f"불일치하는 종목: {', '.join(mismatch)}\n계산하지 않고 중단합니다.")
        return

    md = _gather_market(state["phase"])
    # 위기 모드는 점검 시점(종가 하락률 확인)에 갱신 — 게이트 회신부터 배너 반영
    db.update_state(crisis_active=rules.crisis_update(md["ndx"]["drawdown"], state["crisis_active"]))

    # nonce 로 게이트와 콜백을 바인딩 — 옛 게이트 메시지의 버튼이 새 pending 을 승인하지 못하게.
    nonce = secrets.token_hex(8)
    db.set_pending(kind, {"extracted": data, "market": md,
                          "args": dict(_session["args"]), "nonce": nonce})
    _send(_gate_summary(kind, data, md), reply_markup={
        "inline_keyboard": [[{"text": "✅ 맞음", "callback_data": f"confirm:{nonce}"},
                             {"text": "❌ 다시", "callback_data": f"retry:{nonce}"}]]})


def _gather_market(phase: str) -> dict:
    tickers = ["TQQQ", "JEPI"] + (["SGOV"] if phase == "ENTRY" else [])
    return {
        "ndx": market.ndx_drawdown(),
        "prices": {t: market.last_price(t) for t in tickers},
        "fx": market.usdkrw(),
    }


def _gate_summary(kind: str, data: dict, md: dict) -> str:
    nd = md["ndx"]
    lines = [f"[확인 게이트 — {_KIND_KR[kind]}] 추출·조회 값을 확인해주세요.", ""]
    lines.append("보유 종목 (스크린샷 추출)")
    for p in data["positions"]:
        pnl = f", 평가손익 {p['pnl_krw']:+,.0f}원" if p.get("pnl_krw") is not None else ""
        lines.append(f"- {p['ticker']}: {p['shares']}주{pnl}")
    cash_usd = f"${data['cash_usd']:,.2f}" if data.get("cash_usd") is not None else "못 읽음"
    cash_krw = f"{data['cash_krw']:,.0f}원" if data.get("cash_krw") is not None else "못 읽음"
    lines.append(f"- 예수금: {cash_usd} / {cash_krw}")
    lines.append("")
    lines.append("시장 데이터 (서버 조회)")
    lines.append(f"- 나스닥100 종가 {nd['latest_close']:,.2f} ({nd['latest_date']}) · "
                 f"2년 최고 종가 {nd['peak_close']:,.2f} · 하락률 {nd['drawdown']:.1%}")
    lines.append("- 현재가: " + " · ".join(f"{t} ${p:,.2f}" for t, p in md["prices"].items()))
    lines.append(f"- 환율 {md['fx']:,.1f}원/$")
    lines.append("")
    lines.append("숫자 하나가 틀리면 이후 계산이 전부 오염됩니다.")
    return "\n".join(lines)


# ---------- 콜백: 게이트 통과 → 판정 ----------
def handle_callback(cb: dict) -> None:
    notify.call("answerCallbackQuery", callback_query_id=cb["id"])
    action, _, token = (cb.get("data") or "").partition(":")
    pending = db.get_pending()
    if pending is None:
        _send("대기 중인 확인 건이 없습니다. 사진을 다시 보내주세요.")
        return
    kind, payload = pending
    if payload.get("nonce") != token:
        _send("이 확인 건은 만료되었습니다. 최신 게이트 메시지의 버튼을 사용해주세요.")
        return
    if action == "retry":
        db.clear_pending()
        _send("취소했습니다. 다시 촬영해 보내주세요.")
        return
    if action != "confirm":
        return

    result = compute_judgment(kind, payload)
    # 전송 성공을 커밋의 선행 조건으로 — 전송 실패 시 pending 이 남아 같은 ✅ 로
    # 재시도하면 동일 payload 로 재계산되므로 가속 주문표가 유실되지 않는다.
    _send(result["text"])
    _commit(result)
    db.clear_pending()
    if result["intercepted"]:
        # 가속이 원래 용건을 가로챈 경우 — 다음 사진이 원래 용건으로 이어지게 세션 보존
        _session.update(next_kind=kind, args=dict(payload.get("args", {})), await_input=None)
    else:
        _reset_session()


def _commit(result: dict) -> None:
    """상태·로그 반영(+노션). 회신 전송 성공 후에만 호출한다."""
    if result["updates"]:
        db.update_state(**result["updates"])
    for log in result["logs"]:
        row = db.append_log(**log)
        notion.sync_log(row)


def run_judgment(kind: str, p: dict) -> str:
    """계산 + 커밋(전송과 무관한 단순 경로·테스트용)."""
    result = compute_judgment(kind, p)
    _commit(result)
    return result["text"]


def compute_judgment(kind: str, p: dict) -> dict:
    """판정 계산만 수행 — DB 쓰기 없음. 반환: {text, updates, logs, intercepted}."""
    state = db.get_state()
    data, md, args = p["extracted"], p["market"], p.get("args", {})
    dd = md["ndx"]["drawdown"]
    prices = md["prices"]
    year = int(db.today_kst()[:4])
    shares = {pos["ticker"]: pos["shares"] for pos in data["positions"]}
    pnl = {pos["ticker"]: pos.get("pnl_krw") for pos in data["positions"]}
    snap = rules.Snapshot(
        tqqq_shares=shares.get("TQQQ", 0), jepi_shares=shares.get("JEPI", 0),
        tqqq_price=prices["TQQQ"], jepi_price=prices["JEPI"])

    updates: dict = {"crisis_active": rules.crisis_update(dd, state["crisis_active"])}
    updates.update(rules.episode_reset_updates(
        dd, state["episode_active"], state["tier1_fired"], state["tier2_fired"]))
    tier1 = updates.get("tier1_fired", state["tier1_fired"])
    tier2 = updates.get("tier2_fired", state["tier2_fired"])

    # B. 가속조항은 판정일마다 우선 점검하되, 생계 인출(E)은 '즉시 협조'가 규칙보다
    # 우선이라 가로채지 않는다(가속 플래그도 소진하지 않음 — 다음 점검일에 발동).
    accel = None if kind == "withdraw" else rules.judge_accel(snap, dd, tier1, tier2, year)
    if accel is not None:
        updates.update(accel.state_updates)
        updates["carry_usd"] = state["carry_usd"] + accel.carry_delta_usd
        text, log = _render(accel, dd, updates, memo="가속조항 우선")
        text += "\n\n가속 주문 체결 후 잔고를 다시 캡처해 보내면 원래 용건" \
                f"({_KIND_KR[kind]})을 이어서 판정합니다."
        return {"text": text, "updates": updates, "logs": [log], "intercepted": True}

    if kind == "monthly":
        # 예수금(달러)에는 환전분·분배금·이월 잔돈이 모두 담겨 있어 그대로 가용액으로 쓴다.
        # (null 예수금은 needs_retake 가 게이트 전에 차단 — 여기 도달하면 실측값)
        j = rules.judge_monthly(snap, data["cash_usd"])
        updates["carry_usd"] = j.carry_delta_usd
        text, log = _render(j, dd, updates, memo="월간 루틴")
        return {"text": text, "updates": updates, "logs": [log], "intercepted": False}

    if kind == "entry":
        j = rules.judge_entry(shares.get("SGOV", 0), state["entry_week"],
                              prices.get("SGOV", 0.0), prices["TQQQ"])
        updates.update(j.state_updates)
        updates["carry_usd"] = state["carry_usd"] + j.carry_delta_usd
        text, log = _render(j, dd, updates, memo="진입기")
        if j.state_updates.get("phase") == "STEADY":
            text += "\n\n진입 5회 완료 — STEADY 로 자동 전환했습니다."
        return {"text": text, "updates": updates, "logs": [log], "intercepted": False}

    if kind == "december":
        j = rules.judge_december(snap, year, state["skip_december_year"])
        updates["carry_usd"] = state["carry_usd"] + j.carry_delta_usd
        text, log = _render(j, dd, updates, memo="12월 정기")
        logs = [log]
        if j.action != "12월 리밸런싱 스킵":
            gains = [(t, pnl[t] / shares[t], shares[t]) for t in ("TQQQ", "JEPI")
                     if shares.get(t) and pnl.get(t) is not None and pnl[t] > 0]
            losses = [(t, pnl[t] / shares[t], shares[t]) for t in ("TQQQ", "JEPI")
                      if shares.get(t) and pnl.get(t) is not None and pnl[t] < 0]
            h = rules.judge_harvest(args["realized_krw"], gains, losses)
            h_text, h_weights = reply_mod.render_judgment(h, dd)
            if h.orders:
                h_log = {"action": h.action, "drawdown": f"{dd:.1%}", "weights": h_weights,
                         "memo": "공제·손실 수확", "date": db.today_kst()}
                logs.append(h_log)
                h_text += "\n\n⑤ 기록: " + db.format_log(h_log)
            text += "\n\n──── 공제 수확 ────\n\n" + h_text + \
                "\n\n12월 말일이 임박했다면 결제일(T+1)의 연내 귀속 여부를 확인하세요."
        return {"text": text, "updates": updates, "logs": logs, "intercepted": False}

    if kind == "withdraw":
        gain_per = {t: (pnl[t] / shares[t]) if shares.get(t) and pnl.get(t) is not None else None
                    for t in ("TQQQ", "JEPI")}
        j = rules.judge_withdraw(args["need_krw"], md["fx"], snap,
                                 tqqq_gain_krw_per_share=gain_per["TQQQ"],
                                 jepi_gain_krw_per_share=gain_per["JEPI"])
        text, log = _render(j, dd, updates, memo="생계 인출 — 정상 절차")
        if gain_per["TQQQ"] is None and gain_per["JEPI"] is None:
            text += "\n\n(평가손익을 읽지 못해 예상 실현손익·세금 보고는 생략했습니다.)"
        return {"text": text, "updates": updates, "logs": [log], "intercepted": False}

    raise ValueError(f"알 수 없는 판정 종류: {kind}")


def _render(j: rules.Judgment, dd: float, updates: dict, memo: str) -> tuple[str, dict]:
    """회신 본문과 로그 행(dict)을 만든다 — DB 쓰기는 _commit 의 몫."""
    text, weights = reply_mod.render_judgment(j, dd)
    log = {"action": j.action, "drawdown": f"{dd:.1%}", "weights": weights,
           "memo": memo, "date": db.today_kst()}
    return text + "\n\n⑤ 기록: " + db.format_log(log), log


# ---------- 메인 루프 ----------
def main() -> None:
    db.init_db()
    # 강제 종료로 남은 스크린샷 임시 폴더 청소(보안 7절 보완)
    for stale in glob.glob(os.path.join(tempfile.gettempdir(), "rulebot_*")):
        shutil.rmtree(stale, ignore_errors=True)
    print("규칙서 집행봇 시작 — 롱폴링")
    offset = 0
    while True:
        try:
            updates = notify.call("getUpdates", http_timeout=60, offset=offset, timeout=50)
        except Exception as e:
            print(f"getUpdates 실패(5초 후 재시도): {e}")
            time.sleep(5)
            continue
        for u in updates:
            offset = u["update_id"] + 1
            try:
                handle_update(u)
            except Exception as e:
                traceback.print_exc()
                try:
                    _send(f"처리 중 오류가 났습니다: {e}\n다시 시도해주세요.")
                except Exception:
                    pass


if __name__ == "__main__":
    main()
