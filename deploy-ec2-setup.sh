#!/bin/bash

# EC2 Deployment Script for Veda AI Coaching
# Run this on your EC2 instance

set -e

echo "🚀 Starting EC2 deployment setup..."

# Update system
sudo apt-get update
sudo apt-get upgrade -y

# Install Docker
echo "📦 Installing Docker..."
sudo apt-get install -y docker.io docker-compose-plugin

# Enable Docker service
sudo systemctl start docker
sudo systemctl enable docker

# Add ubuntu user to docker group
sudo usermod -aG docker ubuntu

# Install git
sudo apt-get install -y git

echo "✓ Docker installed successfully"
echo "✓ Please logout and login again for docker group changes to take effect"
