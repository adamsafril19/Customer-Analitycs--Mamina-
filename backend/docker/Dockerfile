# syntax=docker/dockerfile:1

# Dependency stage. This is the expensive layer and should only rebuild when
# requirements.txt changes.
FROM python:3.10-slim AS deps

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
ENV PIP_DEFAULT_TIMEOUT=120 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_RETRIES=10
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir --user --timeout 120 --retries 10 -r requirements.txt


# Runtime stage. Code-only rebuilds should usually start here from cached deps.
FROM python:3.10-slim AS runtime

WORKDIR /app

# Keep HF cache outside copied source and mount it as a volume in compose.
ENV HF_HOME=/app/.cache/huggingface \
    TRANSFORMERS_CACHE=/app/.cache/huggingface/transformers \
    SENTENCE_TRANSFORMERS_HOME=/app/.cache/huggingface/sentence_transformers

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash appuser

COPY --from=deps /root/.local /home/appuser/.local

# Make sure scripts in .local are usable
ENV PATH=/home/appuser/.local/bin:$PATH

# Copy application code
COPY --chown=appuser:appuser . .

# Create directories
RUN mkdir -p /app/logs /app/models /app/.cache/huggingface \
    && chown -R appuser:appuser /app /home/appuser/.local

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/api/health || exit 1

# Default command
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--threads", "2", "run:app"]


# Optional image variant with HF models baked in. Use only for deployment builds
# where a larger image is preferable to first-run model downloads.
FROM runtime AS runtime-preloaded

RUN python -c "from sentence_transformers import SentenceTransformer; from transformers import AutoModelForSequenceClassification, AutoTokenizer; SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'); AutoTokenizer.from_pretrained('Aardiiiiy/indobertweet-base-Indonesian-sentiment-analysis'); AutoModelForSequenceClassification.from_pretrained('Aardiiiiy/indobertweet-base-Indonesian-sentiment-analysis'); print('HF models cached')"
