#!/bin/bash
# Fail2ban Container Entrypoint Script
# Handles initialization and configuration for fail2ban service

set -e

# Configure logging
exec > >(tee -a /var/log/fail2ban/entrypoint.log)
exec 2>&1

echo "$(date): Starting fail2ban container initialization..."

# Function to log messages
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [FAIL2BAN] $1"
}

log "INFO: Fail2ban container starting up"

# Create necessary directories with proper permissions
log "INFO: Creating and setting up directories"
mkdir -p /var/run/fail2ban /var/log/fail2ban /var/lib/fail2ban

# Copy user-provided configurations if they exist
if [ -d "/data/fail2ban/config" ]; then
    log "INFO: Copying user configuration from /data/fail2ban/config"
    if [ -f "/data/fail2ban/config/jail.conf" ]; then
        cp /data/fail2ban/config/jail.conf /etc/fail2ban/jail.d/
        log "INFO: Copied custom jail.conf"
    fi
    if [ -f "/data/fail2ban/config/fail2ban.conf" ]; then
        cp /data/fail2ban/config/fail2ban.conf /etc/fail2ban/
        log "INFO: Copied custom fail2ban.conf"
    fi
    if [ -d "/data/fail2ban/config/filter.d" ]; then
        cp -r /data/fail2ban/config/filter.d/* /etc/fail2ban/filter.d/ 2>/dev/null || true
        log "INFO: Copied custom filters"
    fi
fi

# Set up persistent ban database location
if [ ! -d "/data/fail2ban/database" ]; then
    mkdir -p /data/fail2ban/database
fi

# Link fail2ban database to persistent storage
if [ ! -L "/var/lib/fail2ban" ]; then
    rm -rf /var/lib/fail2ban
    ln -s /data/fail2ban/database /var/lib/fail2ban
fi

# Validate log paths exist
log "INFO: Validating log file paths"
LOG_PATHS=(
    "/data/logs/apache/unified_access.log"
    "/data/logs/apache/unified_error.log"
    "/data/logs/mail/postfix.log"
    "/data/logs/mail/dovecot.log"
)

for log_path in "${LOG_PATHS[@]}"; do
    if [ ! -f "$log_path" ]; then
        log "WARN: Log file not found: $log_path"
        # Create empty log file to prevent fail2ban errors
        mkdir -p "$(dirname "$log_path")"
        touch "$log_path"
        log "INFO: Created empty log file: $log_path"
    else
        log "INFO: Found log file: $log_path"
    fi
done

# Check if iptables is available (host networking should provide this)
if command -v iptables >/dev/null 2>&1; then
    log "INFO: iptables is available"
    # Test iptables access
    if iptables -L -n >/dev/null 2>&1; then
        log "INFO: iptables access confirmed"
    else
        log "ERROR: iptables access denied - fail2ban may not function properly"
    fi
else
    log "ERROR: iptables not found - fail2ban requires iptables for IP blocking"
fi

# Set proper permissions
chown -R fail2ban:fail2ban /var/lib/fail2ban /var/log/fail2ban /var/run/fail2ban 2>/dev/null || true

# Test fail2ban configuration
log "INFO: Testing fail2ban configuration"
if fail2ban-client -t; then
    log "INFO: Fail2ban configuration test passed"
else
    log "ERROR: Fail2ban configuration test failed"
    fail2ban-client -t
    exit 1
fi

# Handle signals for graceful shutdown
cleanup() {
    log "INFO: Received shutdown signal, stopping fail2ban"
    if [ -f "$FAIL2BAN_PIDFILE" ]; then
        fail2ban-client stop
    fi
    exit 0
}

trap cleanup SIGTERM SIGINT

# Start fail2ban
log "INFO: Starting fail2ban service"
log "INFO: Command: $*"

# If no arguments provided, start fail2ban-server
if [ $# -eq 0 ]; then
    log "INFO: Starting fail2ban-server in foreground mode"
    exec fail2ban-server -f
else
    log "INFO: Executing command: $*"
    exec "$@"
fi
