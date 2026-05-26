# EC2 ONE-COMMAND DEPLOYMENT

## Copy and paste this into your EC2 terminal:

```bash
curl -fsSL https://raw.githubusercontent.com/ashokrudra1/ec2-ai-coaching/main/deploy.sh | bash
```

Or manually:

```bash
ssh -i "C:\Users\HP\Downloads\coaching.pem" ubuntu@ec2-13-233-127-186.ap-south-1.compute.amazonaws.com

# Once logged in, run:
curl -fsSL https://raw.githubusercontent.com/ashokrudra1/ec2-ai-coaching/main/deploy.sh | bash
```

## What the script does:
✓ Updates system packages
✓ Installs Docker & Docker Compose
✓ Clones your GitHub repository
✓ Creates production .env file
✓ Tests RDS database connection
✓ Builds Docker images
✓ Starts all services (7 containers)
✓ Initializes database tables
✓ Verifies deployment

## After deployment:

1. **Wait 2-3 minutes** for all services to start

2. **Check service status:**
   ```bash
   docker ps
   docker compose logs -f
   ```

3. **Update DNS:**
   - Go to your domain registrar
   - Add/update A record: `vedaactivewellness.xyz` → `13.233.127.186`
   - Wait 5-10 minutes for propagation

4. **Access application:**
   - https://vedaactivewellness.xyz
   - https://vedaactivewellness.xyz/docs

## Troubleshooting:

If RDS connection fails:
- Check EC2 security group allows outbound to RDS
- Check RDS security group allows inbound from EC2

If services don't start:
```bash
docker compose logs api
docker compose logs postgres
```

If you need to restart:
```bash
docker compose restart
```

