# Transition from Poststack Podman to Docker Compose

## Executive Summary

The current poststack system has evolved into a complex reimplementation of Docker Compose using error-prone Podman Kubernetes YAML templates. This document outlines a complete architectural transition to standard Docker Compose, eliminating ~1750 lines of custom orchestration code and resolving persistent container termination issues.

## Current Architecture Problems

### 1. Complexity Overhead

- **Custom orchestration system**: 850+ lines in orchestrator.py
- **Template processing**: 300+ lines of Jinja2 substitution logic
- **Environment management**: 400+ lines for copying/isolation
- **Port allocation**: 200+ lines of custom port management
- **Total**: ~1750 lines of complex orchestration code

### 2. Known Issues

- **Podman kube down bug**: 1+ minute shutdown delays due to improper termination handling
- **Template debugging**: Complex Jinja2 error troubleshooting
- **Non-standard tooling**: Custom CLI commands instead of industry standards
- **Test complexity**: Custom test fixtures and environment management

### 3. Maintenance Burden

- Complex debugging for pod-specific issues
- Custom documentation for non-standard workflows
- Developer onboarding overhead
- CI/CD integration complexity

## Target Docker Compose Architecture

### 1. File Structure

```
docker-compose.yml              # Base services definition
docker-compose.dev.yml         # Development environment overrides
docker-compose.staging.yml     # Staging environment overrides
docker-compose.production.yml  # Production environment overrides
.env.dev                       # Development environment variables
.env.staging                   # Staging environment variables
.env.production               # Production environment variables
```

### 2. Service Definitions

#### PostgreSQL Service

```yaml
services:
  postgres:
    image: localhost/poststack/postgres:latest
    container_name: postgres-${ENVIRONMENT}
    environment:
      POSTGRES_DB: ${DB_NAME}
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_HOST_AUTH_METHOD: trust
      PGDATA: /data/postgres/data
    ports:
      - "${DB_PORT}:5432"
    volumes:
      - postgres_data:/data/postgres/data
      - logs:/data/logs
      - postgres_config:/data/postgres/config
    healthcheck:
      test: ["CMD", "pg_isready", "-h", "localhost", "-p", "5432"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped
```

#### Apache Service

```yaml
services:
  apache:
    image: localhost/unified/apache:latest
    container_name: apache-${ENVIRONMENT}
    depends_on:
      postgres:
        condition: service_healthy
      volume-setup:
        condition: service_completed_successfully
    environment:
      # Database connection
      DATABASE_URL: postgresql://${DB_USER}:${DB_PASSWORD}@postgres:5432/${DB_NAME}
      DB_HOST: postgres
      DB_PORT: 5432
      DB_NAME: ${DB_NAME}
      DB_USER: ${DB_USER}
      DB_PASSWORD: ${DB_PASSWORD}

      # Apache configuration
      APACHE_SERVER_NAME: ${SERVER_NAME}
      APACHE_SERVER_ADMIN: ${SERVER_ADMIN}
      APACHE_LOG_LEVEL: ${APACHE_LOG_LEVEL}
      SSL_ENABLED: ${SSL_ENABLED}
      SSL_REDIRECT: ${SSL_REDIRECT}

      # Application settings
      ENVIRONMENT: ${ENVIRONMENT}
      LOG_LEVEL: ${LOG_LEVEL}
      DEBUG_MODE: ${DEBUG_MODE}
      APP_VERSION: ${APP_VERSION}
    ports:
      - "${APACHE_HOST_PORT}:80"
      - "${APACHE_HTTPS_PORT}:443"
    volumes:
      - logs:/data/logs
      - certificates:/data/certificates
      - apache_config:/etc/apache2/conf.d
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped
```

#### Mail Service

```yaml
services:
  mail:
    image: localhost/unified/mail:latest
    container_name: mail-${ENVIRONMENT}
    depends_on:
      postgres:
        condition: service_healthy
      volume-setup:
        condition: service_completed_successfully
    environment:
      # Database connection
      DB_HOST: postgres
      DB_PORT: 5432
      DB_NAME: ${DB_NAME}
      DB_USER: ${DB_USER}
      DB_PASSWORD: ${DB_PASSWORD}

      # Mail configuration
      MAIL_DOMAIN: ${MAIL_DOMAIN}
      MAIL_LOG_LEVEL: ${MAIL_LOG_LEVEL}
      VMAIL_UID: ${VMAIL_UID}
      VMAIL_GID: ${VMAIL_GID}

      # Environment settings
      ENVIRONMENT: ${ENVIRONMENT}
      SSL_ENABLED: ${SSL_ENABLED}
    ports:
      - "${MAIL_SMTP_PORT}:25"
      - "${MAIL_IMAP_PORT}:143"
      - "${MAIL_IMAPS_PORT}:993"
      - "${MAIL_SMTPS_PORT}:465"
      - "${MAIL_SUBMISSION_PORT}:587"
    volumes:
      - mail_data:/var/mail
      - logs:/data/logs
      - mail_config:/etc/dovecot/conf.d
      - certificates:/data/certificates
    restart: unless-stopped
```

#### Bind Service

```yaml
services:
  bind:
    image: localhost/unified/dns:latest
    container_name: bind-${ENVIRONMENT}
    depends_on:
      postgres:
        condition: service_healthy
      volume-setup:
        condition: service_completed_successfully
    environment:
      # Database connection
      DB_HOST: postgres
      DB_PORT: 5432
      DB_NAME: ${DB_NAME}
      DB_USER: ${DB_USER}
      DB_PASSWORD: ${DB_PASSWORD}

      # DNS configuration
      DNS_LOG_LEVEL: ${DNS_LOG_LEVEL}
      DNS_FORWARDERS: ${DNS_FORWARDERS}
      DNS_ALLOW_QUERY: ${DNS_ALLOW_QUERY}
      DNS_RECURSION: ${DNS_RECURSION}
      DNS_CACHE_SIZE: ${DNS_CACHE_SIZE}
      DNS_MAX_CACHE_TTL: ${DNS_MAX_CACHE_TTL}

      # Mail domain settings
      MAIL_DOMAIN: ${MAIL_DOMAIN}
      MAIL_SERVER_IP: ${MAIL_SERVER_IP}

      # Environment settings
      ENVIRONMENT: ${ENVIRONMENT}
    ports:
      - "${BIND_PORT}:53/udp"
      - "${BIND_PORT}:53/tcp"
    volumes:
      - bind_zones:/data/dns/zones
      - logs:/data/logs
    restart: unless-stopped
```

#### Volume Setup Service

```yaml
services:
  volume-setup:
    image: localhost/unified/volume-setup:latest
    container_name: volume-setup-${ENVIRONMENT}
    environment:
      ENVIRONMENT: ${ENVIRONMENT}
    volumes:
      - logs:/data/logs
      - certificates:/data/certificates
      - mail_data:/var/mail
      - bind_zones:/data/dns/zones
    restart: "no"  # Run once like init container
    profiles:
      - init  # Only run when explicitly requested
```

### 3. Volume Definitions

```yaml
volumes:
  postgres_data:
    name: postgres-data-${ENVIRONMENT}
  logs:
    name: logs-${ENVIRONMENT}
  certificates:
    name: certificates-${ENVIRONMENT}
  mail_data:
    name: mail-data-${ENVIRONMENT}
  bind_zones:
    name: bind-zones-${ENVIRONMENT}
  postgres_config:
  apache_config:
  mail_config:
```

### 4. Environment-Specific Overrides

#### Development Override (docker-compose.dev.yml)

```yaml
services:
  postgres:
    ports:
      - "5436:5432"  # Dev-specific port
    environment:
      POSTGRES_DB: unified_dev
      POSTGRES_USER: unified_dev_user
      POSTGRES_PASSWORD: dev_password123

  apache:
    ports:
      - "8080:80"
      - "8443:443"
    environment:
      APACHE_LOG_LEVEL: debug
      DEBUG_MODE: "true"

  mail:
    ports:
      - "2525:25"
      - "1144:143"
      - "9933:993"
      - "4465:465"
      - "5587:587"
    environment:
      MAIL_LOG_LEVEL: debug
```

#### Production Override (docker-compose.production.yml)

```yaml
services:
  postgres:
    ports:
      - "5435:5432"
    environment:
      POSTGRES_DB: unified_prod
      POSTGRES_USER: unified_prod_user
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '1.0'
        reservations:
          memory: 1G
          cpus: '0.5'

  apache:
    ports:
      - "80:80"
      - "443:443"
    environment:
      APACHE_LOG_LEVEL: warn
      DEBUG_MODE: "false"
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
```

## Environment Variable Strategy

### Development (.env.dev)

```bash
ENVIRONMENT=dev
COMPOSE_PROJECT_NAME=poststack-dev

# Database
DB_NAME=unified_dev
DB_USER=unified_dev_user
DB_PASSWORD=dev_password123
DB_PORT=5436

# Apache
APACHE_HOST_PORT=8080
APACHE_HTTPS_PORT=8443
APACHE_LOG_LEVEL=debug
SERVER_NAME=lab.sethlakowske.com
SERVER_ADMIN=lakowske@gmail.com
SSL_ENABLED=true
SSL_REDIRECT=false

# Mail
MAIL_DOMAIN=lab.sethlakowske.com
MAIL_LOG_LEVEL=debug
MAIL_SMTP_PORT=2525
MAIL_IMAP_PORT=1144
MAIL_IMAPS_PORT=9933
MAIL_SMTPS_PORT=4465
MAIL_SUBMISSION_PORT=5587
VMAIL_UID=5000
VMAIL_GID=5000
MAIL_SERVER_IP=192.168.0.156

# Bind DNS
DNS_LOG_LEVEL=info
DNS_FORWARDERS=8.8.8.8;8.8.4.4;1.1.1.1;1.0.0.1
DNS_ALLOW_QUERY=any
DNS_RECURSION=yes
DNS_CACHE_SIZE=100m
DNS_MAX_CACHE_TTL=3600
BIND_PORT=5353

# Application
LOG_LEVEL=debug
DEBUG_MODE=true
APP_VERSION=dev-latest
```

### Staging (.env.staging)

```bash
ENVIRONMENT=staging
COMPOSE_PROJECT_NAME=poststack-staging

# Database
DB_NAME=unified_staging
DB_USER=unified_staging_user
DB_PASSWORD=dev_password123
DB_PORT=5434

# Apache
APACHE_HOST_PORT=8081
APACHE_HTTPS_PORT=8444
APACHE_LOG_LEVEL=info
SERVER_NAME=staging.unified.local
SERVER_ADMIN=staging@unified.local
SSL_ENABLED=true
SSL_REDIRECT=false

# Application
LOG_LEVEL=info
DEBUG_MODE=false
APP_VERSION=staging-0.1.0
```

## CLI Command Mapping

### Current Poststack Commands → Docker Compose Equivalents

| Current Command                            | Docker Compose Equivalent                           |
| ------------------------------------------ | --------------------------------------------------- |
| `poststack env start dev`                  | `docker compose --env-file .env.dev up -d`          |
| `poststack env stop dev --rm`              | `docker compose --env-file .env.dev down -v`        |
| `poststack env restart dev`                | `docker compose --env-file .env.dev restart`        |
| `poststack env status dev`                 | `docker compose --env-file .env.dev ps`             |
| `poststack env logs dev apache`            | `docker compose --env-file .env.dev logs apache`    |
| `poststack env start-service dev postgres` | `docker compose --env-file .env.dev up postgres -d` |
| `poststack env stop-service dev postgres`  | `docker compose --env-file .env.dev stop postgres`  |

### New Simplified CLI Commands

```bash
# Start environment with volume initialization
poststack up dev                    # docker compose --env-file .env.dev --profile init up -d

# Stop environment and clean volumes
poststack down dev                  # docker compose --env-file .env.dev down -v

# Restart environment
poststack restart dev               # docker compose --env-file .env.dev restart

# View logs
poststack logs dev apache           # docker compose --env-file .env.dev logs apache

# Start specific service
poststack start dev postgres        # docker compose --env-file .env.dev up postgres -d

# Environment status
poststack status dev                # docker compose --env-file .env.dev ps
```

## Migration Implementation Plan

### Phase 1: Parallel Implementation (Week 1)

1. **Create Docker Compose files** alongside existing pod templates
1. **Test environment parity** between pod and compose deployments
1. **Verify all services work correctly** with compose
1. **Document any behavioral differences**

### Phase 2: CLI Bridge (Week 2)

1. **Add compose commands to poststack CLI** as alternatives
1. **Implement environment detection** (pod vs compose)
1. **Provide migration utilities** to convert environments
1. **Update documentation** with compose examples

### Phase 3: Full Transition (Week 3)

1. **Replace orchestrator calls** with compose commands
1. **Remove pod templates and Jinja2 system**
1. **Clean up legacy code** (orchestrator, environment manager, port allocator)
1. **Update all documentation** to compose-first approach

### Phase 4: Cleanup (Week 4)

1. **Remove unused dependencies** (Jinja2, YAML processing)
1. **Simplify CLI implementation**
1. **Add compose-specific enhancements**
1. **Performance testing and optimization**

## Benefits Analysis

### Immediate Improvements

- **Eliminate 1+ minute shutdown delays** (Podman kube down bug)
- **Standard industry tooling** - Docker Compose is universally understood
- **Simplified debugging** - standard compose logs, ps, exec commands
- **Faster development cycles** - no template processing overhead

### Code Reduction

- **Remove ~1750 lines** of custom orchestration code
- **Replace with ~300 lines** of declarative YAML configuration
- **85% reduction in codebase complexity**
- **Eliminate entire modules**: orchestrator, environment_manager, port_allocator, substitution

### Developer Experience

- **Easier onboarding** - developers already know Docker Compose
- **Better debugging tools** - standard compose commands
- **Simplified testing** - compose test patterns are well-established
- **CI/CD ready** - native support in all major platforms

### Maintenance Benefits

- **Reduced bug surface** - rely on mature Docker Compose instead of custom code
- **Community support** - extensive Docker Compose documentation and examples
- **Future-proof** - Docker Compose is industry standard with active development
- **Easier contributions** - lower barrier to understanding and modifying

## Risk Mitigation

### Compatibility Concerns

- **Container images remain unchanged** - only orchestration changes
- **Environment variables preserved** - same configuration interface
- **Volume mappings maintained** - data persistence guaranteed
- **Port mappings preserved** - external interfaces unchanged

### Rollback Strategy

- **Keep pod templates temporarily** until compose is validated
- **Implement environment detection** to support both systems
- **Gradual migration** with ability to revert per environment
- **Comprehensive testing** before removing legacy code

### Testing Strategy

- **Parallel testing** of pod vs compose environments
- **Service-by-service validation** of functionality parity
- **Performance benchmarking** to ensure no regressions
- **Integration testing** with external systems

## Success Metrics

### Technical Metrics

- **Startup time**: Target \<5 seconds for full environment (currently achieved)
- **Shutdown time**: Target \<10 seconds (currently 1+ minutes)
- **Code complexity**: Reduce from 1750 to \<300 lines
- **Memory usage**: Reduce CLI overhead

### Operational Metrics

- **Developer onboarding time**: Reduce by eliminating custom tooling learning
- **Debug time**: Reduce with standard compose tooling
- **CI/CD setup time**: Reduce with native compose support
- **Documentation maintenance**: Reduce with standard patterns

This transition represents a fundamental simplification of the poststack architecture, eliminating custom orchestration complexity while gaining industry-standard tooling and resolving persistent container lifecycle issues.
