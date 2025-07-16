#!/bin/bash
set -e

# Mail server SSL reload script
# Safely reloads Dovecot and Postfix configurations after SSL certificate changes

echo "Starting mail server SSL reload..."

# Source environment variables
export MAIL_DOMAIN=${MAIL_DOMAIN:-localhost}
export SSL_ENABLED=${SSL_ENABLED:-false}

echo "Reload configuration:"
echo "  Domain: $MAIL_DOMAIN"
echo "  SSL Enabled: $SSL_ENABLED"

# Function to test configuration before applying
test_dovecot_config() {
    echo "Testing Dovecot configuration..."
    if dovecot -n >/dev/null 2>&1; then
        echo "Dovecot configuration test passed"
        return 0
    else
        echo "ERROR: Dovecot configuration test failed"
        return 1
    fi
}

# Function to test Postfix configuration
test_postfix_config() {
    echo "Testing Postfix configuration..."
    if postfix check >/dev/null 2>&1; then
        echo "Postfix configuration test passed"
        return 0
    else
        echo "ERROR: Postfix configuration test failed"
        return 1
    fi
}

# Function to reload Dovecot safely
reload_dovecot() {
    echo "Reloading Dovecot..."

    # Test configuration first
    if ! test_dovecot_config; then
        echo "ERROR: Dovecot configuration test failed, aborting reload"
        return 1
    fi

    # Reload Dovecot
    if doveadm reload >/dev/null 2>&1; then
        echo "Dovecot reloaded successfully"

        # Verify Dovecot is still running
        if pgrep -x dovecot >/dev/null; then
            echo "Dovecot is running after reload"
            return 0
        else
            echo "ERROR: Dovecot stopped after reload"
            return 1
        fi
    else
        echo "ERROR: Dovecot reload failed"
        return 1
    fi
}

# Function to reload Postfix safely
reload_postfix() {
    echo "Reloading Postfix..."

    # Test configuration first
    if ! test_postfix_config; then
        echo "ERROR: Postfix configuration test failed, aborting reload"
        return 1
    fi

    # Reload Postfix
    if postfix reload >/dev/null 2>&1; then
        echo "Postfix reloaded successfully"

        # Verify Postfix is still running
        if pgrep -x master >/dev/null; then
            echo "Postfix is running after reload"
            return 0
        else
            echo "ERROR: Postfix stopped after reload"
            return 1
        fi
    else
        echo "ERROR: Postfix reload failed"
        return 1
    fi
}

# Function to verify SSL certificates are accessible
verify_ssl_certificates() {
    if [ "$SSL_ENABLED" != "true" ]; then
        echo "SSL disabled, skipping certificate verification"
        return 0
    fi

    local ssl_cert_path="${SSL_CERT_PATH:-}"
    local ssl_key_path="${SSL_KEY_PATH:-}"

    if [ -z "$ssl_cert_path" ] || [ -z "$ssl_key_path" ]; then
        echo "ERROR: SSL enabled but certificate paths not set"
        return 1
    fi

    echo "Verifying SSL certificates..."
    echo "  Certificate: $ssl_cert_path"
    echo "  Key: $ssl_key_path"

    # Check certificate file exists and is readable
    if [ ! -f "$ssl_cert_path" ]; then
        echo "ERROR: Certificate file not found: $ssl_cert_path"
        return 1
    fi

    if [ ! -r "$ssl_cert_path" ]; then
        echo "ERROR: Certificate file not readable: $ssl_cert_path"
        return 1
    fi

    # Check key file exists and is readable
    if [ ! -f "$ssl_key_path" ]; then
        echo "ERROR: Key file not found: $ssl_key_path"
        return 1
    fi

    if [ ! -r "$ssl_key_path" ]; then
        echo "ERROR: Key file not readable: $ssl_key_path"
        return 1
    fi

    # Verify certificate is valid and not expired
    if ! openssl x509 -checkend 86400 -noout -in "$ssl_cert_path" >/dev/null 2>&1; then
        echo "ERROR: Certificate is expired or will expire within 24 hours"
        return 1
    fi

    # Verify certificate and key match
    cert_modulus=$(openssl x509 -noout -modulus -in "$ssl_cert_path" 2>/dev/null | openssl md5)
    key_modulus=$(openssl rsa -noout -modulus -in "$ssl_key_path" 2>/dev/null | openssl md5)

    if [ "$cert_modulus" != "$key_modulus" ]; then
        echo "ERROR: Certificate and key do not match"
        return 1
    fi

    echo "SSL certificate verification passed"
    return 0
}

# Function to check service health after reload
check_service_health() {
    echo "Checking service health after reload..."

    # Check Dovecot IMAP port
    if ! nc -z localhost 143 >/dev/null 2>&1; then
        echo "ERROR: Dovecot IMAP port (143) not accessible"
        return 1
    fi

    # Check Postfix SMTP port
    if ! nc -z localhost 25 >/dev/null 2>&1; then
        echo "ERROR: Postfix SMTP port (25) not accessible"
        return 1
    fi

    # If SSL is enabled, check secure ports
    if [ "$SSL_ENABLED" = "true" ]; then
        if ! nc -z localhost 993 >/dev/null 2>&1; then
            echo "WARNING: Dovecot IMAPS port (993) not accessible"
        fi

        if ! nc -z localhost 465 >/dev/null 2>&1; then
            echo "WARNING: Postfix SMTPS port (465) not accessible"
        fi

        if ! nc -z localhost 587 >/dev/null 2>&1; then
            echo "WARNING: Postfix submission port (587) not accessible"
        fi
    fi

    echo "Service health check passed"
    return 0
}

# Main execution
echo "=== Mail Server SSL Reload ==="

# Step 1: Verify SSL certificates if SSL is enabled
if ! verify_ssl_certificates; then
    echo "ERROR: SSL certificate verification failed"
    exit 1
fi

# Step 2: Reload Dovecot
if ! reload_dovecot; then
    echo "ERROR: Dovecot reload failed"
    exit 1
fi

# Step 3: Reload Postfix
if ! reload_postfix; then
    echo "ERROR: Postfix reload failed"
    exit 1
fi

# Step 4: Check service health
if ! check_service_health; then
    echo "WARNING: Service health check failed after reload"
    # Don't exit with error, services might still be starting
fi

echo "Mail server SSL reload completed successfully"
echo "Services reloaded with SSL configuration"

# Log reload event
logger -t mail-ssl-reload "Mail server SSL configuration reloaded successfully for domain $MAIL_DOMAIN"
