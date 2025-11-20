#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Traceo - 1-Click Installation${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Step 1: Check Docker
echo -e "${YELLOW}[1/4] Checking Docker installation...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker not found. Please install Docker from https://www.docker.com${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Docker found${NC}"

# Step 2: Check Docker Compose
echo -e "${YELLOW}[2/4] Checking Docker Compose installation...${NC}"
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}Docker Compose not found. Please install from https://docs.docker.com/compose/install${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Docker Compose found${NC}"

# Step 3: Start Docker Compose
echo -e "${YELLOW}[3/4] Starting Traceo services...${NC}"
docker-compose up -d
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Services started${NC}"
else
    echo -e "${RED}Failed to start services${NC}"
    exit 1
fi

# Step 4: Wait for services to be ready
echo -e "${YELLOW}[4/4] Waiting for services to be ready...${NC}"
sleep 10

# Check health
BACKEND_HEALTH=$(curl -s http://localhost:8000/health || echo "error")
if [[ $BACKEND_HEALTH == *"ok"* ]]; then
    echo -e "${GREEN}✓ All services are running${NC}"
else
    echo -e "${YELLOW}Services are starting, this may take a moment...${NC}"
    sleep 5
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Installation Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "Open your browser and go to: ${YELLOW}http://localhost:3000${NC}"
echo ""
echo "To stop services, run: ${YELLOW}docker-compose down${NC}"
echo "To view logs, run: ${YELLOW}docker-compose logs -f${NC}"
echo ""
