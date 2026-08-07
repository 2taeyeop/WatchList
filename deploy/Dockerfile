FROM python:3.12-slim

# print 가 도커 로그에 즉시 보이게 stdout 버퍼링 해제
ENV PYTHONUNBUFFERED=1

# claude CLI(node 기반)는 비전 추출·자유 질문에 필수 — 구독 인증은 CLAUDE_CODE_OAUTH_TOKEN 환경변수로.
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g @anthropic-ai/claude-code \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ backend/
COPY prompts/ prompts/

# 롱폴링 봇 — 공개 포트 없음
CMD ["python", "-m", "backend.bot"]
