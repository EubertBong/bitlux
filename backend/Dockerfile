# Bitlux CRM API -- Render (runtime: docker, dockerContext: ./backend).
#
# Two `uv sync` passes so the dependency layer is cached independently of the
# application code: only the second, near-instant pass re-runs on a code change.
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev

EXPOSE 8000

# Render injects PORT; anything else (local `docker run`) gets 8000.
CMD ["sh", "-c", "uv run --frozen --no-dev uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
