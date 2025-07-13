# Apache Web Server Container for Unified Project
# Based on poststack/base-debian for consistency

FROM localhost/poststack/base-debian:latest

# Install Apache and required modules
RUN apt-get update && apt-get install -y --no-install-recommends \
    apache2 \
    apache2-utils \
    libapache2-mod-php \
    libaprutil1-dbd-pgsql \
    php \
    php-pgsql \
    php-json \
    php-curl \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Enable Apache modules
RUN a2enmod rewrite ssl headers deflate expires dbd authn_dbd

# Create centralized logging directory structure using existing certgroup
RUN mkdir -p /data/logs/apache /data/logs/container-runtime && \
    chown root:certgroup /data/logs && \
    chmod 2755 /data/logs && \
    chown www-data:certgroup /data/logs/apache && \
    chmod 755 /data/logs/apache

# Add www-data user to certgroup for certificate access and logging
RUN usermod -a -G certgroup www-data

# Create application directory
RUN mkdir -p /var/www/unified

# Copy configuration templates
COPY containers/apache/apache2.conf.template /etc/apache2/apache2.conf.template
COPY containers/apache/sites-available/unified.conf.template /etc/apache2/sites-available/unified.conf.template
COPY containers/apache/entrypoint.sh /entrypoint.sh

# Copy web content
COPY src/www/ /var/www/unified/

# Set proper permissions
RUN chmod +x /entrypoint.sh
RUN chown -R www-data:www-data /var/www/unified

# Expose HTTP and HTTPS ports
EXPOSE 80 443

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:80/health || exit 1

# Set entrypoint
ENTRYPOINT ["/entrypoint.sh"]
CMD ["apache2ctl", "-D", "FOREGROUND"]
