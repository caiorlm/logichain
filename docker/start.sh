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

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    print_error "Docker is not running. Please start Docker first."
    exit 1
fi

# Create necessary directories
print_status "Creating data directories..."
mkdir -p data/{blockchain,logs,keys,contracts,web}

# Check if .env file exists, create if not
if [ ! -f .env ]; then
    print_status "Creating .env file..."
    cat > .env << EOF
LOG_LEVEL=INFO
DATA_DIR=/data
STAKE_AMOUNT=1000
REPUTATION_THRESHOLD=0.7
EOF
fi

# Pull or build images
print_status "Building Docker images..."
docker-compose build

# Start the services
print_status "Starting LogiChain services..."
docker-compose up -d

# Wait for services to be ready
print_status "Waiting for services to be ready..."
sleep 10

# Check service health
print_status "Checking service health..."
docker-compose ps

# Print access information
print_status "\nLogiChain services are ready!"
echo -e "\nAccess points:"
echo -e "- API Server: http://localhost:5000"
echo -e "- Web Interface: http://localhost:8081"
echo -e "- Integrated Server: http://localhost:8000"
echo -e "- P2P Network: tcp://localhost:30303"
echo -e "- Validator Node: http://localhost:6000"
echo -e "- Executor Node: http://localhost:7000"
echo -e "- Establishment Node: http://localhost:8001"

print_status "Logs can be viewed with: docker-compose logs -f" 