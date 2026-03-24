# ── Stage 1: Build frontend ───────────────────────────────────────────────
FROM node:22-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --ignore-scripts 2>/dev/null || npm install
COPY frontend/ ./
RUN npx quasar build

# ── Stage 2: Python backend ──────────────────────────────────────────────
FROM python:3.12-slim AS backend

# System deps for audio processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e ".[dev]" 2>/dev/null || pip install --no-cache-dir .

# Copy backend source
COPY api/ api/
COPY config/ config/
COPY db/ db/
COPY mcp_servers/ mcp_servers/
COPY mt/ mt/
COPY orchestrator/ orchestrator/
COPY postprocessor/ postprocessor/
COPY quality/ quality/
COPY scripts/ scripts/
COPY tests/ tests/
COPY .env.example .env.example

# Copy built frontend
COPY --from=frontend-build /app/frontend/dist/spa /app/static

# Create data directories
RUN mkdir -p /app/data/audio /app/data/output /app/data/providers

# Environment
ENV PYTHONUNBUFFERED=1
ENV STORAGE_ROOT=/app/data
ENV CORS_ORIGINS=*

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
