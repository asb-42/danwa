# Dockerfile.backend — Danwa API server
#
# Build:  docker build -f Dockerfile.backend -t danwa-backend .
# Run:    docker run -p 8000:8000 -e DANWA_JWT_SECRET_KEY=secret danwa-backend

FROM python:3.12-slim AS base

# System dependencies for OCR, TTS, and audio processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-deu \
    tesseract-ocr-eng \
    espeak-ng \
    espeak-ng-data \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev

# Copy application code
COPY backend/ backend/
COPY config/ config/
COPY modules/ modules/
COPY schemas/ schemas/
COPY version ./

# Create data directories
RUN mkdir -p data/logs data/projects data/backups

EXPOSE 8000

# Production: Gunicorn with Uvicorn workers
CMD ["gunicorn", "backend.main:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "4", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "300", \
     "--graceful-timeout", "30", \
     "--keep-alive", "5"]
