// 반등 스캔 사유 → 사람이 읽는 설명. scanner.py 의 실제 판정 로직과 1:1로 맞춤.
export function explainReason(reason: string): string {
  if (reason.includes("200일선"))
    return "주가가 장기 추세선(200일 이동평균)을 다시 위로 돌파 — 하락추세에서 추세가 복원되는 신호.";
  if (reason.includes("50일선"))
    return "중기 추세선(50일 이동평균)을 회복 — 단기 모멘텀이 개선되는 신호.";
  if (reason.includes("RSI"))
    return "RSI가 과매도(30 미만)에서 30 이상으로 반등 — 매도 과열이 풀리며 반등이 시작될 수 있음.";
  if (reason.includes("거래량"))
    return "평균(20일) 대비 1.8배 이상 거래량을 동반한 상승 — 매수세 유입으로 반등 신뢰도가 높음.";
  if (reason.includes("미충족"))
    return "현재 실제 반등 조건은 충족하지 않음(미리보기용 표시).";
  if (reason.includes("샘플") || reason.includes("미리보기"))
    return "화면 미리보기용 예시 데이터 — 실제 매수 신호가 아님.";
  return "기술적 반등 신호.";
}
