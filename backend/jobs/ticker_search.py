"""종목 검색 분석 — 티커/이름(한국·미국장)을 Claude 웹검색으로 최신 분석.

API(POST /api/search)가 이 함수를 동기 호출한다. Claude Code(claude -p, 구독 인증)
웹검색이므로 **호출당 구독(Max 등) 한도 차감 + 수십 초 지연**. run_claude 재사용 =
별도 Anthropic API 종량 과금 없음. (자동 실행 금지 — 사용자가 화면에서 검색할 때만)
"""
import json

from backend.jobs.digest import run_claude  # 구독 인증 claude -p 호출 재사용

PROMPT_TMPL = """당신은 투자 리서치 어시스턴트입니다. 사용자가 검색한 종목을 웹에서 검색해
최신(최근 1~3일) 정보를 종합하고 한국어로 분석하세요. 한국장/미국장 모두 대상입니다.

[검색어] {query}

먼저 검색어가 어떤 종목인지(티커·정식명·시장)를 확정하세요. 한국 종목이면 6자리 코드와
시장(KOSPI/KOSDAQ), 미국 종목이면 심볼을 씁니다. 그 종목의 최근 주가 흐름과 호재/악재,
촉매, 단기 관점을 웹검색으로 확인해 정리하세요. 과장 없이 사실·출처 기반.

[출력 — 순수 JSON 객체 하나만, 마크다운/설명 없이]
{{"ticker": "심볼 또는 6자리코드", "name": "정식 종목명", "market": "KR|US",
  "price": 최근가(숫자, 모르면 null), "change_pct": 최근 등락률(숫자, 모르면 null),
  "summary": "핵심 요약 2~3줄", "catalyst": "호재/촉매(없으면 빈 문자열)",
  "view": "단기 관점 한 줄", "sentiment": "positive|neutral|negative",
  "sources": ["출처 URL", ...]}}
종목을 특정할 수 없으면 ticker 를 빈 문자열로 두고 summary 에 사유를 적어 JSON 하나만 출력하세요."""


def parse(text: str) -> dict | None:
    """결과 텍스트에서 JSON 객체만 추출."""
    if "{" not in text or "}" not in text:
        return None
    raw = text[text.find("{"):text.rfind("}") + 1]
    try:
        obj = json.loads(raw)
    except Exception as e:
        print(f"검색 JSON 파싱 실패: {e}")
        return None
    return obj if isinstance(obj, dict) else None


def analyze(query: str) -> dict | None:
    """query → Claude 웹검색 분석 dict(or None). 호출당 구독 차감·지연."""
    text = run_claude(PROMPT_TMPL.format(query=query))
    return parse(text)
