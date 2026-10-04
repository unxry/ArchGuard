FROM python:3.13-slim AS builder
WORKDIR /app
RUN pip install --no-cache-dir uv==0.12.0
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never UV_COMPILE_BYTECODE=1
COPY pyproject.toml uv.lock README.md .python-version ./
COPY src ./src
RUN uv sync --locked --no-editable --no-dev

FROM python:3.13-slim
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system archguard \
    && useradd --system --gid archguard archguard
COPY --from=builder /app/.venv /app/.venv
COPY alembic.ini ./
COPY migrations ./migrations
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER archguard
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"
CMD ["python", "-m", "uvicorn", "archguard.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
