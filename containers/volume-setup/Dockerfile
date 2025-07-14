FROM localhost/poststack/base-debian:latest

# Install additional tools needed for volume setup
# Note: passwd package provides shadow utilities (useradd, groupadd, etc.)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        passwd \
    && rm -rf /var/lib/apt/lists/*

# Add certgroup with consistent GID across all containers
RUN groupadd -g 9999 certgroup || true

# Create setup script
COPY containers/volume-setup/setup-volumes.sh /usr/local/bin/setup-volumes.sh
RUN chmod +x /usr/local/bin/setup-volumes.sh

# Create UID mapping script
COPY containers/volume-setup/uid-mapping.sh /usr/local/bin/uid-mapping.sh
RUN chmod +x /usr/local/bin/uid-mapping.sh

ENTRYPOINT ["/usr/local/bin/setup-volumes.sh"]
