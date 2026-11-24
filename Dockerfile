# BharatSetu AI: Agentic Digital Public Infrastructure Copilot for MSMEs
FROM python:3.12-slim

# Avoid buffering and bytecode generation
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install system libraries for OpenCV, ReportLab, and image processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency requirements
COPY requirements.txt .

# Install Python packages
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application directories
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY docs/ ./docs/
COPY models/ ./models/
COPY .env.example .env

# Expose FastAPI service port
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Start Uvicorn application server
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
