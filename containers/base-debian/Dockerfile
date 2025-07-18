# Base Debian Container for Unified Project
# Provides shared foundation with Python, tools, and certificate management

FROM debian:bookworm-slim

# Install essential packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Python and pip
    python3 \
    python3-pip \
    python3-venv \
    # PostgreSQL client
    postgresql-client \
    # Common tools
    curl \
    wget \
    jq \
    openssl \
    ca-certificates \
    # Process monitoring
    htop \
    procps \
    # Network tools
    netcat-openbsd \
    dnsutils \
    # Text processing
    vim \
    less \
    grep \
    # Template processing
    gettext-base \
    # Build tools for Python packages
    build-essential \
    python3-dev \
    libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create unified user and group for certificate management
RUN groupadd -g 9999 certgroup && \
    useradd -u 9999 -g certgroup -m -s /bin/bash certuser

# Set up directory structure
RUN mkdir -p /data/logs /data/certificates /data/config && \
    chown -R certuser:certgroup /data && \
    chmod 755 /data /data/logs /data/certificates /data/config

# Create Python virtual environment
RUN python3 -m venv /data/.venv && \
    /data/.venv/bin/pip install --upgrade pip setuptools wheel && \
    chown -R certuser:certgroup /data/.venv

# Set environment variables
ENV PATH="/data/.venv/bin:$PATH"
ENV PYTHONPATH="/data"
ENV VIRTUAL_ENV="/data/.venv"

# Set working directory
WORKDIR /data

# Default command
CMD ["/bin/bash"]
