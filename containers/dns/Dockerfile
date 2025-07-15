FROM poststack/base-debian:latest

# Install BIND DNS server and PostgreSQL client
RUN apt-get update && apt-get install -y \
    bind9 \
    bind9utils \
    bind9-doc \
    dnsutils \
    postgresql-client-15 \
    python3-psycopg2 \
    && rm -rf /var/lib/apt/lists/*

# Create necessary directories
RUN mkdir -p /var/log/named /var/run/named /etc/bind/zones /data/zones
RUN chown -R bind:bind /var/log/named /var/run/named /etc/bind/zones /data/zones
RUN chown -R bind:bind /var/cache/bind

# Copy configuration files
COPY containers/dns/named.conf /etc/bind/named.conf
COPY containers/dns/named.conf.options /etc/bind/named.conf.options
COPY containers/dns/named.conf.local /etc/bind/named.conf.local.template

# Create a writable local config file location
RUN touch /etc/bind/named.conf.local && chown bind:bind /etc/bind/named.conf.local

# Copy DNS management scripts
COPY containers/dns/manage-dkim-records.py /usr/local/bin/manage-dkim-records.py
COPY containers/dns/zones/ /usr/local/bin/dns/zones/
RUN chmod +x /usr/local/bin/manage-dkim-records.py

# Copy entrypoint script
COPY containers/dns/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose DNS ports
EXPOSE 53/udp 53/tcp 953/tcp

# Create volume for zone files
VOLUME ["/data/zones"]

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD dig @127.0.0.1 -p 53 . NS || exit 1

# Start as root, entrypoint will handle switching to bind user
ENTRYPOINT ["/entrypoint.sh"]
CMD ["named", "-g", "-c", "/etc/bind/named.conf", "-u", "bind"]
