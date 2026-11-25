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

# Create non-root user and set up application directory permissions
RUN groupadd -g 1001 setu && \
    useradd -u 1001 -g setu -m -s /bin/bash setu && \
    mkdir -p /app/data && \
    chown -R setu:setu /app

# Copy application directories and set ownership
COPY --chown=setu:setu backend/ ./backend/
COPY --chown=setu:setu frontend/ ./frontend/
COPY --chown=setu:setu docs/ ./docs/
COPY --chown=setu:setu models/ ./models/
COPY --chown=setu:setu .env.example .env

# Switch to non-root user
USER setu

# Expose FastAPI service port
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Start Uvicorn application server
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
