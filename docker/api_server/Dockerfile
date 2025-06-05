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
RUN mkdir -p /data/blockchain /data/logs /data/keys

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    DATA_DIR=/data \
    LOG_LEVEL=INFO \
    API_PORT=5000

# Expose API port
EXPOSE 5000

# Set entrypoint
ENTRYPOINT ["python", "api_server.py"]

# Default command (can be overridden)
CMD ["--host", "0.0.0.0", "--port", "5000"]

# Volume for persistent data
VOLUME ["/data"] 