# Apache Web Server Container for Unified Project
# Based on poststack/base-debian for consistency

FROM localhost/poststack/base-debian:latest

# Install Apache and required modules
RUN apt-get update && apt-get install -y --no-install-recommends \
    apache2 \
    apache2-utils \
    libapache2-mod-php \
    php \
    php-pgsql \
    php-json \
    php-curl \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Enable Apache modules
RUN a2enmod rewrite ssl headers

# Create application directory
RUN mkdir -p /var/www/unified

# Copy configuration templates
COPY containers/apache/apache2.conf.template /etc/apache2/apache2.conf.template
COPY containers/apache/sites-available/unified.conf.template /etc/apache2/sites-available/unified.conf.template
COPY containers/apache/entrypoint.sh /entrypoint.sh

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
CMD ["apache2", "-D", "FOREGROUND"]
