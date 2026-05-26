# 🚀 Veda AI Endurance Coach - Production Deployment Guide

This project is now fully containerized using Docker Compose and automated with Caddy for SSL.

## 📋 Prerequisites
- Docker & Docker Compose
- A domain name (e.g., `vedaactivewellness.xyz`) pointed to your server's IP.
- OpenAI API Key
- Telegram Bot Token
- Strava API Credentials

## 🛠️ Quick Start

### 1. Configure Environment
Copy the example environment file and fill in your secrets:
```bash
cp .env.example .env
# Edit .env with your real credentials
```

### 2. Launch the Stack
Run the following command to build and start all services:
```bash
docker compose up --build -d
```

### 3. Initialize Database
Once the containers are running, perform a factory reset to ensure the schema is clean:
```bash
docker compose exec api python nuclear_reset.py
```

## 🏗️ Service Architecture
- **Frontend**: Next.js (Port 3000 internally)
- **API**: FastAPI (Port 8001 internally)
- **Celery Worker**: Background task processor
- **Celery Beat**: Scheduler for periodic syncs
- **DB**: PostgreSQL 15
- **Redis**: Message broker & Cache
- **Caddy**: Reverse proxy & Automatic SSL (Port 80/443)

## 📡 Management Commands

### Viewing Logs
```bash
docker compose logs -f api       # Backend logs
docker compose logs -f frontend  # Frontend logs
docker compose logs -f caddy     # Proxy/SSL logs
```

### Stopping the Stack
```bash
docker compose down
```

### Rebuilding a Single Service
```bash
docker compose up --build -d api
```

## 🩺 Health Check
Visit `https://yourdomain.com/health` to verify the status of all internal dependencies.
