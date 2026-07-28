FROM node:22-bookworm-slim AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
ARG VITE_API_BASE_URL=/
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN npm run build

FROM node:22-bookworm-slim AS remotion-builder

WORKDIR /app/remotion
COPY remotion/package*.json ./
RUN npm ci --no-audit --no-fund
COPY remotion/ ./
RUN npm run typecheck \
    && npm test \
    && npm run browser:ensure

FROM python:3.11-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/backend \
    APP_ENV=production \
    DATABASE_URL=sqlite:////app/data/doodlestory.db \
    DOODLESTORY_STORAGE_ROOT=/app/data/storage \
    DOODLESTORY_FRONTEND_DIST=/app/frontend/dist \
    REMOTION_PROJECT_DIR=/app/remotion \
    REMOTION_NODE_EXECUTABLE=/usr/local/bin/node \
    FRONTEND_ORIGIN=

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        ca-certificates \
        fonts-noto-cjk \
        libasound2 \
        libatk1.0-0 \
        libatspi2.0-0 \
        libcairo2 \
        libcups2 \
        libdbus-1-3 \
        libgbm1 \
        libgomp1 \
        libnss3 \
        libpangocairo-1.0-0 \
        libx11-xcb1 \
        libxcomposite1 \
        libxdamage1 \
        libxfixes3 \
        libxkbcommon0 \
        libxrandr2 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY alembic.ini /app/alembic.ini
COPY backend /app/backend
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist
COPY --from=remotion-builder /usr/local/bin/node /usr/local/bin/node
COPY --from=remotion-builder /app/remotion /app/remotion
COPY scripts/docker-entrypoint.sh /app/scripts/docker-entrypoint.sh

RUN chmod +x /app/scripts/docker-entrypoint.sh \
    && mkdir -p /app/data/storage

EXPOSE 8000

ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
