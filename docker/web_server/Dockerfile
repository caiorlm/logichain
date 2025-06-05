# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories for data persistence
RUN mkdir -p /data/web /data/logs /data/static /data/templates

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    DATA_DIR=/data \
    LOG_LEVEL=INFO \
    WEB_PORT=8080 \
    STATIC_PATH=/data/static \
    TEMPLATE_PATH=/data/templates

# Expose web port
EXPOSE 8080

# Set entrypoint
ENTRYPOINT ["python", "web_server.py"]

# Default command (can be overridden)
CMD ["--host", "0.0.0.0", "--port", "8080"]

# Volume for persistent data
VOLUME ["/data"] 