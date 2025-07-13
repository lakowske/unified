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

# Process Dovecot configuration templates
echo "Processing Dovecot configuration..."
envsubst < /etc/dovecot/dovecot.conf.template > /etc/dovecot/dovecot.conf
envsubst < /etc/dovecot/dovecot-sql.conf.template > /etc/dovecot/dovecot-sql.conf.ext

# Process Postfix configuration templates
echo "Processing Postfix configuration..."
envsubst < /etc/postfix/main.cf.template > /etc/postfix/main.cf
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
EOF

# Virtual mailbox users lookup
cat > /etc/postfix/sql/virtual_users.cf << EOF
user = ${DB_USER}
password = ${DB_PASSWORD}
hosts = ${DB_HOST}:${DB_PORT}
dbname = ${DB_NAME}
query = SELECT home FROM unified.dovecot_users WHERE "user"='%s'
EOF

# Virtual alias maps lookup
cat > /etc/postfix/sql/virtual_aliases.cf << EOF
user = ${DB_USER}
password = ${DB_PASSWORD}
hosts = ${DB_HOST}:${DB_PORT}
dbname = ${DB_NAME}
query = SELECT u.email FROM unified.email_aliases ea JOIN unified.users u ON ea.user_id = u.id WHERE ea.alias_email='%s' AND ea.is_active=true AND u.is_active=true
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
EOF

echo "Mail server configuration complete."
echo "Starting Dovecot and Postfix services..."

# Execute the command passed to docker run
exec "$@"
