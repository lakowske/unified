#!/bin/bash
# Volume setup script - idempotent initialization without privileges
# This script can be run multiple times safely

# Set up signal handlers for clean shutdown
trap 'echo "Received shutdown signal, exiting..."; exit 0' SIGTERM SIGINT

echo "Setting up volumes for environment: ${ENVIRONMENT:-dev}"
echo "Running as user: $(id -u):$(id -g)"

# Create log directories for all services (idempotent)
LOG_DIR="/data/logs"
if [ -d "$LOG_DIR" ]; then
    echo "Creating log directory structure..."

    # Create directories only if they don't exist
    for dir in "$LOG_DIR" "$LOG_DIR/postgres" "$LOG_DIR/apache" "$LOG_DIR/mail" "$LOG_DIR/containers" "$LOG_DIR/database"; do
        if [ ! -d "$dir" ]; then
            echo "Creating directory: $dir"
            mkdir -p "$dir"
        else
            echo "Directory already exists: $dir"
        fi
    done
else
    echo "Log volume not mounted at $LOG_DIR, skipping log directory setup"
fi

# Create certificate directories for SSL/TLS management (idempotent)
CERT_DIR="/data/certificates"
if [ -d "$CERT_DIR" ]; then
    echo "Creating certificate directory structure..."

    # Certificate directory structure
    CERT_DIRS=(
        "$CERT_DIR"
        "$CERT_DIR/live"
        "$CERT_DIR/staged"
        "$CERT_DIR/self-signed"
        "$CERT_DIR/archive"
        "$CERT_DIR/accounts"
        "$CERT_DIR/renewal-hooks"
        "$CERT_DIR/renewal-hooks/pre"
        "$CERT_DIR/renewal-hooks/post"
        "$CERT_DIR/renewal-hooks/deploy"
    )

    # Create certificate directories only if they don't exist
    for dir in "${CERT_DIRS[@]}"; do
        if [ ! -d "$dir" ]; then
            echo "Creating certificate directory: $dir"
            mkdir -p "$dir"
        else
            echo "Certificate directory already exists: $dir"
        fi
    done
else
    echo "Certificate volume not mounted at $CERT_DIR, skipping certificate directory setup"
fi

# Set proper permissions with certgroup for shared access (idempotent - safe to run multiple times)
if [ -d "$LOG_DIR" ]; then
    echo "Setting permissions on $LOG_DIR with certgroup for shared access..."
    chown -R 9999:9999 "$LOG_DIR" || echo "Warning: Could not change ownership to 9999:9999"
    chmod -R 755 "$LOG_DIR" || echo "Warning: Could not change permissions"

    # Set specific ownership for postgres logs (postgres user UID 100)
    if [ -d "$LOG_DIR/postgres" ]; then
        echo "Setting postgres log directory ownership for postgres user (UID 100)..."
        chown -R 100:9999 "$LOG_DIR/postgres" || echo "Warning: Could not change postgres log ownership to 100:9999"
    fi
fi

# Set proper permissions for postgres data directory (idempotent)
POSTGRES_DATA="/data/postgres/data"
if [ -d "$POSTGRES_DATA" ]; then
    echo "Setting postgres data directory ownership for postgres user (UID 100)..."
    chown -R 100:102 "$POSTGRES_DATA" || echo "Warning: Could not change postgres data ownership to 100:102"
    chmod 700 "$POSTGRES_DATA" || echo "Warning: Could not set postgres data directory permissions to 700"
else
    echo "Postgres data volume not mounted at $POSTGRES_DATA, skipping postgres data directory setup"
fi

# Set proper permissions on certificate directories with certgroup for shared access
if [ -d "$CERT_DIR" ]; then
    echo "Setting permissions on $CERT_DIR with certgroup for secure certificate access..."

    # Apache (www-data) should own the certificate directories since it will manage them
    # www-data UID is 33, certgroup GID is 9999
    chown -R 33:9999 "$CERT_DIR" || echo "Warning: Could not change certificate ownership to 33:9999 (www-data:certgroup)"

    # Set secure permissions for certificate directories
    chmod 755 "$CERT_DIR" || echo "Warning: Could not set certificate directory permissions"

    # Set permissions for existing subdirectories
    for subdir in live staged self-signed archive renewal-hooks; do
        if [ -d "$CERT_DIR/$subdir" ]; then
            chmod 755 "$CERT_DIR/$subdir" || echo "Warning: Could not set $subdir directory permissions"
        fi
    done

    # Special permissions for accounts directory (Let's Encrypt private keys)
    if [ -d "$CERT_DIR/accounts" ]; then
        chmod 700 "$CERT_DIR/accounts" || echo "Warning: Could not set accounts directory permissions"
    fi

    echo "Certificate directory permissions set: www-data:certgroup with 755 permissions"
fi

# Create README file for certificate directory
if [ -d "$CERT_DIR" ]; then
    cat > "$CERT_DIR/README.txt" << 'EOF'
Certificate Directory Structure
==============================

This directory contains SSL/TLS certificates managed by the unified project.

Directory Structure:
- live/        : Active certificates (symlinks to current versions)
- staged/      : Staged certificates pending validation
- self-signed/ : Self-signed certificates for development
- archive/     : Historical certificates with timestamps
- accounts/    : Let's Encrypt account keys (restricted access)
- renewal-hooks/: Scripts executed during certificate renewal

Security:
- All directories owned by certgroup (GID 9999) for container access
- Private keys have 600 permissions (owner read/write only)
- Certificates have 644 permissions (owner read/write, group/others read)
- Account keys directory has 700 permissions (owner access only)

DO NOT manually modify files in this directory unless you understand
the certificate management system. Use the poststack cert commands instead.
EOF
fi

# Create marker files to indicate setup is complete
if [ -d "$LOG_DIR" ]; then
    SETUP_MARKER="$LOG_DIR/.volume-setup-complete"
    echo "$(date): Volume setup completed for environment ${ENVIRONMENT:-dev}" > "$SETUP_MARKER"
fi

if [ -d "$CERT_DIR" ]; then
    CERT_MARKER="$CERT_DIR/.certificate-setup-complete"
    echo "$(date): Certificate directory setup completed for environment ${ENVIRONMENT:-dev}" > "$CERT_MARKER"
fi

echo "Volume setup completed successfully - no privileges needed"
exit 0
