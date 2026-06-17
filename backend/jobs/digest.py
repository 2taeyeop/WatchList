"""① 개장 전 뉴스·신호 다이제스트 (Claude Code 헤드리스 + 구독 인증).

Anthropic API 키 대신 Claude Code(`claude -p`)를 '구독 인증'으로 호출해 다이제스트를
생성한다. 웹검색은 Claude Code 내장 WebSearch 도구가 담당. → 별도 Anthropic API 종량
과금 없이 Claude 구독(Max 등) 한도에서 차감된다. 미국 개장 약 30분 전(예: 09:00 ET)에 실행.

필요:
- Claude Code 설치 + 구독 인증: `claude setup-token` 으로 발급한 CLAUDE_CODE_OAUTH_TOKEN,
  또는 호스트에 이미 `claude` 로그인이 되어 있을 것.
- TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID.
- ⚠️ ANTHROPIC_API_KEY 는 두지 말 것. 설정돼 있으면 Claude Code 가 구독보다 API 키를
  우선해 종량 과금되므로, 아래 run_claude 가 자식 프로세스 환경에서 강제로 제외한다.
"""
import json
import os
import subprocess

from backend import db
from backend.notify import send_telegram

# claude 실행 파일 경로(호스트마다 다를 수 있어 환경변수로 덮어쓸 수 있게).
CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "claude")
# 본문과 구조화 신호 JSON 을 가르는 구분자.
_SIGNAL_DELIM = "===SIGNAL_JSON==="

PROMPT = """당신은 내 반도체·레버리지 ETF 투자 모니터링 어시스턴트입니다.
미국 증시 개장 전에, 어젯밤 미국장 마감(4 PM ET) 이후부터 오늘 프리마켓까지의
정보를 웹에서 검색해 종합하고, 한국어로 간결한 '개장 전 다이제스트'를 작성하세요.
나는 이걸 보고 개장(또는 개장 +30분)에 정규장에서 진입·관리를 판단합니다.

[내 상황/맥락 — 총평에 반영]
- 나는 공격적 성장 투자자. QLD·SSO·SMH(레버리지)와 매월 ISA 2배 나스닥 보유/적립.
- 2026년 8월에 약 1,500만원을 일괄(또는 분할) 진입 예정 → 시장 과열도·매크로가
  진입 판단에 직접 영향.
- 디리스킹 규칙: capex 감액 / 메모리 가격 하락 전환 / SMH 200일선 이탈 중
  2개 이상이면 QLD·SMH부터 현금·SSO로 축소.
- 진입 신호 규칙: 신호 양호=일괄 / 1개 경고=절반 / 2개 이상=대기.
- 감정·헤드라인이 아니라 '확인된 신호 변화'가 행동을 정하게 할 것.

[모니터링 대상 — 중요도 순]
1. 하이퍼스케일러 capex 가이던스(MS·구글·아마존·메타): 데이터센터·AI 투자
   증액/감액. 분기 실적 시즌 특히 주목.
2. 메모리 고정거래가격(TrendForce DRAM·HBM·NAND): 상승/횡보/하락(전분기 대비).
3. SMH 가격과 200일 이동평균선: 200일선 위/아래, 이격도(과열 여부).
4. TSMC 월간 매출(매월 10일경): 전년동월·전월 대비.
5. Fed 통화정책·금리 전망(CME FedWatch): 인하/인상 기대 변화.
6. 어젯밤~오늘 반도체·AI·매크로 주요 헤드라인(실적·가이던스·지표 서프라이즈).

[작성 형식]
- 맨 위 "오늘 핵심 변화" 2~3줄 요약.
- 신호 항목별: 최신 수치/뉴스 + 직전 대비 변화 + 한 줄 코멘트 + 출처.
- "디리스킹 신호등": 🟢/🟡/🔴 + 근거 한 줄.
  (capex 감액·메모리 하락 전환·SMH 200일선 이탈을 '경고'로 간주.)
- 변화 없는 항목은 "변화 없음"으로 짧게.

[마지막 — 총평 코멘트, 반드시 포함]
- 오늘 신호를 한 문장으로 종합.
- '신호'와 '소음' 구분: 큰 단일 급락/'버블' 헤드라인이 핵심 3신호를 실제로
  꺾었는지, 회복된 노이즈였는지 명시.
- '수준'이 아니라 '변화'(어제 대비)에 초점.
- 두 질문 분리: ① 디리스킹해야 하나(신호등) ② 오늘/8월 진입해도 되나(과열·밸류).
- 경계 요인이 쌓이면 '디리스킹 계획 장전 유지' 환기.
- 마지막에 '한 줄 결론'.

[주의] 사실·데이터만, 매수/매도 권유 금지. 수치엔 출처·날짜. 텔레그램에 보낼
것이므로 표·과한 마크다운 없이 줄글+불릿으로 간결하게.
"""

# 본문 뒤에 대시보드용 구조화 신호를 같은 호출에서 함께 받기 위한 출력 규약.
OUTPUT_SPEC = f"""

[출력 형식 — 반드시 지킬 것]
1) 먼저 위 지침대로 '개장 전 다이제스트' 본문을 한국어 줄글+불릿으로 작성한다(텔레그램 발송용).
2) 본문이 끝나면 정확히 다음 한 줄만 출력한다: {_SIGNAL_DELIM}
3) 마지막으로 아래 스키마의 JSON 객체 '하나만' 출력한다(마크다운 펜스/설명 없이, 순수 JSON):
{{"signal_light": "green|yellow|red",
  "indicators": [{{"name": "지표명(예: SMH 200일선)", "status": "ok|caution|alert|na",
                   "value": "최신 수치", "change": "직전 대비 변화", "comment": "한 줄", "source": "출처"}}],
  "conclusion": "한 줄 결론"}}
신호등 기준: 경고(capex 감액·메모리 하락 전환·SMH 200일선 이탈) 2개 이상=red, 1개=yellow, 없음=green.
indicators 는 위 모니터링 대상 5개(capex·메모리·SMH 200일선·TSMC·Fed)를 각각 1개 항목으로 채운다.
"""


def build_prompt() -> str:
    return PROMPT + OUTPUT_SPEC


def run_claude(prompt: str, timeout: int = 600) -> str:
    """claude -p 를 구독 인증으로 호출하고 최종 결과 텍스트를 반환.

    ANTHROPIC_API_KEY/AUTH_TOKEN 을 자식 프로세스 환경에서 제거해 '구독 인증'을 강제한다
    (= 실수로 API 종량 과금되는 것을 코드 차원에서 차단)."""
    env = dict(os.environ)
    dropped = [k for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")
               if env.pop(k, None) is not None]
    if dropped:
        print(f"구독 인증 강제: 자식 프로세스에서 {', '.join(dropped)} 제외(API 과금 차단)")

    proc = subprocess.run(
        [CLAUDE_BIN, "-p", prompt,
         "--allowedTools", "WebSearch,WebFetch",
         "--output-format", "json"],
        capture_output=True, text=True, encoding="utf-8", env=env, timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"claude 실행 실패(exit {proc.returncode}): {proc.stderr[:500]}")

    envelope = json.loads(proc.stdout)
    if envelope.get("is_error"):
        raise RuntimeError(f"claude 응답 오류: {str(envelope)[:500]}")
    result = (envelope.get("result") or "").strip()
    if not result:
        raise RuntimeError("claude 응답이 비어 있음")
    return result


def parse_output(text: str) -> tuple[str, dict]:
    """결과 텍스트를 (본문 prose, 구조화 신호 dict)로 분리. 신호 파싱 실패해도 본문은 보존."""
    default_sig = {"signal_light": "unknown", "indicators": [], "conclusion": ""}
    if _SIGNAL_DELIM in text:
        prose, _, tail = text.partition(_SIGNAL_DELIM)
        prose = prose.strip()
    else:
        prose, tail = text.strip(), ""

    sig = default_sig
    if "{" in tail and "}" in tail:
        raw = tail[tail.find("{"):tail.rfind("}") + 1]  # 펜스·잡텍스트 제거
        try:
            parsed = json.loads(raw)
            sig = {
                "signal_light": parsed.get("signal_light", "unknown"),
                "indicators": parsed.get("indicators", []),
                "conclusion": parsed.get("conclusion", ""),
            }
        except Exception as e:
            print(f"신호 JSON 파싱 실패(무시): {e}")
    return (prose or text.strip()), sig


def main() -> None:
    text = run_claude(build_prompt())
    prose, sig = parse_output(text)
    if not prose:
        prose = "(다이제스트 생성 실패 — 본문이 비어 있습니다.)"

    # 대시보드용 DB 저장(베스트에포트: 실패해도 발송은 계속).
    try:
        db.init_db()
        saved = db.save_digest(
            prose=prose,
            signal_light=sig.get("signal_light", "unknown"),
            indicators=sig.get("indicators", []),
            conclusion=sig.get("conclusion", ""),
        )
        print(f"다이제스트 DB 저장 완료 ({saved}, 신호등={sig.get('signal_light')})")
    except Exception as e:
        print(f"DB 저장 실패(무시): {e}")

    send_telegram(prose)
    print("다이제스트 발송 완료")


if __name__ == "__main__":
    main()
