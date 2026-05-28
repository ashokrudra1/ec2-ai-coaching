#!/bin/bash
# scripts/backup-to-s3.sh
# Automated PostgreSQL backup to S3 with lifecycle management

set -e

# Configuration
BACKUP_DIR="/tmp/backups"
POSTGRES_CONTAINER="postgres"
DB_USER="postgres"
S3_BUCKET="${S3_BACKUP_BUCKET:-veda-ai-backups}"
S3_PREFIX="production/postgresql"
AWS_REGION="ap-south-1"
RETENTION_DAYS=30
COMPRESSION="gzip"

# Logging
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

error() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1" >&2
    exit 1
}

log "Starting PostgreSQL backup to S3..."

# Create backup directory
mkdir -p "$BACKUP_DIR"
BACKUP_FILE="$BACKUP_DIR/postgres_backup_$(date +%Y%m%d_%H%M%S).sql.gz"

# Perform backup
log "Dumping PostgreSQL database..."
docker-compose exec -T "$POSTGRES_CONTAINER" pg_dump -U "$DB_USER" postgres | gzip > "$BACKUP_FILE" || error "Database dump failed"

# Verify backup file
if [ ! -f "$BACKUP_FILE" ]; then
    error "Backup file not created"
fi

BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
log "Backup completed: $BACKUP_FILE ($BACKUP_SIZE)"

# Upload to S3
log "Uploading to S3: s3://$S3_BUCKET/$S3_PREFIX/..."
aws s3 cp "$BACKUP_FILE" "s3://$S3_BUCKET/$S3_PREFIX/" \
    --region "$AWS_REGION" \
    --storage-class STANDARD_IA \
    --metadata "backup-date=$(date -u +%Y-%m-%dT%H:%M:%SZ),environment=production" \
    || error "S3 upload failed"

log "Backup uploaded successfully"

# Cleanup local backup
log "Cleaning up local backup..."
rm -f "$BACKUP_FILE"

# Get backup age and cleanup old backups (keep last 30 days)
log "Cleaning up backups older than $RETENTION_DAYS days..."
aws s3 ls "s3://$S3_BUCKET/$S3_PREFIX/" --region "$AWS_REGION" | while read -r line; do
    BACKUP_DATE=$(echo "$line" | awk '{print $1}')
    BACKUP_NAME=$(echo "$line" | awk '{print $4}')
    BACKUP_TIMESTAMP=$(date -d "$BACKUP_DATE" +%s 2>/dev/null || echo 0)
    CURRENT_TIMESTAMP=$(date +%s)
    DIFF_DAYS=$(( ($CURRENT_TIMESTAMP - $BACKUP_TIMESTAMP) / 86400 ))
    
    if [ $DIFF_DAYS -gt $RETENTION_DAYS ]; then
        log "Deleting old backup: $BACKUP_NAME (age: ${DIFF_DAYS} days)"
        aws s3 rm "s3://$S3_BUCKET/$S3_PREFIX/$BACKUP_NAME" --region "$AWS_REGION" || true
    fi
done

log "Backup process completed successfully"
log "Next backup in 24 hours"
