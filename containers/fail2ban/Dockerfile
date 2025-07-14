# Fail2ban Container for Unified Project
# Provides intrusion prevention by monitoring logs and blocking malicious IPs

FROM localhost/poststack/base-debian:latest

# Install fail2ban and iptables tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    fail2ban \
    iptables \
    ipset \
    netfilter-persistent \
    net-tools \
    rsyslog \
    && rm -rf /var/lib/apt/lists/*

# Create necessary directories
RUN mkdir -p \
    /etc/fail2ban/filter.d \
    /etc/fail2ban/action.d \
    /etc/fail2ban/jail.d \
    /var/log/fail2ban \
    /var/lib/fail2ban \
    /data/logs \
    /data/fail2ban/config \
    /data/fail2ban/database

# Copy custom configuration files
COPY containers/fail2ban/config/fail2ban.conf /etc/fail2ban/
COPY containers/fail2ban/config/jail.conf /etc/fail2ban/jail.d/
COPY containers/fail2ban/config/jail.local /etc/fail2ban/
COPY containers/fail2ban/config/filter.d/ /etc/fail2ban/filter.d/

# Copy entrypoint script
COPY containers/fail2ban/scripts/entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh

# Create fail2ban user (if not exists) and set permissions
RUN groupadd -f fail2ban && \
    useradd -r -g fail2ban -s /bin/false fail2ban 2>/dev/null || true && \
    chown -R fail2ban:fail2ban /var/lib/fail2ban /var/log/fail2ban

# Environment variables
ENV FAIL2BAN_LOG_LEVEL=INFO
ENV FAIL2BAN_LOG_TARGET=/var/log/fail2ban/fail2ban.log
ENV FAIL2BAN_SOCKET=/var/run/fail2ban/fail2ban.sock
ENV FAIL2BAN_PIDFILE=/var/run/fail2ban/fail2ban.pid

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD fail2ban-client ping || exit 1

# Expose rsyslog port for log forwarding (if needed)
EXPOSE 514/udp

# Volume mounts
VOLUME ["/data/logs", "/data/fail2ban/config", "/data/fail2ban/database"]

# Set entrypoint
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["fail2ban-server", "-f"]