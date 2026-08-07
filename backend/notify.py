"""텔레그램 Bot API 클라이언트 — 봇(수신 루프)과 리마인더(발신)가 공용.

프레임워크 없이 requests 직접 호출(리포 최소 의존성 방침). 4096자 제한이 있어
줄 경계에서 안전하게 나눠 보낸다.
"""
import os

import requests

_LIMIT = 3900  # 4096 한도 - 여유


def _token() -> str:
    return os.environ["TELEGRAM_BOT_TOKEN"]


def owner_chat_id() -> str:
    """화이트리스트 = 소유자 chat_id 하나(보안 7절)."""
    return os.environ["TELEGRAM_CHAT_ID"]


def call(method: str, http_timeout: int = 60, **params):
    """Bot API 호출 후 result 반환. ok=false 면 예외.
    (getUpdates 의 롱폴링 timeout 파라미터와 이름이 겹치지 않게 http_timeout 사용.)"""
    r = requests.post(f"https://api.telegram.org/bot{_token()}/{method}",
                      json=params, timeout=http_timeout)
    r.raise_for_status()
    body = r.json()
    if not body.get("ok"):
        raise RuntimeError(f"텔레그램 {method} 실패: {str(body)[:300]}")
    return body["result"]


def _chunks(text: str) -> list[str]:
    """줄 경계 분할 + 한도 초과 단일 라인은 하드 슬라이스 — 빈 청크·4096 초과 청크 방지."""
    chunks, buf = [], ""
    for line in text.split("\n"):
        while len(line) > _LIMIT:
            if buf.strip():
                chunks.append(buf)
                buf = ""
            chunks.append(line[:_LIMIT])
            line = line[_LIMIT:]
        if len(buf) + len(line) + 1 > _LIMIT:
            if buf.strip():
                chunks.append(buf)
            buf = ""
        buf += line + "\n"
    if buf.strip():
        chunks.append(buf)
    return chunks


def send(text: str, chat_id: str | None = None, reply_markup: dict | None = None) -> None:
    chat_id = chat_id or owner_chat_id()
    chunks = _chunks(text)
    for i, chunk in enumerate(chunks):
        params: dict = {"chat_id": chat_id, "text": chunk, "disable_web_page_preview": True}
        # 인라인 버튼은 마지막 청크에만 붙인다(중복 게이트 방지).
        if reply_markup and i == len(chunks) - 1:
            params["reply_markup"] = reply_markup
        call("sendMessage", **params)


def download_photo(file_id: str, dest_dir: str) -> str:
    """사진 파일을 dest_dir 에 내려받고 로컬 경로 반환. 처리 후 삭제는 호출자 책임(보안 7절)."""
    info = call("getFile", file_id=file_id)
    file_path = info["file_path"]
    url = f"https://api.telegram.org/file/bot{_token()}/{file_path}"
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    os.makedirs(dest_dir, exist_ok=True)
    local = os.path.join(dest_dir, os.path.basename(file_path))
    with open(local, "wb") as f:
        f.write(r.content)
    return local


# 하위 호환 — 리마인더 등 단순 발신용.
def send_telegram(text: str) -> None:
    send(text)
