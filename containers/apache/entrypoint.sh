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

# Database configuration - use standard DB_ environment variables
export DB_HOST=${DB_HOST:-localhost}
export DB_PORT=${DB_PORT:-5432}
export DB_NAME=${DB_NAME:-unified}
export DB_USER=${DB_USER:-unified}
export DB_PASSWORD=${DB_PASSWORD:-unified_dev}
export DB_SCHEMA=${DB_SCHEMA:-unified}

# Legacy UNIFIED_DB_* variables for backward compatibility
export UNIFIED_DB_HOST=${DB_HOST}
export UNIFIED_DB_PORT=${DB_PORT}
export UNIFIED_DB_NAME=${DB_NAME}
export UNIFIED_DB_USER=${DB_USER}
export UNIFIED_DB_PASSWORD=${DB_PASSWORD}
export UNIFIED_DB_SCHEMA=${DB_SCHEMA}

# Certificate generation database URL
export DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"

# SSL/TLS Certificate configuration
export SSL_ENABLED=${SSL_ENABLED:-false}
export SSL_REDIRECT=${SSL_REDIRECT:-false}
export CERT_TYPE=${CERT_TYPE:-self-signed}
export APACHE_SERVER_NAME=${APACHE_SERVER_NAME:-localhost}

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

# SSL certificate setup and site configuration
if [ "$SSL_ENABLED" = "true" ]; then
    echo "SSL enabled - configuring HTTPS virtual host..."

    # Determine certificate paths based on certificate type and domain
    CERT_DIR="/data/certificates"
    CERT_DOMAIN="${APACHE_SERVER_NAME}"

    # Certificate preference logic: live > staged > self-signed
    # Check for live certificates first (Let's Encrypt production)
    if [ -f "$CERT_DIR/live/$CERT_DOMAIN/fullchain.pem" ] && [ -f "$CERT_DIR/live/$CERT_DOMAIN/privkey.pem" ]; then
        echo "Found live Let's Encrypt certificates for $CERT_DOMAIN"
        export SSL_CERT_PATH="$CERT_DIR/live/$CERT_DOMAIN/fullchain.pem"
        export SSL_KEY_PATH="$CERT_DIR/live/$CERT_DOMAIN/privkey.pem"
        export SSL_CHAIN_PATH="$CERT_DIR/live/$CERT_DOMAIN/chain.pem"
        export CERT_TYPE_USED="live"
    # Check for staged certificates second (Let's Encrypt staging)
    elif [ -f "$CERT_DIR/staged/$CERT_DOMAIN/fullchain.pem" ] && [ -f "$CERT_DIR/staged/$CERT_DOMAIN/privkey.pem" ]; then
        echo "Found staged Let's Encrypt certificates for $CERT_DOMAIN"
        export SSL_CERT_PATH="$CERT_DIR/staged/$CERT_DOMAIN/fullchain.pem"
        export SSL_KEY_PATH="$CERT_DIR/staged/$CERT_DOMAIN/privkey.pem"
        export SSL_CHAIN_PATH="$CERT_DIR/staged/$CERT_DOMAIN/chain.pem"
        export CERT_TYPE_USED="staged"
    # Check for self-signed certificates third (fallback)
    elif [ -f "$CERT_DIR/self-signed/$CERT_DOMAIN/fullchain.pem" ] && [ -f "$CERT_DIR/self-signed/$CERT_DOMAIN/privkey.pem" ]; then
        echo "Found self-signed certificates for $CERT_DOMAIN"
        export SSL_CERT_PATH="$CERT_DIR/self-signed/$CERT_DOMAIN/fullchain.pem"
        export SSL_KEY_PATH="$CERT_DIR/self-signed/$CERT_DOMAIN/privkey.pem"
        export SSL_CHAIN_PATH="$CERT_DIR/self-signed/$CERT_DOMAIN/chain.pem"
        export CERT_TYPE_USED="self-signed"
    else
        echo "WARNING: No certificates found for $CERT_DOMAIN, generating self-signed certificate..."

        # Use the certificate generation script
        if /usr/local/bin/generate-certificate.sh self-signed "$CERT_DOMAIN"; then
            echo "Certificate generated successfully, checking paths again..."

            # Check for the generated certificate in self-signed directory
            if [ -f "$CERT_DIR/self-signed/$CERT_DOMAIN/fullchain.pem" ] && [ -f "$CERT_DIR/self-signed/$CERT_DOMAIN/privkey.pem" ]; then
                export SSL_CERT_PATH="$CERT_DIR/self-signed/$CERT_DOMAIN/fullchain.pem"
                export SSL_KEY_PATH="$CERT_DIR/self-signed/$CERT_DOMAIN/privkey.pem"
                export SSL_CHAIN_PATH="$CERT_DIR/self-signed/$CERT_DOMAIN/chain.pem"
                export CERT_TYPE_USED="self-signed"
                echo "Self-signed certificate ready for $CERT_DOMAIN"
            else
                echo "ERROR: Certificate generation reported success but files not found"
                export SSL_ENABLED="false"
                echo "SSL disabled due to certificate generation failure"
            fi
        else
            echo "ERROR: Certificate generation failed"
            export SSL_ENABLED="false"
            echo "SSL disabled due to certificate generation failure"
        fi
    fi

    # Only verify certificate files if SSL is still enabled
    if [ "$SSL_ENABLED" = "true" ]; then
        # Verify certificate files exist and are readable
        if [ ! -f "$SSL_CERT_PATH" ] || [ ! -f "$SSL_KEY_PATH" ]; then
            echo "ERROR: SSL certificate files not found or not readable"
            echo "Certificate: $SSL_CERT_PATH"
            echo "Private Key: $SSL_KEY_PATH"
            exit 1
        fi
    fi

    if [ "$SSL_ENABLED" = "true" ]; then
        echo "Using SSL certificates (type: $CERT_TYPE_USED):"
        echo "  Certificate: $SSL_CERT_PATH"
        echo "  Private Key: $SSL_KEY_PATH"
        echo "  Chain: $SSL_CHAIN_PATH"

        # Process SSL virtual host template
        envsubst < /etc/apache2/sites-available/unified-ssl.conf.template > /etc/apache2/sites-available/unified-ssl.conf

        # Enable SSL site and modules
        a2ensite unified-ssl
        a2enmod ssl

        echo "SSL virtual host configured and enabled"
    fi

    # Create ACME challenge directory for Let's Encrypt
    mkdir -p /var/www/acme-challenge
    chown www-data:www-data /var/www/acme-challenge
else
    echo "SSL disabled - using HTTP only"
fi

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
    echo "Please ensure the database migration has been applied with: docker compose run --rm flyway migrate"
    exit 1
fi

# Web content is already copied by Dockerfile, no need to create index.php

# Generate API key for unified service operations
echo "Generating API key for service operations..."
API_KEY=$(openssl rand -hex 32)
API_KEY_FILE="/var/local/unified_api_key"

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
