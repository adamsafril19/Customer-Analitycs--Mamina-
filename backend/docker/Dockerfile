# Multi-stage build for smaller final image
FROM python:3.10-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
ENV PIP_DEFAULT_TIMEOUT=120 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_RETRIES=10
RUN pip install --no-cache-dir --user --timeout 120 --retries 10 -r requirements.txt


# Final stage
FROM python:3.10-slim

WORKDIR /app

# Cache Hugging Face models in the image to avoid runtime downloads
ENV HF_HOME=/app/.cache/huggingface \
    TRANSFORMERS_CACHE=/app/.cache/huggingface/transformers \
    SENTENCE_TRANSFORMERS_HOME=/app/.cache/huggingface/sentence_transformers

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash appuser

# Copy installed packages from builder
COPY --from=builder /root/.local /home/appuser/.local

# Make sure scripts in .local are usable
ENV PATH=/home/appuser/.local/bin:$PATH

# Copy application code
COPY --chown=appuser:appuser . .


# Create directories
RUN mkdir -p /app/logs /app/models && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Pre-download HF models used by the backend
RUN python - <<'PY'
from sentence_transformers import SentenceTransformer
from transformers import AutoModelForSequenceClassification, AutoTokenizer

SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
AutoTokenizer.from_pretrained("Aardiiiiy/indobertweet-base-Indonesian-sentiment-analysis")
AutoModelForSequenceClassification.from_pretrained(
    "Aardiiiiy/indobertweet-base-Indonesian-sentiment-analysis"
)
print("HF models cached")
PY

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/api/health || exit 1

# Default command
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--threads", "2", "run:app"]
