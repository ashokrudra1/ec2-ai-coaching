# EC2 Deployment Guide - Veda AI Coaching

## Prerequisites
- EC2 instance IP: 13.233.127.186
- SSH key: coaching.pem (in Downloads)
- Domain: vedaactivewellness.xyz

## Step 1: SSH into EC2

```bash
ssh -i "C:\Users\HP\Downloads\coaching.pem" ubuntu@ec2-13-233-127-186.ap-south-1.compute.amazonaws.com
```

## Step 2: Setup Docker on EC2

```bash
# Download and run setup script
curl -fsSL https://raw.githubusercontent.com/your-repo/deploy-ec2-setup.sh | bash

# Or manually:
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-plugin
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker ubuntu
# Logout and login again
```

## Step 3: Clone Repository on EC2

```bash
git clone https://github.com/your-repo/ec2-ai-coaching.git
cd ec2-ai-coaching
```

## Step 4: Create .env on EC2

```bash
# Copy from local .env or create with:
cat > .env << 'EOF'
ENVIRONMENT=production
ALLOWED_ORIGIN=https://vedaactivewellness.xyz
DATABASE_URL=postgresql://postgres:[REDACTED]@postgres:5432/postgres
REDIS_URL=redis://redis:6379/0
TELEGRAM_BOT_TOKEN=[REDACTED]
TELEGRAM_SECRET_TOKEN=JaipurVedaSec_987654321_Token
OPENAI_API_KEY=[REDACTED]
STRAVA_CLIENT_ID=204777
STRAVA_CLIENT_SECRET=af6c7c0711d7a9a22b1e9e0fcfbf7b6261811489
STRAVA_SIGNING_SECRET=StravaVedaSec_123456789_Secret
STRAVA_REDIRECT_URI=https://vedaactivewellness.xyz/auth/callback
ADMIN_API_KEY=AdminVedaSuperSecretMasterKey_2026
SENTRY_DSN=
DOMAIN=vedaactivewellness.xyz
EOF
```

## Step 5: Start Docker Compose

```bash
docker compose up -d
```

## Step 6: Initialize Database

```bash
docker compose exec api python -c "from backend.database import Base, engine; Base.metadata.create_all(bind=engine)"
```

## Step 7: Verify Services

```bash
docker ps
docker compose logs -f
```

## Step 8: Configure DNS

Update your domain registrar to point vedaactivewellness.xyz to:
- A record: 13.233.127.186

## Step 9: Access Application

- Frontend: https://vedaactivewellness.xyz
- API: https://vedaactivewellness.xyz/api
- API Docs: https://vedaactivewellness.xyz/docs

## Monitoring

```bash
# View logs
docker compose logs -f api
docker compose logs -f celery_worker

# Check health
curl https://vedaactivewellness.xyz/health

# SSH into running container
docker compose exec api bash
```

## Troubleshooting

If containers fail to start:
```bash
docker compose down
docker compose up -d
docker compose logs
```

