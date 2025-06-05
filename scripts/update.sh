#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Function to print colored output
print_status() {
    echo -e "${GREEN}[+]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[-]${NC} $1"
}

# Check if running with sudo/root
if [ "$EUID" -ne 0 ]; then
    print_error "Please run as root (sudo)"
    exit 1
fi

# Stop the service
print_status "Stopping LogiChain service..."
systemctl stop logichain

# Create backup
print_status "Creating backup..."
python3 scripts/backup.py --action create

# Pull latest changes
print_status "Pulling latest changes..."
git pull

# Update Python dependencies
print_status "Updating Python dependencies..."
python3 -m pip install -r requirements.txt --upgrade

# Update Docker images
print_status "Updating Docker images..."
docker-compose pull
docker-compose build --pull

# Check for environment changes
print_status "Checking for environment changes..."
if [ -f config/.env.template.new ]; then
    print_warning "New environment template found"
    print_warning "Please review and merge changes from config/.env.template.new to config/.env.production"
    diff -u config/.env.template config/.env.template.new || true
fi

# Update SSL certificates if expired or near expiry
print_status "Checking SSL certificates..."
CERT_FILE="data/ssl/cert.pem"
if [ -f "$CERT_FILE" ]; then
    # Get expiry date
    EXPIRY=$(openssl x509 -enddate -noout -in "$CERT_FILE" | cut -d= -f2)
    EXPIRY_TS=$(date -d "$EXPIRY" +%s)
    NOW_TS=$(date +%s)
    DAYS_LEFT=$(( ($EXPIRY_TS - $NOW_TS) / 86400 ))
    
    if [ $DAYS_LEFT -lt 30 ]; then
        print_warning "SSL certificate expires in $DAYS_LEFT days"
        print_status "Generating new SSL certificate..."
        openssl req -x509 -newkey rsa:4096 \
            -keyout data/ssl/key.pem \
            -out data/ssl/cert.pem \
            -days 365 \
            -nodes \
            -subj "/C=BR/ST=SP/L=Sao Paulo/O=LogiChain/CN=localhost"
        chmod 600 data/ssl/*.pem
    fi
fi

# Update firewall rules
print_status "Updating firewall rules..."
ufw allow 5000/tcp  # API Server
ufw allow 30303/tcp # P2P Network
ufw allow 30304/tcp # P2P Discovery
ufw allow 8080/tcp  # Web Server
ufw allow 8000/tcp  # Integrated Server
ufw allow 6000/tcp  # Validator Node
ufw allow 7000/tcp  # Executor Node

# Cleanup old data
print_status "Cleaning up old data..."
python3 scripts/backup.py --action cleanup

# Remove old Docker images
print_status "Cleaning up Docker images..."
docker image prune -f

# Start the service
print_status "Starting LogiChain service..."
systemctl start logichain

# Verify service status
print_status "Verifying service status..."
systemctl status logichain

print_status "Update complete!"
echo
echo "Next steps:"
echo "1. Check service logs: journalctl -u logichain"
echo "2. Monitor system status"
echo "3. Test functionality"
echo
print_warning "Important: Review any configuration changes in config/.env.production" 