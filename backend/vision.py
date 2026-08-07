"""스크린샷 수치 추출 — Claude 비전(Read 도구로 이미지 파일을 읽게 함).

흐릿하거나 잘린 값은 추측하지 않고 null 처리한다(재촬영 요청은 봇의 몫 — 작업지시 4-1).
"""
from backend.claude_runner import run_claude, parse_json_obj

PROMPT_TMPL = """당신은 증권앱(토스증권) 잔고 스크린샷에서 수치를 추출하는 도구입니다.
Read 도구로 다음 이미지 파일을 읽으세요: {path}

[추출 항목]
- positions: 보유 종목마다 {{"ticker": 미국 티커 대문자 또는 null, "name_raw": 화면 표기 종목명,
  "shares": 보유 주수(정수) 또는 null, "value_usd": 평가금액 USD 또는 null,
  "pnl_krw": 원화 평가손익(± 정수) 또는 null}}
- cash_usd: 달러 예수금 또는 null
- cash_krw: 원화 예수금 또는 null

[규칙]
- 흐릿하거나 잘려서 확실하지 않은 숫자는 절대 추측하지 말고 null 로 두고,
  unclear 배열에 '무엇이 왜 불확실한지'를 한 줄씩 적으세요.
- 화면에 없는 항목도 null. 종목명이 한글이어도 티커가 화면에 있으면 그 티커를 쓰고,
  티커가 안 보이면 ticker 는 null 로 두세요(임의 추정 금지).
- 원화/달러 표기를 혼동하지 마세요(₩, $ 기호와 자릿수로 판별).

[출력 — 순수 JSON 객체 하나만, 마크다운/설명 없이]
{{"positions": [...], "cash_usd": ..., "cash_krw": ..., "unclear": ["..."]}}"""


def extract(image_path: str) -> dict:
    # cleanup_session: 스크린샷이 claude 세션 트랜스크립트에 사본으로 남지 않게 즉시 삭제.
    out = run_claude(PROMPT_TMPL.format(path=image_path), allowed_tools=("Read",),
                     timeout=300, cleanup_session=True)
    data = parse_json_obj(out)
    if not data or "positions" not in data:
        raise RuntimeError("스크린샷 추출 결과 파싱 실패")
    data.setdefault("cash_usd", None)
    data.setdefault("cash_krw", None)
    data.setdefault("unclear", [])
    return data


def needs_retake(data: dict, kind: str = "monthly") -> list[str]:
    """계산에 필수인 값이 비면 재촬영 사유 목록 반환(추측 금지 — '못 읽음'을 0이나
    '없음'으로 단정하지 않는다). 필수 항목은 판정 종류(kind)에 따라 다르다."""
    reasons = list(data.get("unclear") or [])
    for p in data.get("positions", []):
        if p.get("ticker") is None:
            reasons.append(f"종목 '{p.get('name_raw', '?')}'의 티커를 식별하지 못함")
        if p.get("shares") is None:
            reasons.append(f"{p.get('ticker') or p.get('name_raw', '?')} 보유 주수를 읽지 못함")
        if kind == "december" and p.get("shares") is not None and p.get("pnl_krw") is None:
            reasons.append(f"{p.get('ticker') or p.get('name_raw', '?')} 평가손익을 읽지 못함 "
                           "— 공제·손실 수확 판정에 필수")
    if kind == "monthly" and data.get("cash_usd") is None:
        reasons.append("달러 예수금을 읽지 못함 — 월간 적립 판정에 필수")
    return reasons
