#!/bin/bash
# scripts/ec2-security-hardening.sh
# Production security hardening for EC2 deployment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() {
    echo -e "${GREEN}✓${NC} $1"
}

warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

error() {
    echo -e "${RED}✗${NC} $1"
    exit 1
}

echo "=========================================="
echo "AWS EC2 Production Security Hardening"
echo "=========================================="
echo ""

# 1. Update system packages
log "Updating system packages..."
sudo apt-get update
sudo apt-get upgrade -y

# 2. Install security tools
log "Installing security tools..."
sudo apt-get install -y \
    ufw \
    fail2ban \
    aws-cli \
    curl \
    git \
    htop \
    tmux \
    vim

# 3. Configure firewall (UFW)
log "Configuring firewall..."
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp       # SSH
sudo ufw allow 80/tcp       # HTTP
sudo ufw allow 443/tcp      # HTTPS
sudo ufw --force enable

# 4. Configure SSH security
log "Hardening SSH configuration..."
sudo bash -c 'cat >> /etc/ssh/sshd_config << EOF

# Production hardening
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
X11Forwarding no
MaxAuthTries 3
MaxSessions 10
ClientAliveInterval 300
ClientAliveCountMax 2
Protocol 2
EOF'

sudo systemctl restart ssh

# 5. Setup fail2ban
log "Configuring fail2ban..."
sudo bash -c 'cat > /etc/fail2ban/jail.local << EOF
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5

[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
maxretry = 3
EOF'

sudo systemctl enable fail2ban
sudo systemctl restart fail2ban

# 6. Create IAM role for EC2 (instructions)
log "IAM Role requirements (manual setup):"
echo ""
echo "  1. Create IAM Role: 'VedaAICoachingEC2Role'"
echo "  2. Attach policies:"
echo "     - AmazonSSMManagedInstanceCore (Systems Manager)"
echo "     - CloudWatchAgentServerPolicy (CloudWatch logs)"
echo "     - AmazonS3FullAccess (for backups)"
echo "  3. Attach to this EC2 instance"
echo ""

# 7. Create non-root user for application
log "Creating application user..."
if ! id -u veda >/dev/null 2>&1; then
    sudo useradd -m -s /bin/bash -G docker veda
    echo "User 'veda' created. Add SSH key:"
    echo "sudo -u veda mkdir -p ~/.ssh"
    echo "sudo -u veda chmod 700 ~/.ssh"
    echo "sudo vim /home/veda/.ssh/authorized_keys"
fi

# 8. Configure log rotation
log "Configuring log rotation..."
sudo bash -c 'cat > /etc/logrotate.d/veda-ai-coaching << EOF
/var/log/veda-ai-coaching/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0640 veda veda
    sharedscripts
    postrotate
        docker exec api curl -s http://localhost:8001/health > /dev/null 2>&1 || true
    endscript
}
EOF'

# 9. Install CloudWatch agent
log "Installing CloudWatch agent..."
cd /tmp
wget -q https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb
sudo dpkg -i amazon-cloudwatch-agent.deb

# 10. Configure sysctl for security
log "Configuring kernel parameters..."
sudo bash -c 'cat >> /etc/sysctl.conf << EOF

# Security hardening
net.ipv4.conf.all.send_redirects = 0
net.ipv4.conf.default.send_redirects = 0
net.ipv4.icmp_echo_ignore_broadcasts = 1
net.ipv4.tcp_syncookies = 1
net.ipv4.conf.all.log_martians = 1
net.ipv4.conf.default.log_martians = 1
net.ipv4.tcp_timestamps = 0
net.ipv4.conf.all.arp_ignore = 1
EOF'

sudo sysctl -p > /dev/null

# 11. Disable unnecessary services
log "Disabling unnecessary services..."
sudo systemctl disable --now avahi-daemon 2>/dev/null || true
sudo systemctl disable --now isc-dhcp-server 2>/dev/null || true

# 12. Enable automatic security updates
log "Enabling automatic security updates..."
sudo apt-get install -y unattended-upgrades
sudo bash -c 'cat > /etc/apt/apt.conf.d/50unattended-upgrades << EOF
Unattended-Upgrade::Allowed-Origins {
    "\${distro_id}:\${distro_codename}-security";
};
EOF'

# 13. Create monitoring directory
log "Creating application monitoring directories..."
sudo mkdir -p /var/log/veda-ai-coaching
sudo chown veda:veda /var/log/veda-ai-coaching
sudo chmod 750 /var/log/veda-ai-coaching

# 14. Harden Docker daemon
log "Configuring Docker security..."
sudo bash -c 'cat > /etc/docker/daemon.json << EOF
{
    "log-driver": "json-file",
    "log-opts": {
        "max-size": "50m",
        "max-file": "3"
    },
    "userland-proxy": false,
    "icc": false,
    "live-restore": true,
    "restart-policy": {
        "Name": "on-failure",
        "MaximumRetryCount": 5
    }
}
EOF'

sudo systemctl restart docker

# 15. Enable audit logging
log "Configuring audit logging..."
sudo bash -c 'cat >> /etc/audit/rules.d/docker.rules << EOF
-w /var/lib/docker/ -p wa -k docker
-w /etc/docker/ -p wa -k docker
-w /usr/bin/docker -p x -k docker_exec
EOF'

sudo service auditd restart 2>/dev/null || true

echo ""
echo "=========================================="
echo "✓ Security hardening completed!"
echo "=========================================="
echo ""
echo "Post-hardening checklist:"
echo "  [ ] Verify SSH key-based auth works"
echo "  [ ] Test firewall rules: sudo ufw status"
echo "  [ ] Configure CloudWatch agent"
echo "  [ ] Setup monitoring alerts"
echo "  [ ] Enable backup scheduling"
echo "  [ ] Test database backups"
echo ""
