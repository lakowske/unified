# Poststack CLI Container
# Uses shared base image and installs simplified poststack from source
# Used as init container for database migrations and poststack operations

FROM localhost/poststack/base-debian:latest

# Set working directory
WORKDIR /app

# Copy simplified poststack source from build context
COPY . /app/poststack-src/

# Install poststack into existing virtual environment
# The base image already has Python 3.11, pip, postgresql-client, and build tools
RUN /data/.venv/bin/pip install --no-cache-dir /app/poststack-src/

# Set permissions - certuser already exists in base image
RUN chown -R certuser:certgroup /app

# Switch to non-root user for security
USER certuser

# Default working directory for migrations (mounted at runtime)
WORKDIR /app

# Default entrypoint uses the virtual environment python
ENTRYPOINT ["/data/.venv/bin/poststack"]
CMD ["--help"]
