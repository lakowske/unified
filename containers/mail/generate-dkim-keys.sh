#!/bin/bash
set -e

# Generate DKIM keys for the mail domain
# This script creates the private key, public key, and DNS record

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - DKIM-KEYGEN - $1" >&2
}

# Check if domain is provided
if [ -z "$MAIL_DOMAIN" ]; then
    log "ERROR: MAIL_DOMAIN environment variable is required"
    exit 1
fi

log "Generating DKIM keys for domain: $MAIL_DOMAIN"

# Create key directory
KEY_DIR="/etc/opendkim/keys/${MAIL_DOMAIN}"
mkdir -p "$KEY_DIR"

# Generate DKIM key pair if it doesn't exist
if [ ! -f "$KEY_DIR/mail.private" ]; then
    log "Generating new DKIM key pair for selector 'mail'"
    
    # Generate key pair
    opendkim-genkey -b 2048 -d "$MAIL_DOMAIN" -D "$KEY_DIR" -r -s mail -v
    
    # Set proper permissions
    chown -R opendkim:opendkim "$KEY_DIR"
    chmod 600 "$KEY_DIR/mail.private"
    chmod 644 "$KEY_DIR/mail.txt"
    
    log "DKIM key pair generated successfully"
    log "Private key: $KEY_DIR/mail.private"
    log "Public key DNS record: $KEY_DIR/mail.txt"
else
    log "DKIM key pair already exists for domain: $MAIL_DOMAIN"
fi

# Display the DNS record that needs to be added
log "=== DNS RECORD FOR DKIM ==="
log "Add this TXT record to your DNS:"
log "Record name: mail._domainkey.${MAIL_DOMAIN}"
log "Record content:"
cat "$KEY_DIR/mail.txt"
log "=========================="

# Verify key permissions
if [ -f "$KEY_DIR/mail.private" ]; then
    PRIVATE_PERMS=$(stat -c "%a" "$KEY_DIR/mail.private")
    PRIVATE_OWNER=$(stat -c "%U:%G" "$KEY_DIR/mail.private")
    
    log "Private key permissions: $PRIVATE_PERMS (owner: $PRIVATE_OWNER)"
    
    if [ "$PRIVATE_PERMS" != "600" ]; then
        log "WARNING: Private key permissions should be 600"
        chmod 600 "$KEY_DIR/mail.private"
    fi
    
    if [ "$PRIVATE_OWNER" != "opendkim:opendkim" ]; then
        log "WARNING: Private key should be owned by opendkim:opendkim"
        chown opendkim:opendkim "$KEY_DIR/mail.private"
    fi
fi

log "DKIM key generation completed"