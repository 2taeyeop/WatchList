"""Telegram 발송 헬퍼.

텔레그램 메시지는 4096자 제한이 있어, 줄 경계에서 안전하게 나눠 보냅니다.
Discord로 바꾸려면 send_discord()를, 이메일이면 SMTP/SendGrid 버전을 쓰면 됩니다.
"""
import os
import requests

_API = "https://api.telegram.org/bot{token}/sendMessage"
_LIMIT = 3900  # 4096 한도 - 여유


def send_telegram(text: str) -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    url = _API.format(token=token)

    chunks, buf = [], ""
    for line in text.split("\n"):
        if len(buf) + len(line) + 1 > _LIMIT:
            chunks.append(buf)
            buf = ""
        buf += line + "\n"
    if buf.strip():
        chunks.append(buf)

    for chunk in chunks:
        r = requests.post(
            url,
            json={
                "chat_id": chat_id,
                "text": chunk,
                "disable_web_page_preview": True,
            },
            timeout=30,
        )
        r.raise_for_status()


# --- 참고: Discord로 바꾸려면 이 함수를 send_telegram 대신 호출 ---
def send_discord(text: str) -> None:
    """DISCORD_WEBHOOK_URL 환경변수에 웹훅 URL을 넣고 사용."""
    url = os.environ["DISCORD_WEBHOOK_URL"]
    for i in range(0, len(text), 1900):  # 디스코드 2000자 한도
        r = requests.post(url, json={"content": text[i : i + 1900]}, timeout=30)
        r.raise_for_status()
