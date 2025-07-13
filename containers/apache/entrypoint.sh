#!/bin/bash
set -e

# Apache entrypoint script for unified project
# Configures Apache with environment variables and templates

echo "Starting Apache container for unified project..."

# Default environment variables
export APACHE_RUN_USER=${APACHE_RUN_USER:-www-data}
export APACHE_RUN_GROUP=${APACHE_RUN_GROUP:-www-data}
export APACHE_PID_FILE=${APACHE_PID_FILE:-/var/run/apache2/apache2.pid}
export APACHE_RUN_DIR=${APACHE_RUN_DIR:-/var/run/apache2}
export APACHE_LOCK_DIR=${APACHE_LOCK_DIR:-/var/lock/apache2}
export APACHE_LOG_DIR=${APACHE_LOG_DIR:-/data/logs/apache}

# Unified project specific variables
export UNIFIED_DB_HOST=${UNIFIED_DB_HOST:-localhost}
export UNIFIED_DB_PORT=${UNIFIED_DB_PORT:-5435}
export UNIFIED_DB_NAME=${UNIFIED_DB_NAME:-poststack}
export UNIFIED_DB_USER=${UNIFIED_DB_USER:-poststack}
export UNIFIED_DB_PASSWORD=${UNIFIED_DB_PASSWORD:-poststack_dev}
export UNIFIED_DB_SCHEMA=${UNIFIED_DB_SCHEMA:-unified}

# Create run directory
mkdir -p $APACHE_RUN_DIR

# Ensure log directory exists and has proper permissions
mkdir -p $APACHE_LOG_DIR
chown -R www-data:www-data $APACHE_LOG_DIR

# Process configuration templates
echo "Processing Apache configuration templates..."

# Replace placeholders in apache2.conf
envsubst < /etc/apache2/apache2.conf.template > /etc/apache2/apache2.conf

# Replace placeholders in site configuration
envsubst < /etc/apache2/sites-available/unified.conf.template > /etc/apache2/sites-available/unified.conf

# Enable the unified site
a2ensite unified
a2dissite 000-default

# Wait for database to be ready and schema to exist
echo "Waiting for ${DB_HOST} database to be ready on port ${DB_PORT}..."
max_attempts=30
attempt=0

while [ $attempt -lt $max_attempts ]; do
    # Check if we can connect to PostgreSQL and the unified.apache_auth view exists
    if php -r "
        try {
            \$pdo = new PDO('pgsql:host=${DB_HOST};port=${DB_PORT};dbname=${DB_NAME}', '${DB_USER}', '${DB_PASSWORD}');
            \$stmt = \$pdo->query('SELECT 1 FROM unified.apache_auth LIMIT 1');
            echo 'Database ready with unified schema!';
            exit(0);
        } catch (Exception \$e) {
            exit(1);
        }
    " 2>/dev/null; then
        echo "Database and unified schema are ready!"
        break
    fi

    attempt=$((attempt + 1))
    echo "Attempt $attempt/$max_attempts: Database not ready, waiting 2 seconds..."
    sleep 2
done

if [ $attempt -eq $max_attempts ]; then
    echo "ERROR: Database or unified schema not ready after $max_attempts attempts"
    echo "Please ensure the database migration has been applied with: poststack db migrate"
    exit 1
fi

# Web content is already copied by Dockerfile, no need to create index.php

# Generate API key for poststack service operations
echo "Generating API key for service operations..."
API_KEY=$(openssl rand -hex 32)
API_KEY_FILE="/var/local/poststack_api_key"

# Create directory if it doesn't exist
mkdir -p /var/local

# Store API key securely (readable only by www-data)
echo "$API_KEY" > "$API_KEY_FILE"
chown www-data:www-data "$API_KEY_FILE"
chmod 600 "$API_KEY_FILE"

echo "API key generated and stored in $API_KEY_FILE"
echo "API key: $API_KEY"

# Set proper permissions
chown -R www-data:www-data /var/www/unified

echo "Apache configuration complete. Starting server..."

# Execute the command passed to docker run
exec "$@"
