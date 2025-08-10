FROM python:3.12-slim

WORKDIR /app

RUN pip install uv
COPY pyproject.toml uv.lock* ./
COPY emotibot_relay/ ./emotibot_relay/
RUN uv sync --frozen --no-dev

EXPOSE 8000

CMD ["uv", "run", "emotibot-server"]
