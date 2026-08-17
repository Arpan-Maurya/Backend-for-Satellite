FROM python:3.11-slim

# Security: run as non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Install dependencies first (cache layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ app/
COPY models/ models/

# No secrets in image
# .env is NOT copied — use environment variables at runtime

# Switch to non-root user
USER appuser

# PORT is set by the deployment platform (e.g. Render)
ENV PORT=8000

EXPOSE ${PORT}

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import httpx; r = httpx.get(f'http://localhost:${PORT}/health'); r.raise_for_status()" || exit 1

# Run with Uvicorn
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 1 --log-level info"]
