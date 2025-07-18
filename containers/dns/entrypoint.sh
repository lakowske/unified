#!/bin/bash
set -e

# DNS Container Entrypoint Script
# Configures and starts BIND DNS server

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - DNS-ENTRYPOINT - $1" >&2
}

log "Starting DNS container entrypoint"

# Create necessary directories (as root first)
mkdir -p /var/log/named /var/run/named /var/cache/bind
chown -R bind:bind /var/log/named /var/run/named /var/cache/bind
# Ensure bind user can write to cache directory
chmod 755 /var/cache/bind

# Ensure zone directory exists and has proper permissions
mkdir -p /data/dns/zones
# Only try to change ownership if we can
if chown -R bind:bind /data/dns/zones 2>/dev/null; then
    log "Set ownership of /data/dns/zones to bind:bind"
else
    log "Could not change ownership of /data/dns/zones, continuing anyway"
fi

# RPZ zone removed - not needed for mail DNS setup

# Create mail domain zone file if MAIL_DOMAIN is set
if [ -n "$MAIL_DOMAIN" ] && [ "$MAIL_DOMAIN" != "localhost" ]; then
    log "Creating zone file for mail domain: $MAIL_DOMAIN"

    # Set default IP if not provided
    MAIL_SERVER_IP=${MAIL_SERVER_IP:-"127.0.0.1"}

    # Create zone file from template
    if [ -f "/usr/local/bin/dns/zones/mail-domain.zone.template" ]; then
        # Use sed to replace variables instead of envsubst to preserve $TTL
        sed -e "s/\${MAIL_DOMAIN}/${MAIL_DOMAIN}/g" \
            -e "s/\${MAIL_SERVER_IP}/${MAIL_SERVER_IP}/g" \
            /usr/local/bin/dns/zones/mail-domain.zone.template > /data/dns/zones/${MAIL_DOMAIN}.zone
        # Only try to change ownership if we can
        if chown bind:bind /data/dns/zones/${MAIL_DOMAIN}.zone 2>/dev/null; then
            log "Set ownership of ${MAIL_DOMAIN}.zone to bind:bind"
        else
            log "Could not change ownership of ${MAIL_DOMAIN}.zone, continuing anyway"
        fi
        log "Zone file created: /data/dns/zones/${MAIL_DOMAIN}.zone"
    else
        log "WARNING: Mail domain zone template not found"
    fi
fi

# Process named.conf.local template
log "Processing named.conf.local template"
if [ -n "$MAIL_DOMAIN" ]; then
    sed -e "s/\${MAIL_DOMAIN}/${MAIL_DOMAIN}/g" /etc/bind/named.conf.local.template > /etc/bind/named.conf.local
else
    # Use default without mail domain
    sed 's/zone "${MAIL_DOMAIN}"/# zone "${MAIL_DOMAIN}"/' /etc/bind/named.conf.local.template > /etc/bind/named.conf.local
fi

# Validate BIND configuration
log "Validating BIND configuration"
if ! named-checkconf /etc/bind/named.conf; then
    log "ERROR: BIND configuration validation failed"
    exit 1
fi

# Check zone files
log "Checking zone files"

# Check mail domain zone file
if [ -n "$MAIL_DOMAIN" ] && [ -f "/data/dns/zones/${MAIL_DOMAIN}.zone" ]; then
    if ! named-checkzone "$MAIL_DOMAIN" "/data/dns/zones/${MAIL_DOMAIN}.zone"; then
        log "WARNING: Mail domain zone file validation failed"
    fi
fi

# Set up signal handlers for graceful shutdown
cleanup() {
    log "Received shutdown signal, stopping BIND"
    if [ -n "$BIND_PID" ]; then
        kill -TERM "$BIND_PID" 2>/dev/null || true
        wait "$BIND_PID" 2>/dev/null || true
    fi
    exit 0
}

trap cleanup SIGTERM SIGINT

# Start BIND in the background
log "Starting BIND DNS server"
# Run as bind user for security
named -g -c /etc/bind/named.conf -u bind &
BIND_PID=$!

log "BIND DNS server started with PID: $BIND_PID"

# Wait for BIND to finish
wait "$BIND_PID"
