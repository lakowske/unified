#!/bin/bash
# UID/GID mapping configuration for unified project containers
# This ensures consistent user ownership across all services

# Known UIDs from our containers (discovered through testing)
export POSTGRES_UID=101
export POSTGRES_GID=103
export APACHE_UID=33
export APACHE_GID=33
export VMAIL_UID=102
export VMAIL_GID=105
export DOVECOT_UID=102
export DOVECOT_GID=105

# Shared group for log access
export CERTGROUP_GID=9999

# Log which UIDs we're using
echo "UID/GID Mapping:"
echo "  postgres: ${POSTGRES_UID}:${POSTGRES_GID}"
echo "  apache/www-data: ${APACHE_UID}:${APACHE_GID}"
echo "  vmail/dovecot: ${VMAIL_UID}:${VMAIL_GID}"
echo "  certgroup (shared): ${CERTGROUP_GID}"
