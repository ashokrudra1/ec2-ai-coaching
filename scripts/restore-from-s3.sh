#!/bin/bash
# scripts/restore-from-s3.sh
# Restore PostgreSQL database from S3 backup

set -e

# Configuration
POSTGRES_CONTAINER="postgres"
DB_USER="postgres"
S3_BUCKET="${S3_BACKUP_BUCKET:-veda-ai-backups}"
S3_PREFIX="production/postgresql"
AWS_REGION="ap-south-1"
RESTORE_DIR="/tmp/restore"

# Logging
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

error() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1" >&2
    exit 1
}

# Parse arguments
if [ -z "$1" ]; then
    log "Usage: $0 <backup-filename>"
    log ""
    log "Available backups:"
    aws s3 ls "s3://$S3_BUCKET/$S3_PREFIX/" --region "$AWS_REGION"
    exit 1
fi

BACKUP_FILE="$1"

log "Starting PostgreSQL restore from S3..."
log "Backup file: $BACKUP_FILE"

# Confirmation
read -p "This will DROP and recreate the entire database. Continue? (yes/no): " -r
if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    log "Restore cancelled"
    exit 0
fi

# Create restore directory
mkdir -p "$RESTORE_DIR"
RESTORE_PATH="$RESTORE_DIR/$BACKUP_FILE"

# Download from S3
log "Downloading backup from S3..."
aws s3 cp "s3://$S3_BUCKET/$S3_PREFIX/$BACKUP_FILE" "$RESTORE_PATH" \
    --region "$AWS_REGION" \
    || error "Download failed"

log "Downloaded: $RESTORE_PATH"

# Restore database
log "Restoring database..."
gunzip -c "$RESTORE_PATH" | docker-compose exec -T "$POSTGRES_CONTAINER" psql -U "$DB_USER" postgres \
    || error "Database restore failed"

log "Database restored successfully"

# Cleanup
log "Cleaning up..."
rm -f "$RESTORE_PATH"

log "Restore process completed"
