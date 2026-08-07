"""Claude Code 헤드리스 호출(claude -p) — 구독 인증 강제 공용 러너.

ANTHROPIC_API_KEY/AUTH_TOKEN 을 자식 프로세스 환경에서 제거해 '구독 인증'을 강제한다
(= 실수로 API 종량 과금되는 것을 코드 차원에서 차단).
"""
import glob
import json
import os
import subprocess

# claude 실행 파일 경로(호스트마다 다를 수 있어 환경변수로 덮어쓸 수 있게).
CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "claude")


def _remove_session_transcript(session_id: str | None) -> None:
    """세션 트랜스크립트(JSONL) 삭제 — Read 로 읽힌 스크린샷 사본이 ~/.claude 에
    남으면 '이미지는 처리 후 즉시 삭제'(보안 7절)가 깨지기 때문."""
    if not session_id:
        return
    base = os.path.join(os.path.expanduser("~"), ".claude", "projects")
    for path in glob.glob(os.path.join(base, "*", f"{session_id}.jsonl")):
        try:
            os.remove(path)
        except OSError:
            pass


def build_cmd(prompt: str, allowed_tools: tuple[str, ...] = (),
              system_prompt: str | None = None) -> list[str]:
    cmd = [CLAUDE_BIN, "-p", prompt, "--output-format", "json"]
    if allowed_tools:
        cmd += ["--allowedTools", ",".join(allowed_tools)]
    if system_prompt:
        # 대화 기억은 CLI 세션이 아니라 봇이 소유한 채팅방 기록(DB)을 시스템 프롬프트로
        # 주입해 유지한다 — 명령어·판정까지 전부 기억에 포함시키기 위함.
        cmd += ["--append-system-prompt", system_prompt]
    return cmd


def run_claude(prompt: str, allowed_tools: tuple[str, ...] = (), timeout: int = 600,
               cleanup_session: bool = False, system_prompt: str | None = None):
    env = dict(os.environ)
    dropped = [k for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")
               if env.pop(k, None) is not None]
    if dropped:
        print(f"구독 인증 강제: 자식 프로세스에서 {', '.join(dropped)} 제외(API 과금 차단)")

    cmd = build_cmd(prompt, allowed_tools, system_prompt)
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          env=env, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"claude 실행 실패(exit {proc.returncode}): {proc.stderr[:500]}")

    envelope = json.loads(proc.stdout)
    if cleanup_session:
        _remove_session_transcript(envelope.get("session_id"))
    if envelope.get("is_error"):
        raise RuntimeError(f"claude 응답 오류: {str(envelope)[:500]}")
    result = (envelope.get("result") or "").strip()
    if not result:
        raise RuntimeError("claude 응답이 비어 있음")
    return result


def parse_json_obj(text: str) -> dict:
    """결과 텍스트에서 JSON 객체만 추출(펜스·잡텍스트 무시). 실패 시 빈 dict."""
    if "{" not in text or "}" not in text:
        return {}
    raw = text[text.find("{"):text.rfind("}") + 1]
    try:
        obj = json.loads(raw)
    except Exception as e:
        print(f"JSON 파싱 실패(무시): {e}")
        return {}
    return obj if isinstance(obj, dict) else {}
