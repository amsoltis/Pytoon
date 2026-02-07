FROM python:3.11-slim

# System deps for ffmpeg + Pillow
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg libgl1 libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Default: run the API server
CMD ["uvicorn", "pytoon.api_orchestrator.app:app", "--host", "0.0.0.0", "--port", "8080"]
