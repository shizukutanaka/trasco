#!/bin/bash

# Traceo Database Backup Script
# Backs up PostgreSQL database and application files
# Usage: ./backup.sh [backup-dir]

set -e

# Configuration
BACKUP_DIR="${1:-.backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DB_BACKUP_FILE="$BACKUP_DIR/traceo_db_$TIMESTAMP.sql.gz"
APP_BACKUP_FILE="$BACKUP_DIR/traceo_app_$TIMESTAMP.tar.gz"

# Database connection
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-traceo}"
DB_USER="${DB_USER:-traceo_user}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Create backup directory
if [ ! -d "$BACKUP_DIR" ]; then
    log_info "Creating backup directory: $BACKUP_DIR"
    mkdir -p "$BACKUP_DIR"
fi

# Check if PostgreSQL is accessible
log_info "Checking database connection..."
if ! PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1" > /dev/null 2>&1; then
    log_error "Cannot connect to database at $DB_HOST:$DB_PORT"
    exit 1
fi

# Backup database
log_info "Backing up database to $DB_BACKUP_FILE..."
if PGPASSWORD="$POSTGRES_PASSWORD" pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" "$DB_NAME" | gzip > "$DB_BACKUP_FILE"; then
    log_info "Database backup completed successfully"
    log_info "Backup size: $(du -h "$DB_BACKUP_FILE" | cut -f1)"
else
    log_error "Database backup failed"
    exit 1
fi

# Backup application files (optional)
if [ -d "backend" ] || [ -d "frontend" ]; then
    log_info "Backing up application files to $APP_BACKUP_FILE..."

    # Create temporary directory for app backup
    TEMP_DIR=$(mktemp -d)
    mkdir -p "$TEMP_DIR/traceo-app"

    # Copy relevant files
    [ -d "backend" ] && cp -r backend "$TEMP_DIR/traceo-app/" || true
    [ -d "frontend/public" ] && cp -r frontend/public "$TEMP_DIR/traceo-app/" || true
    [ -f "docker-compose.yml" ] && cp docker-compose.yml "$TEMP_DIR/traceo-app/" || true
    [ -f ".env.example" ] && cp .env.example "$TEMP_DIR/traceo-app/" || true

    # Create tarball
    if tar -czf "$APP_BACKUP_FILE" -C "$TEMP_DIR" traceo-app > /dev/null 2>&1; then
        log_info "Application backup completed successfully"
        log_info "Backup size: $(du -h "$APP_BACKUP_FILE" | cut -f1)"
    else
        log_warn "Application backup failed, but database backup succeeded"
    fi

    # Cleanup
    rm -rf "$TEMP_DIR"
fi

# Cleanup old backups (keep only last 7 days)
log_info "Cleaning up old backups..."
find "$BACKUP_DIR" -name "traceo_db_*.sql.gz" -mtime +7 -delete
find "$BACKUP_DIR" -name "traceo_app_*.tar.gz" -mtime +7 -delete

# Create backup manifest
MANIFEST="$BACKUP_DIR/MANIFEST_$TIMESTAMP.txt"
cat > "$MANIFEST" << EOF
Traceo Backup Manifest
======================

Timestamp: $TIMESTAMP
Database Host: $DB_HOST
Database Name: $DB_NAME
Database User: $DB_USER

Database Backup:
- File: $(basename $DB_BACKUP_FILE)
- Size: $(du -h "$DB_BACKUP_FILE" | cut -f1)
- MD5: $(md5sum "$DB_BACKUP_FILE" | cut -d' ' -f1)

Application Backup:
- File: $(basename $APP_BACKUP_FILE)
- Size: $(du -h "$APP_BACKUP_FILE" | cut -f1)
- MD5: $(md5sum "$APP_BACKUP_FILE" | cut -d' ' -f1)

Restore Instructions:
====================

1. Database:
   gzip -dc $DB_BACKUP_FILE | PGPASSWORD="your_password" psql -h $DB_HOST -U $DB_USER -d $DB_NAME

2. Application:
   tar -xzf $APP_BACKUP_FILE

Note: Ensure you have PostgreSQL client tools installed before restoring.
EOF

log_info "Backup manifest created: $MANIFEST"
log_info "All backups completed successfully!"
log_info "Backup directory: $(cd $BACKUP_DIR && pwd)"
