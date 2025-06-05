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
RUN mkdir -p /data/network /data/logs /data/peers

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    DATA_DIR=/data \
    LOG_LEVEL=INFO \
    P2P_PORT=30303 \
    DISCOVERY_PORT=30304

# Expose P2P and discovery ports
EXPOSE 30303 30304

# Set entrypoint
ENTRYPOINT ["python", "network.py"]

# Default command (can be overridden)
CMD ["--host", "0.0.0.0", "--port", "30303", "--discovery-port", "30304"]

# Volume for persistent data
VOLUME ["/data"] 