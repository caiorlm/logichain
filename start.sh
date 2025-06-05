#!/bin/bash

# Start udev
/lib/systemd/systemd-udevd --daemon

# Wait for GPS device
while [ ! -e "$GPS_DEVICE" ]; do
    echo "Waiting for GPS device at $GPS_DEVICE..."
    sleep 1
done

# Start gpsd if using USB GPS
if [ -e "$GPS_DEVICE" ]; then
    echo "Starting gpsd for device $GPS_DEVICE..."
    gpsd -n -N -D3 $GPS_DEVICE
fi

# Start the application
echo "Starting LogiChain GPS tracking..."
python -m blockchain.core.location.main \
    --node-id "$NODE_ID" \
    --gps-device "$GPS_DEVICE" \
    --gps-baud "$GPS_BAUD" \
    --gpsd-host "$GPSD_HOST" \
    --gpsd-port "$GPSD_PORT" \
    --db-path "$DB_PATH" 