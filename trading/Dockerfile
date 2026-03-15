FROM python:3.11-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    netcat-openbsd \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Python deps first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Source
COPY . .

ENV PYTHONPATH=/app/scripts
ENV PYTHONUNBUFFERED=1

# Default: keep alive (override in compose)
CMD ["python", "-c", "import time; time.sleep(1e9)"]
