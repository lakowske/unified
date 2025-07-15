#!/bin/bash
set -e

# Mail server SSL/TLS certificate configuration script
# Implements certificate preference logic: live > staged > self-signed
# Sets up SSL for both Dovecot (IMAP/IMAPS) and Postfix (SMTP/SMTPS/Submission)

echo "Starting mail server SSL/TLS certificate configuration..."

# SSL configuration variables
export SSL_ENABLED=${SSL_ENABLED:-false}
export CERT_TYPE_PREFERENCE=${CERT_TYPE_PREFERENCE:-}
export MAIL_DOMAIN=${MAIL_DOMAIN:-localhost}
export CERT_DIR=${CERT_DIR:-/data/certificates}

# Ensure required mail configuration variables are set for envsubst
export VMAIL_UID=${VMAIL_UID:-5000}
export VMAIL_GID=${VMAIL_GID:-5000}

echo "SSL Configuration:"
echo "  SSL Enabled: $SSL_ENABLED"
echo "  Mail Domain: $MAIL_DOMAIN"
echo "  Certificate Directory: $CERT_DIR"
echo "  Certificate Type Preference: $CERT_TYPE_PREFERENCE"

# Function to check if certificate exists and is valid
check_certificate_exists() {
    local domain="$1"
    local cert_type="$2"
    local cert_dir="$CERT_DIR"
    
    local target_dir
    case "$cert_type" in
        "live")
            target_dir="$cert_dir/live/$domain"
            ;;
        "staged")
            target_dir="$cert_dir/staged/$domain"
            ;;
        "self-signed")
            target_dir="$cert_dir/self-signed/$domain"
            ;;
        *)
            echo "ERROR: Unknown certificate type: $cert_type"
            return 1
            ;;
    esac
    
    if [ -f "$target_dir/fullchain.pem" ] && [ -f "$target_dir/privkey.pem" ]; then
        # Check if certificate is not expired
        if openssl x509 -checkend 86400 -noout -in "$target_dir/fullchain.pem" >/dev/null 2>&1; then
            echo "Valid $cert_type certificate found for $domain at $target_dir"
            export SSL_CERT_PATH="$target_dir/fullchain.pem"
            export SSL_KEY_PATH="$target_dir/privkey.pem"
            export SSL_CHAIN_PATH="$target_dir/chain.pem"
            export CERT_TYPE_USED="$cert_type"
            return 0
        else
            echo "Certificate at $target_dir is expired, skipping"
            return 1
        fi
    else
        echo "No valid certificate files found at $target_dir"
        return 1
    fi
}

# Function to configure SSL based on preference
configure_ssl_certificates() {
    local domain="$MAIL_DOMAIN"
    
    # If SSL is disabled, skip certificate configuration
    if [ "$SSL_ENABLED" != "true" ]; then
        echo "SSL is disabled, skipping certificate configuration"
        export SSL_CERT_PATH=""
        export SSL_KEY_PATH=""
        export SSL_CHAIN_PATH=""
        export CERT_TYPE_USED="none"
        return 0
    fi
    
    # If specific certificate type preference is set, only check that type
    if [ -n "$CERT_TYPE_PREFERENCE" ]; then
        echo "Certificate type preference specified: $CERT_TYPE_PREFERENCE"
        case "$CERT_TYPE_PREFERENCE" in
            "live"|"staged"|"self-signed")
                if check_certificate_exists "$domain" "$CERT_TYPE_PREFERENCE"; then
                    echo "Using $CERT_TYPE_PREFERENCE certificate for $domain"
                    return 0
                else
                    echo "ERROR: Preferred certificate type '$CERT_TYPE_PREFERENCE' not available for $domain"
                    export SSL_ENABLED="false"
                    return 1
                fi
                ;;
            *)
                echo "ERROR: Invalid certificate type preference: $CERT_TYPE_PREFERENCE"
                export SSL_ENABLED="false"
                return 1
                ;;
        esac
    fi
    
    # Certificate preference logic: live > staged > self-signed
    # Check for live certificates first (Let's Encrypt production)
    if check_certificate_exists "$domain" "live"; then
        echo "Using live Let's Encrypt certificate for $domain"
        return 0
    # Check for staged certificates second (Let's Encrypt staging)
    elif check_certificate_exists "$domain" "staged"; then
        echo "Using staged Let's Encrypt certificate for $domain"
        return 0
    # Check for self-signed certificates last
    elif check_certificate_exists "$domain" "self-signed"; then
        echo "Using self-signed certificate for $domain"
        return 0
    else
        echo "WARNING: No valid certificates found for $domain, disabling SSL"
        export SSL_ENABLED="false"
        export SSL_CERT_PATH=""
        export SSL_KEY_PATH=""
        export SSL_CHAIN_PATH=""
        export CERT_TYPE_USED="none"
        return 1
    fi
}

# Function to update Dovecot SSL configuration
configure_dovecot_ssl() {
    local dovecot_conf="/etc/dovecot/dovecot.conf"
    local dovecot_template="/etc/dovecot/dovecot.conf.template"
    
    echo "Configuring Dovecot SSL settings..."
    
    if [ "$SSL_ENABLED" = "true" ] && [ -n "$SSL_CERT_PATH" ] && [ -n "$SSL_KEY_PATH" ]; then
        echo "Enabling SSL for Dovecot with certificate: $SSL_CERT_PATH"
        
        # Update Dovecot configuration to enable SSL
        sed -e "s|^ssl = no|ssl = yes|" \
            -e "s|^# ssl_cert = <.*|ssl_cert = <$SSL_CERT_PATH|" \
            -e "s|^# ssl_key = <.*|ssl_key = <$SSL_KEY_PATH|" \
            "$dovecot_template" | envsubst > "$dovecot_conf"
        
        # Ensure certificate files are readable by dovecot
        chown dovecot:dovecot "$SSL_CERT_PATH" "$SSL_KEY_PATH" 2>/dev/null || true
        chmod 644 "$SSL_CERT_PATH" 2>/dev/null || true
        chmod 600 "$SSL_KEY_PATH" 2>/dev/null || true
        
        echo "Dovecot SSL configuration updated successfully"
    else
        echo "SSL disabled for Dovecot"
        
        # Use template with variable substitution but SSL disabled
        envsubst < "$dovecot_template" > "$dovecot_conf"
    fi
}

# Function to update Postfix SSL configuration
configure_postfix_ssl() {
    local postfix_conf="/etc/postfix/main.cf"
    local postfix_template="/etc/postfix/main.cf.template"
    local postfix_master_conf="/etc/postfix/master.cf"
    local postfix_master_template="/etc/postfix/master.cf.template"
    
    echo "Configuring Postfix SSL settings..."
    
    if [ "$SSL_ENABLED" = "true" ] && [ -n "$SSL_CERT_PATH" ] && [ -n "$SSL_KEY_PATH" ]; then
        echo "Enabling SSL for Postfix with certificate: $SSL_CERT_PATH"
        
        # Update Postfix main.cf configuration to enable TLS
        sed -e "s|^smtpd_use_tls = no|smtpd_use_tls = yes|" \
            -e "s|^# smtpd_tls_cert_file = .*|smtpd_tls_cert_file = $SSL_CERT_PATH|" \
            -e "s|^# smtpd_tls_key_file = .*|smtpd_tls_key_file = $SSL_KEY_PATH|" \
            -e "s|^# smtpd_tls_security_level = .*|smtpd_tls_security_level = may|" \
            "$postfix_template" | envsubst > "$postfix_conf"
        
        # Update Postfix master.cf configuration for SSL ports
        echo "Configuring Postfix SSL ports (submission and smtps)"
        envsubst < "$postfix_master_template" > "$postfix_master_conf"
        
        # Add additional TLS settings for better security
        cat >> "$postfix_conf" << EOF

# Additional TLS settings for $CERT_TYPE_USED certificate
smtpd_tls_protocols = !SSLv2, !SSLv3, !TLSv1, !TLSv1.1
smtpd_tls_ciphers = medium
smtpd_tls_mandatory_protocols = !SSLv2, !SSLv3, !TLSv1, !TLSv1.1
smtpd_tls_mandatory_ciphers = medium
smtpd_tls_exclude_ciphers = aNULL, eNULL, EXPORT, DES, RC4, MD5, PSK, SRP, DSS, aECDH, EDH-DSS-DES-CBC3-SHA, EDH-RSA-DES-CDC3-SHA, KRB5-DE5, CBC3-SHA
smtpd_tls_session_cache_database = btree:\${data_directory}/smtpd_scache
smtp_tls_session_cache_database = btree:\${data_directory}/smtp_scache
smtpd_tls_loglevel = 1
smtpd_tls_received_header = yes
smtpd_tls_ask_ccert = yes
tls_random_source = dev:/dev/urandom
EOF
        
        # Ensure certificate files are readable by postfix
        chown postfix:postfix "$SSL_CERT_PATH" "$SSL_KEY_PATH" 2>/dev/null || true
        chmod 644 "$SSL_CERT_PATH" 2>/dev/null || true
        chmod 600 "$SSL_KEY_PATH" 2>/dev/null || true
        
        echo "Postfix SSL configuration updated successfully"
    else
        echo "SSL disabled for Postfix"
        
        # Use templates with variable substitution but SSL disabled
        envsubst < "$postfix_template" > "$postfix_conf"
        envsubst < "$postfix_master_template" > "$postfix_master_conf"
    fi
}

# Function to log certificate status to database
log_certificate_status() {
    if [ -z "$DATABASE_URL" ]; then
        echo "WARNING: DATABASE_URL not set, skipping certificate status logging"
        return 0
    fi
    
    local domain="$MAIL_DOMAIN"
    local cert_type="$CERT_TYPE_USED"
    local ssl_enabled="$SSL_ENABLED"
    
    echo "Logging certificate status to database..."
    
    # Use Python to update certificate status in database
    /data/.venv/bin/python << EOF
import os
import psycopg2
from datetime import datetime
import sys

try:
    # Get environment variables
    domain = os.environ.get('MAIL_DOMAIN', 'localhost')
    cert_type = os.environ.get('CERT_TYPE_USED', 'none')
    ssl_enabled = os.environ.get('SSL_ENABLED', 'false')
    ssl_cert_path = os.environ.get('SSL_CERT_PATH', '')
    
    # Connect to database
    conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
    cur = conn.cursor()
    
    # Check if the table exists first
    cur.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_schema = 'unified' 
            AND table_name = 'service_certificates'
        )
    """)
    table_exists = cur.fetchone()[0]
    
    if table_exists:
        # Update certificate status for mail service
        cur.execute("""
            INSERT INTO unified.service_certificates (
                service_name, domain, certificate_type, ssl_enabled, 
                certificate_path, last_updated, is_active
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (service_name, domain) 
            DO UPDATE SET 
                certificate_type = EXCLUDED.certificate_type,
                ssl_enabled = EXCLUDED.ssl_enabled,
                certificate_path = EXCLUDED.certificate_path,
                last_updated = EXCLUDED.last_updated,
                is_active = EXCLUDED.is_active
        """, (
            'mail', domain, cert_type, ssl_enabled == 'true',
            ssl_cert_path, datetime.now(), True
        ))
        
        # Trigger certificate change notification
        cur.execute("NOTIFY certificate_change, %s", (f"mail:{domain}:{cert_type}",))
        
        conn.commit()
        print(f"Certificate status logged: service=mail, domain={domain}, type={cert_type}, ssl={ssl_enabled}")
    else:
        print(f"WARNING: service_certificates table not found, skipping certificate status logging")
        print(f"Certificate status: service=mail, domain={domain}, type={cert_type}, ssl={ssl_enabled}")
    
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"WARNING: Failed to log certificate status: {e}")
    print(f"Certificate status: service=mail, domain={domain}, type={cert_type}, ssl={ssl_enabled}")
    # Don't exit with error - this should not prevent the mail service from starting
EOF
}

# Main execution
echo "=== Mail Server SSL/TLS Certificate Configuration ==="

# Configure SSL certificates based on preference
configure_ssl_certificates

# Update service configurations
configure_dovecot_ssl
configure_postfix_ssl

# Log certificate status to database
log_certificate_status

echo "SSL/TLS certificate configuration completed successfully"
echo "Certificate type used: $CERT_TYPE_USED"
echo "SSL enabled: $SSL_ENABLED"

# Export final SSL configuration for other scripts
export SSL_CONFIGURED="true"
export FINAL_SSL_CERT_PATH="$SSL_CERT_PATH"
export FINAL_SSL_KEY_PATH="$SSL_KEY_PATH"
export FINAL_CERT_TYPE="$CERT_TYPE_USED"

echo "=== SSL Configuration Summary ==="
echo "SSL Enabled: $SSL_ENABLED"
echo "Certificate Type: $CERT_TYPE_USED"
echo "Certificate Path: $SSL_CERT_PATH"
echo "Key Path: $SSL_KEY_PATH"