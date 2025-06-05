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

# Check system requirements
print_status "Checking system requirements..."

# Check Python version
PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
if (( $(echo "$PYTHON_VERSION 3.8" | awk '{print ($1 < $2)}') )); then
    print_error "Python 3.8 or higher required (found $PYTHON_VERSION)"
    exit 1
fi

# Check Docker
if ! command -v docker &> /dev/null; then
    print_warning "Docker not found. Installing..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    usermod -aG docker $SUDO_USER
    rm get-docker.sh
fi

# Check Docker Compose
if ! command -v docker-compose &> /dev/null; then
    print_warning "Docker Compose not found. Installing..."
    curl -L "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
fi

# Create directory structure
print_status "Creating directory structure..."
mkdir -p data/{blockchain,contracts,logs,keys,web,ssl,static,templates,backups}
mkdir -p config/backups

# Set correct permissions
chown -R $SUDO_USER:$SUDO_USER data config
chmod -R 750 data config

# Install Python dependencies
print_status "Installing Python dependencies..."
python3 -m pip install -r requirements.txt

# Initialize environment
print_status "Initializing environment..."
python3 scripts/init_env.py

# Generate keys and certificates
print_status "Generating keys and certificates..."
python3 scripts/generate_keys.py

# Create environment files
print_status "Setting up environment files..."
python3 scripts/generate_env.py

# Setup firewall rules
print_status "Setting up firewall rules..."

# Allow necessary ports
ufw allow 5000/tcp  # API Server
ufw allow 30303/tcp # P2P Network
ufw allow 30304/tcp # P2P Discovery
ufw allow 8080/tcp  # Web Server
ufw allow 8000/tcp  # Integrated Server
ufw allow 6000/tcp  # Validator Node
ufw allow 7000/tcp  # Executor Node

# Deny other incoming traffic
ufw default deny incoming
ufw default allow outgoing

# Enable firewall
ufw --force enable

# Create systemd service
print_status "Creating systemd service..."
cat > /etc/systemd/system/logichain.service << EOF
[Unit]
Description=LogiChain Blockchain Service
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=$SUDO_USER
WorkingDirectory=$(pwd)
ExecStart=/usr/local/bin/docker-compose up
ExecStop=/usr/local/bin/docker-compose down
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
systemctl daemon-reload

# Create backup script
print_status "Setting up backup script..."
cat > /etc/cron.daily/logichain-backup << EOF
#!/bin/bash
cd $(pwd)
python3 scripts/backup.py --action create
EOF

chmod +x /etc/cron.daily/logichain-backup

# Final setup
print_status "Performing final setup..."

# Generate SSL certificates if not exists
if [ ! -f data/ssl/cert.pem ] || [ ! -f data/ssl/key.pem ]; then
    openssl req -x509 -newkey rsa:4096 \
        -keyout data/ssl/key.pem \
        -out data/ssl/cert.pem \
        -days 365 \
        -nodes \
        -subj "/C=BR/ST=SP/L=Sao Paulo/O=LogiChain/CN=localhost"
fi

# Set correct permissions for SSL files
chmod 600 data/ssl/*.pem

print_status "Setup complete!"
echo
echo "Next steps:"
echo "1. Review configuration in config/.env.production"
echo "2. Start the service: systemctl start logichain"
echo "3. Enable service on boot: systemctl enable logichain"
echo
print_warning "Important: Backup your keys and certificates in data/keys and data/ssl" 