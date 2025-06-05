FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gpsd \
    gpsd-clients \
    python3-gps \
    python3-serial \
    udev \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directory for GPS device
RUN mkdir -p /dev/gps

# Create data directory for SQLite
RUN mkdir -p /data/gps

# Set environment variables
ENV GPS_DEVICE=/dev/ttyUSB0
ENV GPS_BAUD=9600
ENV GPSD_HOST=localhost
ENV GPSD_PORT=2947
ENV NODE_ID=""
ENV DB_PATH=/data/gps/gps_cache.db

# Add udev rules for GPS devices
COPY gps.rules /etc/udev/rules.d/99-gps.rules

# Add startup script
COPY start.sh /start.sh
RUN chmod +x /start.sh

# Expose gpsd port
EXPOSE 2947

# Start gpsd and application
CMD ["/start.sh"] 