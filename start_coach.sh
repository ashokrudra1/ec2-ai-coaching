#!/bin/bash

cd /home/ubuntu/ai-coaching
source backend/venv/bin/activate

echo "🚀 Starting AI Coach..."

# Start backend (MAIN PROCESS)
uvicorn backend.main:app --host 0.0.0.0 --port 8001
