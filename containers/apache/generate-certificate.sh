#!/bin/bash
# Certificate generation script for unified project
# Generates certificates in separate directories: live/, staged/, self-signed/
# No symlinks - Apache uses preference logic to select best available certificate

set -e

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [CERT-GEN] $1"
}

# Default values
CERT_DIR="${CERT_DIR:-/data/certificates}"
CERT_TYPE="${1:-self-signed}"
DOMAIN="${2:-localhost}"
EMAIL="${3:-}"
DATABASE_URL="${DATABASE_URL:-}"

# Validate inputs
if [ -z "$DOMAIN" ]; then
    echo "Usage: $0 <cert-type> <domain> [email]"
    echo "cert-type: self-signed, letsencrypt, letsencrypt-staging"
    echo "domain: the domain name for the certificate"
    echo "email: email address for Let's Encrypt (required for letsencrypt types)"
    exit 1
fi

# Set Let's Encrypt staging flag based on cert type
if [ "$CERT_TYPE" = "letsencrypt-staging" ]; then
    LETSENCRYPT_STAGING="true"
    CERT_TYPE="letsencrypt"
else
    LETSENCRYPT_STAGING="false"
fi

# Set email for Let's Encrypt
if [ "$CERT_TYPE" = "letsencrypt" ] && [ -n "$EMAIL" ]; then
    LETSENCRYPT_EMAIL="$EMAIL"
fi

log "INFO: Generating $CERT_TYPE certificate for domain: $DOMAIN"
if [ "$LETSENCRYPT_STAGING" = "true" ]; then
    log "INFO: Using Let's Encrypt staging environment"
fi

# Function to check if certificate exists and is valid for specific type
check_certificate_exists() {
    local domain="$1"
    local cert_type="$2"
    local cert_dir="$CERT_DIR"

    # Determine the directory based on certificate type
    local target_dir
    case "$cert_type" in
        "self-signed")
            target_dir="$cert_dir/self-signed/$domain"
            ;;
        "letsencrypt")
            if [ "$LETSENCRYPT_STAGING" = "true" ]; then
                target_dir="$cert_dir/staged/$domain"
            else
                target_dir="$cert_dir/live/$domain"
            fi
            ;;
        *)
            log "ERROR: Unknown certificate type: $cert_type"
            return 1
            ;;
    esac

    if [ -f "$target_dir/fullchain.pem" ] && [ -f "$target_dir/privkey.pem" ]; then
        log "INFO: $cert_type certificate already exists for $domain"

        # Check if certificate is still valid (not expired)
        if openssl x509 -in "$target_dir/fullchain.pem" -noout -checkend 86400 >/dev/null 2>&1; then
            log "INFO: $cert_type certificate is valid for at least 24 hours"
            return 0
        else
            log "WARNING: $cert_type certificate expires within 24 hours or is already expired"
            return 1
        fi
    else
        log "INFO: No $cert_type certificate found for $domain"
        return 1
    fi
}

# Function to generate self-signed certificate
generate_self_signed() {
    local domain="$1"
    local cert_dir="$CERT_DIR"

    log "INFO: Creating self-signed certificate for $domain"

    # Create directory
    local self_signed_dir="$cert_dir/self-signed/$domain"
    mkdir -p "$self_signed_dir"

    # Generate certificate
    log "INFO: Generating RSA private key and certificate..."
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "$self_signed_dir/privkey.pem" \
        -out "$self_signed_dir/fullchain.pem" \
        -subj "/C=US/ST=Development/L=Development/O=Unified Project/CN=$domain"

    # Create chain.pem (same as fullchain.pem for self-signed)
    cp "$self_signed_dir/fullchain.pem" "$self_signed_dir/chain.pem"

    # Set proper permissions
    chmod 600 "$self_signed_dir/privkey.pem"
    chmod 644 "$self_signed_dir/fullchain.pem" "$self_signed_dir/chain.pem"

    log "INFO: Self-signed certificate created successfully"
    log "INFO: Certificate: $self_signed_dir/fullchain.pem"
    log "INFO: Private key: $self_signed_dir/privkey.pem"

    # Update database if DATABASE_URL is provided
    if [ -n "$DATABASE_URL" ]; then
        update_database_record "$domain" "self-signed" "$self_signed_dir/fullchain.pem" "$self_signed_dir/privkey.pem"
    else
        log "WARNING: DATABASE_URL not set, skipping database update"
    fi
}

# Function to generate Let's Encrypt certificate
generate_letsencrypt() {
    local domain="$1"
    local cert_dir="$CERT_DIR"
    local email="${LETSENCRYPT_EMAIL:-}"
    local staging="${LETSENCRYPT_STAGING:-false}"

    log "INFO: Creating Let's Encrypt certificate for $domain"

    # Check if email is provided
    if [ -z "$email" ]; then
        log "ERROR: Email address is required for Let's Encrypt certificates"
        log "ERROR: Usage: $0 letsencrypt $domain email@example.com"
        exit 1
    fi

    # Determine target directory based on staging
    local le_cert_dir
    if [ "$staging" = "true" ]; then
        le_cert_dir="$cert_dir/staged/$domain"
        log "INFO: Using Let's Encrypt staging environment"
    else
        le_cert_dir="$cert_dir/live/$domain"
        log "INFO: Using Let's Encrypt production environment"
    fi

    # Create target directory
    mkdir -p "$le_cert_dir"

    # Prepare certbot command
    local certbot_args=(
        "certonly"
        "--webroot"
        "--webroot-path=/var/www"
        "--email=$email"
        "--agree-tos"
        "--no-eff-email"
        "--keep-until-expiring"
        "--expand"
        "--domain=$domain"
    )

    # Add staging flag if enabled
    if [ "$staging" = "true" ]; then
        certbot_args+=("--staging")
    fi

    # Set custom certificate directory
    certbot_args+=("--config-dir=$cert_dir/accounts")
    certbot_args+=("--work-dir=$cert_dir/work")
    certbot_args+=("--logs-dir=$cert_dir/logs")

    # Create necessary directories
    mkdir -p "$cert_dir/accounts" "$cert_dir/work" "$cert_dir/logs"
    mkdir -p "/var/www/.well-known/acme-challenge"

    log "INFO: Running certbot with webroot challenge..."
    log "INFO: Make sure Apache is serving .well-known/acme-challenge/ correctly"

    # Run certbot with error handling for compatibility issues
    log "INFO: Attempting certbot certificate generation..."

    # Try certbot with better error handling using the venv version
    local certbot_output
    certbot_output=$(timeout 120 certbot-venv "${certbot_args[@]}" 2>&1)
    local certbot_exit_code=$?

    if [ $certbot_exit_code -eq 0 ]; then
        log "INFO: Let's Encrypt certificate obtained successfully"

        # Find the actual certbot certificate directory (may have suffixes like -0001)
        local certbot_live
        if [ -d "$cert_dir/accounts/live/$domain" ]; then
            certbot_live="$cert_dir/accounts/live/$domain"
        else
            # Look for directories with suffixes like domain-0001, domain-0002, etc.
            certbot_live=$(find "$cert_dir/accounts/live" -maxdepth 1 -name "$domain*" -type d | head -1)
        fi

        if [ -n "$certbot_live" ] && [ -d "$certbot_live" ]; then
            log "INFO: Found certbot certificates at: $certbot_live"

            # Copy certificates from certbot to our target directory
            cp "$certbot_live/fullchain.pem" "$le_cert_dir/"
            cp "$certbot_live/privkey.pem" "$le_cert_dir/"
            cp "$certbot_live/chain.pem" "$le_cert_dir/" 2>/dev/null || cp "$certbot_live/fullchain.pem" "$le_cert_dir/chain.pem"

            # Set proper permissions
            chmod 644 "$le_cert_dir/fullchain.pem" "$le_cert_dir/chain.pem"
            chmod 600 "$le_cert_dir/privkey.pem"

            log "INFO: Let's Encrypt certificate installed successfully"
            log "INFO: Certificate: $le_cert_dir/fullchain.pem"
            log "INFO: Private key: $le_cert_dir/privkey.pem"

            # Update database
            local cert_type
            if [ "$staging" = "true" ]; then
                cert_type="letsencrypt-staging"
            else
                cert_type="letsencrypt"
            fi

            if [ -n "$DATABASE_URL" ]; then
                update_database_record "$domain" "$cert_type" "$le_cert_dir/fullchain.pem" "$le_cert_dir/privkey.pem"
            else
                log "WARNING: DATABASE_URL not set, skipping database update"
            fi
        else
            log "ERROR: Certbot succeeded but certificates not found in accounts/live directory"
            log "ERROR: Searched for: $cert_dir/accounts/live/$domain*"
            ls -la "$cert_dir/accounts/live/" 2>/dev/null || log "ERROR: accounts/live directory not found"
            exit 1
        fi
    else
        log "ERROR: Certbot failed to obtain certificate (exit code: $certbot_exit_code)"
        log "ERROR: Certbot output: $certbot_output"

        # Check for specific known issues
        if echo "$certbot_output" | grep -q "X509_V_FLAG_NOTIFY_POLICY"; then
            log "ERROR: Known Python OpenSSL compatibility issue detected"
            log "INFO: This is a known issue with certbot in some Debian 12 containers"
            log "INFO: Consider using acme.sh or upgrading Python OpenSSL libraries"
            log "INFO: Falling back to self-signed certificate for now"

            # Fall back to self-signed certificate
            generate_self_signed "$domain"
            return
        fi

        log "INFO: Check that the domain $domain resolves to this server"
        log "INFO: Check that Apache is serving /.well-known/acme-challenge/ directory"
        log "INFO: Domain resolution check:"
        nslookup "$domain" || log "WARNING: Domain resolution failed"

        exit 1
    fi
}

# Function to update database record
update_database_record() {
    local domain="$1"
    local cert_type="$2"
    local cert_path="$3"
    local key_path="$4"

    log "INFO: Recording $cert_type certificate in database for $domain"

    # Calculate expiration date (365 days for self-signed)
    local not_after
    if [ "$cert_type" = "self-signed" ]; then
        not_after="NOW() + INTERVAL '365 days'"
    else
        # For Let's Encrypt, we'd extract this from the certificate
        not_after="NOW() + INTERVAL '90 days'"
    fi

    psql "$DATABASE_URL" -c "
        INSERT INTO unified.certificates (domain, certificate_type, not_before, not_after, certificate_path, private_key_path, is_active, auto_renew)
        VALUES (
            '$domain',
            '$cert_type',
            NOW(),
            $not_after,
            '$cert_path',
            '$key_path',
            true,
            $([ "$cert_type" = "letsencrypt" ] && echo "true" || echo "false")
        )
        ON CONFLICT (domain, certificate_type)
        DO UPDATE SET
            not_before = EXCLUDED.not_before,
            not_after = EXCLUDED.not_after,
            certificate_path = EXCLUDED.certificate_path,
            private_key_path = EXCLUDED.private_key_path,
            is_active = EXCLUDED.is_active,
            updated_at = NOW();
    " && log "INFO: Database updated successfully" || log "ERROR: Failed to update database"
}

# Main execution
main() {
    log "INFO: Starting certificate generation for $DOMAIN"
    log "INFO: Certificate type: $CERT_TYPE"
    log "INFO: Certificate directory: $CERT_DIR"

    # Check if certificate already exists for this specific type
    if check_certificate_exists "$DOMAIN" "$CERT_TYPE"; then
        log "INFO: Valid $CERT_TYPE certificate already exists, skipping generation"
        exit 0
    fi

    # Generate certificate based on type
    case "$CERT_TYPE" in
        "self-signed")
            generate_self_signed "$DOMAIN"
            ;;
        "letsencrypt")
            generate_letsencrypt "$DOMAIN"
            ;;
        *)
            log "ERROR: Unsupported certificate type: $CERT_TYPE"
            log "INFO: Supported types: self-signed, letsencrypt, letsencrypt-staging"
            exit 1
            ;;
    esac

    log "INFO: Certificate generation completed successfully"
}

# Execute main function
main "$@"
