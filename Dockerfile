FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
RUN pip install ".[dev]"

COPY migrations ./migrations
COPY tests ./tests

RUN useradd --create-home --uid 1000 apebot && chown -R apebot:apebot /app
USER apebot

CMD ["python", "-m", "apebot.main"]
