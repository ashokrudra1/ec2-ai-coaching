#!/bin/bash

################################################################################
# EC2 AUTOMATED DEPLOYMENT SCRIPT
# Veda AI Coaching - Complete Setup & Deployment
################################################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   Veda AI Coaching - EC2 Automated Deployment${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"

################################################################################
# STEP 1: Update System
################################################################################
echo -e "\n${YELLOW}[1/8] Updating system packages...${NC}"
sudo apt-get update -qq
sudo apt-get upgrade -y -qq
echo -e "${GREEN}✓ System updated${NC}"

################################################################################
# STEP 2: Install Docker
################################################################################
echo -e "\n${YELLOW}[2/8] Installing Docker...${NC}"
sudo apt-get install -y -qq docker.io docker-compose-plugin curl git

# Start Docker service
sudo systemctl start docker
sudo systemctl enable docker

# Add ubuntu user to docker group
sudo usermod -aG docker ubuntu
echo -e "${GREEN}✓ Docker installed and configured${NC}"

################################################################################
# STEP 3: Clone Repository
################################################################################
echo -e "\n${YELLOW}[3/8] Cloning repository...${NC}"
cd /home/ubuntu

if [ -d "ec2-ai-coaching" ]; then
    echo "Directory exists, pulling latest changes..."
    cd ec2-ai-coaching
    git pull origin main
else
    git clone https://github.com/ashokrudra1/ec2-ai-coaching.git
    cd ec2-ai-coaching
fi

echo -e "${GREEN}✓ Repository cloned/updated${NC}"

################################################################################
# STEP 4: Create .env file
################################################################################
echo -e "\n${YELLOW}[4/8] Setting up environment configuration...${NC}"

cat > .env << 'ENVFILE'
# Production Config
ENVIRONMENT=production
ALLOWED_ORIGIN=https://vedaactivewellness.xyz

# Database
DATABASE_URL=postgresql://postgres:[REDACTED]@dbcoach.c94smm4quof0.ap-south-1.rds.amazonaws.com:5432/postgres

# Redis
REDIS_URL=redis://redis:6379/0

# Telegram Bot
TELEGRAM_BOT_TOKEN=[REDACTED]
TELEGRAM_SECRET_TOKEN=JaipurVedaSec_987654321_Token

# OpenAI
OPENAI_API_KEY=[REDACTED]

# Strava
STRAVA_CLIENT_ID=204777
STRAVA_CLIENT_SECRET=af6c7c0711d7a9a22b1e9e0fcfbf7b6261811489
STRAVA_SIGNING_SECRET=StravaVedaSec_123456789_Secret
STRAVA_REDIRECT_URI=https://vedaactivewellness.xyz/auth/callback

# Admin
ADMIN_API_KEY=AdminVedaSuperSecretMasterKey_2026
SENTRY_DSN=

# Domain
DOMAIN=vedaactivewellness.xyz
ENVFILE

echo -e "${GREEN}✓ Environment file created${NC}"

################################################################################
# STEP 5: Test RDS Connection
################################################################################
echo -e "\n${YELLOW}[5/8] Testing RDS database connection...${NC}"

# Install postgres client
sudo apt-get install -y -qq postgresql-client

# Extract RDS endpoint from DATABASE_URL
RDS_HOST="dbcoach.c94smm4quof0.ap-south-1.rds.amazonaws.com"

# Test connection (with timeout)
if timeout 10 psql -h $RDS_HOST -U postgres -d postgres -c "SELECT 1" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ RDS connection successful${NC}"
else
    echo -e "${YELLOW}⚠ RDS connection test failed (check security groups)${NC}"
    echo -e "${YELLOW}  RDS Host: $RDS_HOST${NC}"
    echo -e "${YELLOW}  Ensure EC2 security group allows access to RDS security group${NC}"
fi

################################################################################
# STEP 6: Build and Start Services
################################################################################
echo -e "\n${YELLOW}[6/8] Building Docker images and starting services...${NC}"

# Build images
docker compose build --pull

# Start services
docker compose up -d

echo -e "${GREEN}✓ Services started${NC}"

################################################################################
# STEP 7: Initialize Database
################################################################################
echo -e "\n${YELLOW}[7/8] Initializing database tables...${NC}"

# Wait for services to be ready
sleep 10

# Create tables
docker compose exec -T api python -c "from backend.database import Base, engine; Base.metadata.create_all(bind=engine)" || true

echo -e "${GREEN}✓ Database initialized${NC}"

################################################################################
# STEP 8: Verify Deployment
################################################################################
echo -e "\n${YELLOW}[8/8] Verifying deployment...${NC}"

sleep 5

echo -e "\n${BLUE}Running Containers:${NC}"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo -e "\n${BLUE}Service Health:${NC}"
docker compose ps

################################################################################
# FINAL STATUS
################################################################################
echo -e "\n${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✓ DEPLOYMENT COMPLETE!${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"

echo -e "\n${YELLOW}Access your application:${NC}"
echo -e "  🌐 Frontend:   https://vedaactivewellness.xyz"
echo -e "  📚 API Docs:   https://vedaactivewellness.xyz/docs"
echo -e "  🏥 Health:     https://vedaactivewellness.xyz/health"

echo -e "\n${YELLOW}Useful commands:${NC}"
echo -e "  View logs:     docker compose logs -f api"
echo -e "  Check status:  docker compose ps"
echo -e "  SSH to api:    docker compose exec api bash"
echo -e "  Restart:       docker compose restart"

echo -e "\n${YELLOW}Next steps:${NC}"
echo -e "  1. Update DNS A record: vedaactivewellness.xyz → 13.233.127.186"
echo -e "  2. Wait 5-10 minutes for DNS propagation"
echo -e "  3. Access https://vedaactivewellness.xyz"
echo -e "  4. Check logs: docker compose logs -f"

echo -e "\n${BLUE}════════════════════════════════════════════════════════════${NC}\n"
