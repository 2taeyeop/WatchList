"""노션 로그 동기화(선택) — NOTION_TOKEN·NOTION_DB_ID 가 있으면 기록 로그를 행으로 추가.

없으면 조용히 건너뛴다(로컬 SQLite가 원본, 노션은 사본 — 작업지시 3절).
"""
import os

import requests

_API = "https://api.notion.com/v1/pages"
_VERSION = "2022-06-28"


def sync_log(row: dict) -> None:
    token = os.environ.get("NOTION_TOKEN")
    db_id = os.environ.get("NOTION_DB_ID")
    if not token or not db_id:
        return
    try:
        r = requests.post(
            _API,
            headers={"Authorization": f"Bearer {token}", "Notion-Version": _VERSION},
            json={
                "parent": {"database_id": db_id},
                "properties": {
                    "날짜": {"title": [{"text": {"content": row["date"]}}]},
                    "행동": {"rich_text": [{"text": {"content": row["action"]}}]},
                    "하락률": {"rich_text": [{"text": {"content": row["drawdown"]}}]},
                    "비중": {"rich_text": [{"text": {"content": row["weights"]}}]},
                    "메모": {"rich_text": [{"text": {"content": row["memo"]}}]},
                },
            },
            timeout=30,
        )
        r.raise_for_status()
    except Exception as e:  # 노션 실패가 봇 회신을 막지 않게
        print(f"노션 동기화 실패(무시): {e}")
