FROM python:3.12-slim

# Install system audio libraries and curl for health check
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create non-root application user
RUN groupadd -r -g 1000 appuser && \
    useradd -r -u 1000 -g appuser -d /app -s /sbin/nologin appuser

# Copy dependency definition and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and documentation
COPY calllens/ ./calllens/
COPY app/ ./app/
COPY Documentation/ ./Documentation/
COPY README.md SOLUTION_PITCH.md ./

# Create data directory and assign ownership
RUN mkdir -p /app/data && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Default environment configuration for shippable container
ENV APP_HOST=0.0.0.0 \
    APP_PORT=8000 \
    DATA_DIR=/app/data \
    ALLOW_LIVE_API=0 \
    PYTHONUNBUFFERED=1

EXPOSE 8000

# Container health monitoring
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
