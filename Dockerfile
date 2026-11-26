# Stage 1: Build static React + TypeScript frontend
FROM node:22-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Production Python 3.12 runtime
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LL_MODE=web \
    LL_DATA_DIR=/data

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.6 /uv /usr/local/bin/uv

COPY pyproject.toml ./
COPY backend/ ./backend/
COPY assets/ ./assets/
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

RUN uv pip install --system --no-cache .

RUN useradd --create-home --shell /bin/bash appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /data /app

USER appuser
VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)" || exit 1

CMD ["uvicorn", "backend.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "127.0.0.1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"]
