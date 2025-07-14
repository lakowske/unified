#!/bin/bash
# Volume setup script - idempotent initialization without privileges
# This script can be run multiple times safely

echo "Setting up volumes for environment: ${ENVIRONMENT:-dev}"
echo "Running as user: $(id -u):$(id -g)"

# Create log directories for all services (idempotent)
LOG_DIR="/data/logs"
echo "Creating log directory structure..."

# Create directories only if they don't exist
for dir in "$LOG_DIR" "$LOG_DIR/postgres" "$LOG_DIR/apache" "$LOG_DIR/mail"; do
    if [ ! -d "$dir" ]; then
        echo "Creating directory: $dir"
        mkdir -p "$dir"
    else
        echo "Directory already exists: $dir"
    fi
done

# Set proper permissions with certgroup for shared access (idempotent - safe to run multiple times)
echo "Setting permissions on $LOG_DIR with certgroup for shared access..."
chown -R 1000:9999 "$LOG_DIR" || echo "Warning: Could not change ownership to 1000:9999"
chmod -R 755 "$LOG_DIR" || echo "Warning: Could not change permissions"

# Set specific ownership for postgres logs (postgres user UID 101)
echo "Setting postgres log directory ownership for postgres user (UID 101)..."
chown -R 101:9999 "$LOG_DIR/postgres" || echo "Warning: Could not change postgres log ownership to 101:9999"

# Create marker file to indicate setup is complete
SETUP_MARKER="$LOG_DIR/.volume-setup-complete"
echo "$(date): Volume setup completed for environment ${ENVIRONMENT:-dev}" > "$SETUP_MARKER"

echo "Volume setup completed successfully - no privileges needed"
exit 0
