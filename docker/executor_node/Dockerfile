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
RUN mkdir -p /data/blockchain /data/logs /data/keys /data/contracts

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    DATA_DIR=/data \
    LOG_LEVEL=INFO \
    EXECUTOR_PORT=7000 \
    P2P_PORT=30303 \
    CONTRACT_DIR=/data/contracts

# Expose ports
EXPOSE 7000 30303

# Set entrypoint
ENTRYPOINT ["python", "executor_node.py"]

# Default command (can be overridden)
CMD ["--host", "0.0.0.0", "--port", "7000", "--p2p-port", "30303"]

# Volume for persistent data
VOLUME ["/data"] 