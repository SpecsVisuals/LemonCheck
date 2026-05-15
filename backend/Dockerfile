# Dockerfile
#
# Production container for LemonCheck FastAPI backend.
# Deployed to Railway. Railway builds this image and runs it.
#
# Multi-stage isn't needed here — the app is small and Railway handles caching.

FROM python:3.11-slim

WORKDIR /app

# Install system deps for lxml (BeautifulSoup HTML parser)
RUN apt-get update && apt-get install -y \
    libxml2-dev \
    libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (layer caching — only re-runs if requirements change)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Railway injects PORT env var; default to 8000 for local docker runs
ENV PORT=8000

EXPOSE $PORT

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port $PORT"]
