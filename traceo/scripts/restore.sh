#!/bin/bash

# Traceo Database Restore Script
# Restores PostgreSQL database from backup
# Usage: ./restore.sh <backup-file> [--app-only] [--db-only]

set -e

# Configuration
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-traceo}"
DB_USER="${DB_USER:-traceo_user}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

log_prompt() {
    echo -e "${BLUE}[PROMPT]${NC} $1"
}

# Check arguments
if [ $# -lt 1 ]; then
    log_error "Usage: $0 <backup-file> [--app-only] [--db-only]"
    echo "  backup-file: Path to the backup file (SQL.GZ or TAR.GZ)"
    echo "  --app-only:  Only restore application files"
    echo "  --db-only:   Only restore database (default)"
    exit 1
fi

BACKUP_FILE="$1"
APP_ONLY=false
DB_ONLY=true

# Parse additional arguments
for arg in "$@"; do
    case $arg in
        --app-only)
            APP_ONLY=true
            DB_ONLY=false
            shift
            ;;
        --db-only)
            DB_ONLY=true
            APP_ONLY=false
            shift
            ;;
    esac
done

# Validate backup file
if [ ! -f "$BACKUP_FILE" ]; then
    log_error "Backup file not found: $BACKUP_FILE"
    exit 1
fi

# Determine backup type
if [[ "$BACKUP_FILE" == *.sql.gz ]]; then
    BACKUP_TYPE="database"
elif [[ "$BACKUP_FILE" == *.tar.gz ]]; then
    BACKUP_TYPE="application"
else
    log_error "Unknown backup file format: $BACKUP_FILE"
    exit 1
fi

# Show warning
log_warn "This will restore from backup: $(basename $BACKUP_FILE)"
log_prompt "Are you sure you want to continue? Type 'yes' to proceed:"
read -r CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    log_info "Restore cancelled"
    exit 0
fi

# Restore database
if [ "$DB_ONLY" = true ] && [ "$BACKUP_TYPE" = "database" ]; then
    log_info "Restoring database from $BACKUP_FILE..."

    # Check database connection
    log_info "Checking database connection..."
    if ! PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1" > /dev/null 2>&1; then
        log_error "Cannot connect to database at $DB_HOST:$DB_PORT"
        exit 1
    fi

    # Create backup of current database
    log_warn "Creating backup of current database..."
    CURRENT_BACKUP="current_db_backup_$(date +%Y%m%d_%H%M%S).sql.gz"
    if PGPASSWORD="$POSTGRES_PASSWORD" pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" "$DB_NAME" | gzip > "$CURRENT_BACKUP"; then
        log_info "Current database backed up to: $CURRENT_BACKUP"
    else
        log_warn "Could not backup current database"
    fi

    # Drop existing database objects (but keep the database)
    log_info "Dropping existing database objects..."
    if PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" > /dev/null 2>&1; then
        log_info "Database cleared"
    else
        log_error "Failed to clear database"
        exit 1
    fi

    # Restore from backup
    log_info "Restoring database..."
    if gzip -dc "$BACKUP_FILE" | PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" > /dev/null 2>&1; then
        log_info "Database restored successfully!"
    else
        log_error "Database restore failed"
        log_info "To restore from backup: $CURRENT_BACKUP"
        exit 1
    fi

    # Verify restore
    log_info "Verifying restore..."
    TABLE_COUNT=$(PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';" -t 2>/dev/null || echo "0")
    log_info "Tables restored: $TABLE_COUNT"

fi

# Restore application files
if [ "$APP_ONLY" = true ] || ([ "$BACKUP_TYPE" = "application" ] && [ "$DB_ONLY" = false ]); then
    log_info "Restoring application files from $BACKUP_FILE..."

    # Create restore directory
    RESTORE_DIR="traceo_restore_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$RESTORE_DIR"

    if tar -xzf "$BACKUP_FILE" -C "$RESTORE_DIR" > /dev/null 2>&1; then
        log_info "Application files extracted to: $RESTORE_DIR"
        log_warn "Review the restored files in $RESTORE_DIR before merging"
    else
        log_error "Failed to extract application files"
        exit 1
    fi
fi

log_info "Restore completed successfully!"
log_prompt "Next steps: Verify your application is running correctly and all data is present"
