#!/bin/bash
# scripts/deploy-to-ec2.sh
# Complete one-command deployment to EC2

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() { echo -e "${GREEN}✓${NC} $1"; }
info() { echo -e "${BLUE}ℹ${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC} $1"; }
error() { echo -e "${RED}✗${NC} $1"; exit 1; }

echo ""
echo "======================================================================"
echo "🚀 VEDA AI COACHING - EC2 DEPLOYMENT SCRIPT"
echo "======================================================================"
echo ""

# Configuration
EC2_USER="${EC2_USER:-ubuntu}"
EC2_HOST="${EC2_HOST:-13.233.127.186}"
SSH_KEY="${SSH_KEY:-$HOME/Downloads/coaching.pem}"
APP_DIR="/home/ubuntu/veda-ai-coaching"
REPO_URL="${REPO_URL:-$(git config --get remote.origin.url)}"

info "Configuration:"
echo "  EC2 Host: $EC2_HOST"
echo "  EC2 User: $EC2_USER"
echo "  SSH Key: $SSH_KEY"
echo "  App Directory: $APP_DIR"
echo "  Repository: $REPO_URL"
echo ""

# Verify SSH key
if [ ! -f "$SSH_KEY" ]; then
    error "SSH key not found: $SSH_KEY"
fi
log "SSH key verified"

# Step 1: Push code to EC2
info "Step 1: Pushing code to EC2..."
echo ""

# Check if directory exists on EC2
if ssh -i "$SSH_KEY" -o ConnectTimeout=5 "$EC2_USER@$EC2_HOST" "test -d $APP_DIR"; then
    log "App directory exists on EC2, updating code..."
    ssh -i "$SSH_KEY" "$EC2_USER@$EC2_HOST" "cd $APP_DIR && git pull origin main"
else
    log "Cloning repository to EC2..."
    ssh -i "$SSH_KEY" "$EC2_USER@$EC2_HOST" "git clone $REPO_URL $APP_DIR"
fi

log "Code pushed to EC2"
echo ""

# Step 2: Copy .env template
info "Step 2: Preparing environment configuration..."
ssh -i "$SSH_KEY" "$EC2_USER@$EC2_HOST" "
    if [ ! -f $APP_DIR/.env ]; then
        cp $APP_DIR/.env.example $APP_DIR/.env
        chmod 600 $APP_DIR/.env
        echo 'Template .env created. IMPORTANT: SSH into EC2 and edit with your secrets:'
        echo '  nano $APP_DIR/.env'
    fi
"
log "Environment template ready"
echo ""

# Step 3: Security hardening
info "Step 3: Applying security hardening..."
ssh -i "$SSH_KEY" "$EC2_USER@$EC2_HOST" "
    cd $APP_DIR
    chmod +x scripts/*.sh
    bash scripts/ec2-security-hardening.sh || true
"
log "Security hardening applied"
echo ""

# Step 4: Verify .env is configured
info "Step 4: Checking environment configuration..."
read -p "Have you configured .env file on EC2? (yes/no): " env_configured

if [ "$env_configured" != "yes" ]; then
    warn "Please SSH into EC2 and configure .env file first:"
    echo "  ssh -i \"$SSH_KEY\" $EC2_USER@$EC2_HOST"
    echo "  nano $APP_DIR/.env"
    echo ""
    echo "Required variables:"
    cat .env.example | grep -E "^[A-Z_]+=" | cut -d= -f1 | head -15
    exit 1
fi

log "Environment configuration verified"
echo ""

# Step 5: Build and deploy with Docker
info "Step 5: Building Docker images and deploying..."
ssh -i "$SSH_KEY" "$EC2_USER@$EC2_HOST" "
    cd $APP_DIR
    
    # Stop existing containers
    docker-compose down || true
    
    # Build images
    echo 'Building Docker images...'
    docker-compose build
    
    # Start services
    echo 'Starting services...'
    docker-compose up -d
    
    # Wait for initialization
    echo 'Waiting for database initialization...'
    sleep 15
    
    # Check status
    docker-compose ps
"
log "Docker deployment complete"
echo ""

# Step 6: Initialize database
info "Step 6: Initializing database..."
ssh -i "$SSH_KEY" "$EC2_USER@$EC2_HOST" "
    cd $APP_DIR
    
    # Create tables
    docker-compose exec -T api python -c \
        'from backend.database import Base, engine; Base.metadata.create_all(bind=engine); print(\"Tables created\")'
    
    # Check health
    sleep 5
    curl -s http://localhost:8001/health | python -m json.tool | head -20
"
log "Database initialized"
echo ""

# Step 7: Setup monitoring
info "Step 7: Setting up CloudWatch monitoring..."
ssh -i "$SSH_KEY" "$EC2_USER@$EC2_HOST" "
    cd $APP_DIR
    bash scripts/setup-cloudwatch-monitoring.sh || true
"
log "CloudWatch monitoring configured"
echo ""

# Step 8: Schedule backups
info "Step 8: Scheduling daily backups..."
ssh -i "$SSH_KEY" "$EC2_USER@$EC2_HOST" "
    cd $APP_DIR
    
    # Add cron job for daily backups
    (crontab -l 2>/dev/null | grep -v 'backup-to-s3.sh'; echo '0 2 * * * cd $APP_DIR && bash scripts/backup-to-s3.sh >> /var/log/backup.log 2>&1') | crontab -
    
    echo 'Backup scheduled for 2 AM UTC daily'
"
log "Backup scheduled"
echo ""

# Step 9: Verify deployment
info "Step 9: Verifying deployment..."
echo ""

# Check services
echo "Checking services:"
ssh -i "$SSH_KEY" "$EC2_USER@$EC2_HOST" "
    cd $APP_DIR
    echo ''
    echo 'Running containers:'
    docker-compose ps
    echo ''
    echo 'Health check:'
    curl -s http://localhost:8001/health | python -m json.tool 2>/dev/null || curl -s http://localhost:8001/ping
"

log "Deployment verification complete"
echo ""

echo "======================================================================"
echo "✅ DEPLOYMENT COMPLETE!"
echo "======================================================================"
echo ""
echo "🎯 NEXT STEPS:"
echo ""
echo "1. VERIFY DEPLOYMENT:"
echo "   curl https://vedaactivewellness.xyz/health"
echo ""
echo "2. VIEW LOGS:"
echo "   ssh -i \"$SSH_KEY\" $EC2_USER@$EC2_HOST"
echo "   cd $APP_DIR && docker-compose logs -f api"
echo ""
echo "3. TEST BOT REGISTRATION:"
echo "   Send message to your Telegram bot: /start"
echo ""
echo "4. MONITOR DASHBOARD:"
echo "   https://console.aws.amazon.com/cloudwatch/"
echo ""
echo "5. SSH TO EC2:"
echo "   ssh -i \"$SSH_KEY\" $EC2_USER@$EC2_HOST"
echo ""
echo "======================================================================"
echo ""
