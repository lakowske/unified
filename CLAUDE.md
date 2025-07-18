# Unified Infrastructure Project

## Project Purpose

A comprehensive containerized infrastructure project providing integrated mail, DNS, web, and database services using Docker Compose orchestration with industry-standard Flyway database migrations.

## Architecture Overview

### Core Components

- **Docker Compose** - Standard container orchestration with proper dependency management
- **Flyway** - Industry-standard database migration system (replaced custom poststack)
- **Shared Base Image** - `localhost/unified/base-debian:latest` for layer efficiency
- **Service Integration** - Mail (Postfix/Dovecot), DNS (BIND), Web (Apache), Database (PostgreSQL)

### Container Runtime

**✅ This project uses Docker Compose (migrated from Podman)**

- **Container runtime**: Docker Engine 28.3.2+
- **Orchestration**: `docker compose` command (Docker Compose v2.38.2+)
- **Migration system**: Flyway for enterprise-grade database migrations

## Development History

For detailed information about issues encountered and solutions implemented during development, see:

**[Development Journal](development-journal.md)** - Comprehensive record of roadblocks, solutions, and lessons learned throughout the project evolution.

**⚠️ IMPORTANT for Claude Code Sessions:**

Claude assistants MUST update `development-journal.md` whenever new roadblocks, issues, or significant challenges arise during development and testing. This ensures continuity across sessions and helps future development work learn from past solutions.

## Development Workflow

### Environment Management

**Standard Development Commands:**

```bash
# Start development environment
docker compose --env-file .env.dev -f docker-compose.yml -f docker-compose.dev.yml up -d

# Stop development environment
docker compose --env-file .env.dev -f docker-compose.yml -f docker-compose.dev.yml down

# View logs
docker compose --env-file .env.dev -f docker-compose.yml -f docker-compose.dev.yml logs [service]

# Check service status
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

**Environment Files:**

Environment-specific configurations using standard Docker Compose patterns:

- `.env.dev` - Development environment variables
- `.env.staging` - Staging environment variables
- `docker-compose.dev.yml` - Development overrides
- `docker-compose.yml` - Base service definitions

**Init Containers:**

Services can be run as needed using Docker Compose:

```bash
# Run volume setup
docker compose run --rm volume-setup

# Run database migrations
docker compose run --rm flyway
```

### Database Migration Workflow

**🚀 ENTERPRISE-GRADE: Flyway Database Migrations**

The project uses industry-standard Flyway for database schema management, providing enterprise-grade reliability and conflict resolution.

**Database Management:**

```bash
# Database operations (via Flyway)
docker compose run --rm flyway info        # Show migration status
docker compose run --rm flyway migrate     # Apply pending migrations
docker compose run --rm flyway validate    # Validate migration integrity
docker compose run --rm flyway baseline    # Baseline existing database
docker compose run --rm flyway repair      # Repair failed migrations

# Direct database access
docker compose exec postgres psql -U $DB_USER -d $DB_NAME
```

### Container Management

**Parallel Container Build System:**

The project includes an advanced parallel build system that respects dependencies and provides comprehensive logging:

```bash
# Build all containers with parallel processing and dependency management
./scripts/build.sh

# Check build dependencies
./scripts/build.sh --check

# Show help and features
./scripts/build.sh --help
```

**Build System Features:**

- ✅ **Dependency-aware parallel building** - Builds base image first, then all dependent containers in parallel
- ✅ **Comprehensive logging** - All build output saved to `logs/` directory with timestamps
- ✅ **Performance metrics** - Build timing, image sizes, and efficiency analysis
- ✅ **Smart caching** - Skips rebuild of existing images unless forced
- ✅ **Error handling** - Detailed error logs and graceful failure recovery
- ✅ **Build summaries** - JSON reports with complete build session details

**Build Order:**

1. **Level 1**: `base-debian` (shared foundation)
1. **Level 2**: `postgres`, `volume-setup`, `apache`, `mail`, `dns` (parallel)

**Manual Container Builds:**

```bash
# Build individual containers manually
docker build -f containers/apache/Dockerfile . -t localhost/unified/apache:latest
docker build -f containers/mail/Dockerfile . -t localhost/unified/mail:latest
docker build -f containers/dns/Dockerfile . -t localhost/unified/dns:latest
docker build -f containers/volume-setup/Dockerfile . -t localhost/unified/volume-setup:latest
docker build -f containers/postgres/Dockerfile . -t localhost/unified/postgres:latest
```

**Shared Base Image Architecture:**

All containers inherit from `localhost/unified/base-debian:latest` which includes:

- Debian Bookworm base with Python 3.11, pip, postgresql-client
- Virtual environment at `/data/.venv`
- Certificate management (certuser/certgroup)
- Standard directories (`/data/logs`, `/data/certificates`, `/data/config`)
- Common debugging tools (curl, wget, jq, etc.)

### Working Directory Context for Claude Code

**⚠️ Important for Claude Code Sessions:**

- This project is frequently edited by Claude Code assistants
- Claude Code maintains persistent working directory state across tool calls
- **Always verify your current working directory** before running context-dependent commands

**Best Practices:**

- Use `pwd` to check current working directory when troubleshooting
- Use absolute paths for critical operations: `/home/seth/Software/dev/unified/`
- Remember that `cd` commands in Claude Code **do** persist across tool calls

### Container Logging

**Log Storage:**

- All service logs stored in `/data/logs/` volume mount within containers
- Logs persist in named volumes: `logs-dev`, `logs-staging`, etc.

**Common Log Locations:**

- **Mail**: `/data/logs/mail/postfix.log`, `/data/logs/mail/dovecot-info.log`
- **Apache**: `/data/logs/apache/access.log`, `/data/logs/apache/error.log`
- **DNS**: `/data/logs/named/named.log`
- **Container runtime**: `/data/logs/container-runtime/`

**Viewing Logs:**

```bash
# View service logs via compose
docker compose --env-file .env.dev logs mail

# Direct container log access
docker exec mail-dev tail -20 /data/logs/mail/postfix.log
docker exec apache-dev tail -20 /data/logs/apache/error.log

# View volume contents
docker run --rm -v logs-dev:/logs alpine ls -la /logs/
```

## Performance Baselines

### Container Build Times (Clean Environment)

- **Base Image**: Pre-built (564 MB)
- **Flyway**: Lightweight official image (~100 MB)
- **Postgres**: 16.82s (1.58 GB)
- **Volume-setup**: 13.11s (564 MB)
- **Apache**: 44.63s (616 MB)
- **Mail**: ~90s (660 MB)
- **DNS**: 28.80s (572 MB)

### Environment Performance

- **Startup Time**: ~16-20 seconds (includes volume creation, networking, health checks)
- **Shutdown Time**: ~20-25 seconds (some services require SIGKILL after 10s timeout)
- **Shared Base Efficiency**: Significant layer reuse across all containers

## Container Naming & Volume Conventions

### Naming Patterns

- **Containers**: `{service}-{environment}` (e.g., `postgres-dev`, `apache-dev`)
- **Volumes**: `{volume-name}-{environment}` (e.g., `logs-dev`, `postgres-data-dev`)
- **Networks**: `{project}_default` (e.g., `unified_default`)

### Volume Management

```bash
# List all project volumes
docker volume ls | grep dev

# Remove environment volumes (careful - data loss!)
docker compose --env-file .env.dev down -v

# Backup important volumes
docker run --rm -v postgres-data-dev:/data -v $(pwd):/backup alpine \
  tar czf /backup/postgres-backup.tar.gz -C /data .
```

## Troubleshooting

### Common Issues

1. **Port Conflicts**: Check `.env.dev` for port assignments, avoid system ports
1. **Volume Permissions**: Ensure certuser/certgroup (UID/GID 9999) has proper access
1. **Health Check Failures**: Allow sufficient `start_period` for complex services
1. **DNS Resolution**: Bind service may conflict with host DNS on port 5353

### Debug Commands

```bash
# Check container health
docker inspect {container} --format='{{.State.Health.Status}}'

# Network connectivity test
docker exec postgres-dev pg_isready -h localhost -p 5432

# Service port check
docker exec mail-dev nc -z localhost 25 && echo "SMTP OK"

# Volume content inspection
docker run --rm -v {volume}:/mnt alpine ls -la /mnt
```

### Performance Optimization

1. **Graceful Shutdown**: Increase stop timeout for mail/apache containers
1. **Health Check Tuning**: Adjust intervals based on service startup time
1. **Resource Limits**: Monitor memory/CPU usage during development
1. **Layer Caching**: Rebuild containers in dependency order for optimal caching

## Migration Notes

### Infrastructure Evolution

- **Migration System**: Upgraded to industry-standard Flyway for enterprise-grade database management
- **Container Runtime**: Standardized on Docker Compose for universal compatibility and dependency management
- **Code Simplification**: Eliminated custom migration code in favor of proven industry standards
- **Reliability**: Resolved migration tracking conflicts and DNS container permission issues
- **Performance**: Migrations complete in milliseconds with zero conflicts using Flyway's proven algorithms
- **Security**: Maintained non-root container security throughout infrastructure
