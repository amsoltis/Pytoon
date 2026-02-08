FROM python:3.11-slim

# System deps for ffmpeg + Pillow + curl (healthcheck)
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg libgl1 libglib2.0-0 curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create storage directory
RUN mkdir -p /data/storage

# Expose API port
EXPOSE 8000

# Healthcheck for container orchestrators
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default: run the API server (V2)
CMD ["uvicorn", "pytoon.api_orchestrator.app:app", "--host", "0.0.0.0", "--port", "8000"]
