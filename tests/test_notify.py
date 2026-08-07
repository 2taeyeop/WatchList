"""텔레그램 메시지 분할 테스트 — 빈 청크·4096 초과 청크가 나오면 전송 전체가 실패한다."""
from backend.notify import _LIMIT, _chunks


def test_short_text_single_chunk():
    assert _chunks("안녕\n하세요") == ["안녕\n하세요\n"]


def test_long_multiline_splits_at_line_boundary():
    lines = ["x" * 100 for _ in range(80)]  # 8,080자
    chunks = _chunks("\n".join(lines))
    assert len(chunks) > 1
    assert all(0 < len(c) <= _LIMIT + 1 for c in chunks)


def test_single_overlong_line_hard_sliced():
    chunks = _chunks("x" * 10_000)  # 개행 없는 장문(자유 질문 클로드 응답 등)
    assert all(c.strip() for c in chunks)          # 빈 청크 없음
    assert all(len(c) <= _LIMIT + 1 for c in chunks)  # 4096 초과 없음
    assert sum(len(c.rstrip("\n")) for c in chunks) == 10_000  # 내용 보존


def test_overlong_line_after_normal_lines():
    chunks = _chunks("머리말\n" + "y" * 5_000 + "\n꼬리말")
    assert all(c.strip() for c in chunks)
    assert all(len(c) <= _LIMIT + 1 for c in chunks)
    assert "머리말" in chunks[0]
    assert "꼬리말" in chunks[-1]
