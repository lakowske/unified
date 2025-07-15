#!/bin/bash
set -e

# Mail server entrypoint script for unified project
# Configures Dovecot and Postfix with PostgreSQL authentication and mailbox setup

echo "Starting mail server container for unified project..."

# Default environment variables for mail services
export MAIL_DOMAIN=${MAIL_DOMAIN:-localhost}
export MAIL_LOG_LEVEL=${MAIL_LOG_LEVEL:-info}
export VMAIL_UID=${VMAIL_UID:-5000}
export VMAIL_GID=${VMAIL_GID:-5000}

# Database connection variables (consistent with Apache container)
export DB_HOST=${DB_HOST:-localhost}
export DB_PORT=${DB_PORT:-5432}
export DB_NAME=${DB_NAME:-unified}
export DB_USER=${DB_USER:-unified_user}
export DB_PASSWORD=${DB_PASSWORD:-}
export DB_SSLMODE=${DB_SSLMODE:-prefer}

echo "Mail server configuration:"
echo "  Domain: $MAIL_DOMAIN"
echo "  Log Level: $MAIL_LOG_LEVEL"
echo "  Database: $DB_HOST:$DB_PORT/$DB_NAME"
echo "  vmail UID/GID: $VMAIL_UID/$VMAIL_GID"

# Ensure required directories exist with proper permissions
echo "Setting up mail directories..."
mkdir -p /var/mail /data/logs/mail /var/run/dovecot /var/spool/postfix
chown -R vmail:vmail /var/mail
chown -R dovecot:dovecot /data/logs/mail /var/run/dovecot
chown -R postfix:postfix /var/spool/postfix
chmod 755 /var/mail /data/logs/mail
chmod 755 /var/run/dovecot /var/spool/postfix

# Wait for database to be ready and schema to exist
echo "Waiting for PostgreSQL database on $DB_HOST:$DB_PORT..."
max_attempts=30
attempt=0

while [ $attempt -lt $max_attempts ]; do
    # Check if we can connect to PostgreSQL and the unified.dovecot_auth view exists
    if PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
        -c "SELECT 1 FROM unified.dovecot_auth LIMIT 1;" >/dev/null 2>&1; then
        echo "Database and unified schema are ready!"
        break
    fi

    attempt=$((attempt + 1))
    echo "Attempt $attempt/$max_attempts: Database not ready, waiting 2 seconds..."
    sleep 2
done

if [ $attempt -eq $max_attempts ]; then
    echo "ERROR: Database or unified schema not ready after $max_attempts attempts"
    echo "Please ensure the database migration has been applied"
    exit 1
fi

# Configure SSL/TLS certificates with preference logic
echo "Configuring SSL/TLS certificates..."
/usr/local/bin/configure-ssl.sh

# Process Dovecot configuration templates (SSL configuration handled by configure-ssl.sh)
echo "Processing Dovecot SQL configuration..."
envsubst < /etc/dovecot/dovecot-sql.conf.template > /etc/dovecot/dovecot-sql.conf.ext

# Process Postfix master configuration template (main.cf handled by configure-ssl.sh)
echo "Processing Postfix master configuration..."
envsubst < /etc/postfix/master.cf.template > /etc/postfix/master.cf

# Create Postfix SQL query files for PostgreSQL lookups
echo "Creating Postfix PostgreSQL lookup configurations..."

# Virtual mailbox domains lookup
cat > /etc/postfix/sql/virtual_domains.cf << EOF
user = ${DB_USER}
password = ${DB_PASSWORD}
hosts = ${DB_HOST}:${DB_PORT}
dbname = ${DB_NAME}
query = SELECT DISTINCT domain FROM unified.users WHERE domain='%s' AND is_active=true
# Connection pooling and timeout settings
connection_limit = 5
expansion_limit = 100
timeout = 30
EOF

# Virtual mailbox users lookup
cat > /etc/postfix/sql/virtual_users.cf << EOF
user = ${DB_USER}
password = ${DB_PASSWORD}
hosts = ${DB_HOST}:${DB_PORT}
dbname = ${DB_NAME}
query = SELECT CONCAT(domain, '/', username, '/') FROM unified.users WHERE email='%s' AND is_active=true
# Connection pooling and timeout settings
connection_limit = 5
expansion_limit = 100
timeout = 30
EOF

# Virtual alias maps lookup
cat > /etc/postfix/sql/virtual_aliases.cf << EOF
user = ${DB_USER}
password = ${DB_PASSWORD}
hosts = ${DB_HOST}:${DB_PORT}
dbname = ${DB_NAME}
query = SELECT u.email FROM unified.email_aliases ea JOIN unified.users u ON ea.user_id = u.id WHERE ea.alias_email='%s' AND ea.is_active=true AND u.is_active=true
# Connection pooling and timeout settings
connection_limit = 5
expansion_limit = 100
timeout = 30
EOF

# Set proper permissions for Postfix SQL configs
chmod 640 /etc/postfix/sql/*.cf
chown root:postfix /etc/postfix/sql/*.cf

# Create mailboxes for existing users
echo "Creating mailboxes for existing users..."
/usr/local/bin/mail-scripts/create_mailboxes.sh

# Create supervisor configuration for running both services
echo "Setting up supervisor configuration..."
mkdir -p /etc/supervisor/conf.d

cat > /etc/supervisor/conf.d/mail.conf << EOF
[supervisord]
nodaemon=true
user=root
logfile=/data/logs/mail/supervisord.log
pidfile=/var/run/supervisord.pid

[program:dovecot]
command=/usr/sbin/dovecot -F
autostart=true
autorestart=true
stderr_logfile=/data/logs/mail/dovecot_error.log
stdout_logfile=/data/logs/mail/dovecot.log
user=root

[program:postfix]
command=/usr/lib/postfix/sbin/master -d
autostart=true
autorestart=true
stderr_logfile=/data/logs/mail/postfix_error.log
stdout_logfile=/data/logs/mail/postfix.log
user=root

[program:rsyslog]
command=/usr/sbin/rsyslogd -n
autostart=true
autorestart=true
stderr_logfile=/data/logs/mail/rsyslog_error.log
stdout_logfile=/data/logs/mail/rsyslog.log
user=root

[program:mailbox-listener]
command=/data/.venv/bin/python /usr/local/bin/mail-scripts/mailbox-listener.py
autostart=true
autorestart=true
stderr_logfile=/data/logs/mail/mailbox_listener_error.log
stdout_logfile=/data/logs/mail/mailbox_listener.log
user=root
environment=DB_HOST="%(ENV_DB_HOST)s",DB_PORT="%(ENV_DB_PORT)s",DB_NAME="%(ENV_DB_NAME)s",DB_USER="%(ENV_DB_USER)s",DB_PASSWORD="%(ENV_DB_PASSWORD)s",VMAIL_UID="%(ENV_VMAIL_UID)s",VMAIL_GID="%(ENV_VMAIL_GID)s"

[program:certificate-watcher]
command=/data/.venv/bin/python /usr/local/bin/certificate-watcher.py
autostart=true
autorestart=true
stderr_logfile=/data/logs/mail/certificate_watcher_error.log
stdout_logfile=/data/logs/mail/certificate_watcher.log
user=root
environment=DB_HOST="%(ENV_DB_HOST)s",DB_PORT="%(ENV_DB_PORT)s",DB_NAME="%(ENV_DB_NAME)s",DB_USER="%(ENV_DB_USER)s",DB_PASSWORD="%(ENV_DB_PASSWORD)s",MAIL_DOMAIN="%(ENV_MAIL_DOMAIN)s",SSL_ENABLED="%(ENV_SSL_ENABLED)s",CERT_TYPE_PREFERENCE="%(ENV_CERT_TYPE_PREFERENCE)s"

[program:opendkim]
command=/usr/sbin/opendkim -f
autostart=true
autorestart=true
stderr_logfile=/data/logs/mail/opendkim_error.log
stdout_logfile=/data/logs/mail/opendkim.log
user=opendkim
EOF

# Configure OpenDKIM
echo "Configuring OpenDKIM for domain: $MAIL_DOMAIN"
/usr/local/bin/generate-dkim-keys.sh

# Create OpenDKIM configuration directory
mkdir -p /etc/opendkim

# Process OpenDKIM configuration templates
envsubst < /usr/local/bin/opendkim/opendkim.conf.template > /etc/opendkim/opendkim.conf
envsubst < /usr/local/bin/opendkim/key.table.template > /etc/opendkim/key.table
envsubst < /usr/local/bin/opendkim/signing.table.template > /etc/opendkim/signing.table
envsubst < /usr/local/bin/opendkim/trusted.hosts.template > /etc/opendkim/trusted.hosts

# Create OpenDKIM runtime directory
mkdir -p /var/run/opendkim
chown opendkim:opendkim /var/run/opendkim

# Set proper permissions on OpenDKIM configuration
chown -R opendkim:opendkim /etc/opendkim

echo "Mail server configuration complete."
echo "Starting Dovecot and Postfix services..."

# Execute the command passed to docker run
exec "$@"
