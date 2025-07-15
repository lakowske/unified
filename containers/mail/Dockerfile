# Mail Server Container with Dovecot and Postfix for Unified Project
# Based on poststack/base-debian for consistency

FROM localhost/poststack/base-debian:latest

# Install mail server packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Dovecot IMAP server
    dovecot-core \
    dovecot-imapd \
    dovecot-pgsql \
    # Postfix SMTP server
    postfix \
    postfix-pgsql \
    # OpenDKIM for email signing
    opendkim \
    opendkim-tools \
    # PostgreSQL client for authentication
    postgresql-client-15 \
    # Mail utilities
    mailutils \
    # For mailbox management
    procmail \
    # SSL/TLS support
    ssl-cert \
    # Process supervisor
    supervisor \
    # Network utilities for health checks
    netcat-openbsd \
    # System logging
    rsyslog \
    && rm -rf /var/lib/apt/lists/*

# Create vmail user for mail storage (matching schema default UID/GID 5000)
RUN groupadd -g 5000 vmail && \
    useradd -g vmail -u 5000 -d /var/mail -s /usr/sbin/nologin vmail

# Create centralized logging directory structure using existing certgroup
RUN mkdir -p /data/logs/mail /data/logs/container-runtime && \
    chown root:certgroup /data/logs && \
    chmod 2755 /data/logs && \
    chown vmail:certgroup /data/logs/mail && \
    chmod 755 /data/logs/mail

# Create mail directories
RUN mkdir -p /var/mail /var/log/mail /etc/dovecot/conf.d /etc/postfix/sql && \
    chown -R vmail:vmail /var/mail && \
    chmod 755 /var/mail && \
    chown -R dovecot:dovecot /var/log/mail && \
    chmod 755 /var/log/mail

# Add mail users to certgroup for certificate access and logging
RUN usermod -a -G certgroup vmail && \
    usermod -a -G certgroup dovecot && \
    usermod -a -G certgroup postfix

# Copy configuration templates
COPY containers/mail/dovecot.conf.template /etc/dovecot/dovecot.conf.template
COPY containers/mail/dovecot-sql.conf.template /etc/dovecot/dovecot-sql.conf.template
COPY containers/mail/postfix/main.cf.template /etc/postfix/main.cf.template
COPY containers/mail/postfix/master.cf.template /etc/postfix/master.cf.template

# Copy management scripts
COPY containers/mail/scripts/ /usr/local/bin/mail-scripts/
RUN chmod +x /usr/local/bin/mail-scripts/*.sh

# Copy SSL configuration and certificate watcher
COPY containers/mail/configure-ssl.sh /usr/local/bin/configure-ssl.sh
COPY containers/mail/certificate-watcher.py /usr/local/bin/certificate-watcher.py
COPY containers/mail/reload-ssl.sh /usr/local/bin/reload-ssl.sh
COPY containers/mail/generate-dkim-keys.sh /usr/local/bin/generate-dkim-keys.sh
RUN chmod +x /usr/local/bin/configure-ssl.sh /usr/local/bin/certificate-watcher.py /usr/local/bin/reload-ssl.sh /usr/local/bin/generate-dkim-keys.sh

# Copy OpenDKIM configuration templates
COPY containers/mail/opendkim/ /usr/local/bin/opendkim/

# Copy entrypoint script
COPY containers/mail/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Install Python packages for mail management
RUN /data/.venv/bin/pip install --no-cache-dir \
    psycopg2-binary

# Expose SMTP and IMAP ports
EXPOSE 25 143

# Create health check script for mail services
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
# Run base health check\n\
/usr/local/bin/health-check.sh\n\
\n\
# Check Dovecot IMAP service\n\
if pgrep -x dovecot > /dev/null; then\n\
    echo "Dovecot is running"\n\
    # Test IMAP port connectivity\n\
    nc -z localhost 143 || exit 1\n\
    echo "IMAP port accessible"\n\
else\n\
    echo "Dovecot not running"\n\
    exit 1\n\
fi\n\
\n\
# Check Postfix SMTP service\n\
if pgrep -x master > /dev/null; then\n\
    echo "Postfix is running"\n\
    # Test SMTP port connectivity\n\
    nc -z localhost 25 || exit 1\n\
    echo "SMTP port accessible"\n\
else\n\
    echo "Postfix not running"\n\
    exit 1\n\
fi\n\
\n\
echo "Mail services health check passed"\n\
' > /usr/local/bin/mail-health-check.sh && \
    chmod +x /usr/local/bin/mail-health-check.sh

# Health check for mail services
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD ["/usr/local/bin/mail-health-check.sh"]

# Set entrypoint
ENTRYPOINT ["/entrypoint.sh"]
CMD ["supervisord", "-c", "/etc/supervisor/conf.d/mail.conf"]
