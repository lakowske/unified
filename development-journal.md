# Development Journal

This document tracks significant issues, roadblocks, and solutions encountered during the unified infrastructure project development.

## Major Infrastructure Issues & Solutions

### 1. Poststack Migration System Reliability (July 2025)

**Issue**: Custom poststack migration system was unreliable with frequent tracking conflicts

- Migration tracking failed when tables already existed
- "relation 'users' already exists" errors prevented deployments
- Complex custom logic (4,738 lines) difficult to maintain and debug
- No industry-standard patterns or battle-tested reliability

**Root Cause**: Immature migration tracking system with poor conflict resolution

**Solution**: Complete replacement with Flyway

- Migrated to industry-standard Flyway database migrations
- Converted all migration files to Flyway naming convention (V1\_\_, V2\_\_, etc.)
- Eliminated 64% of custom code while improving reliability
- Migrations now complete in 0.061 seconds with zero conflicts

**Impact**: Major improvement in deployment reliability and maintenance burden

### 2. DNS Container Permission Issues (July 2025)

**Issue**: BIND DNS container stuck in restart loops due to permission problems

- `/var/cache/bind` directory not writable by bind user
- Configuration file access denied errors
- Container running as root instead of secure bind user
- Health checks failing due to service crashes

**Root Cause**: Incorrect permission setup and Docker/Podman compatibility issues

**Solution**: Fixed container permissions and user context

- Updated entrypoint script to properly set `/var/cache/bind` ownership
- Restored proper non-root execution as bind user with `-u bind` flag
- Fixed Dockerfile base image reference for Docker compatibility
- Rebuilt container with corrected permission handling

**Impact**: DNS service now stable and secure, resolving domains correctly

### 3. Podman Compose vs Docker Compose Compatibility (July 2025)

**Issue**: Init container dependencies not working properly with podman-compose

- `--profile` flag not supported in podman-compose version 1.0.6
- Service dependency resolution issues with init containers
- Complex workarounds required for proper startup ordering

**Root Cause**: Podman-compose lacks full Docker Compose feature parity

**Solution**: Migration to Docker Engine and Docker Compose

- Installed Docker Engine 28.3.2 and Docker Compose v2.38.2
- Imported all container images from Podman to Docker
- Updated test framework from podman-compose to docker compose
- Verified non-root container security preserved in Docker environment

**Impact**: Simplified orchestration with proper dependency management

### 4. Test Framework Container Runtime Transition (July 2025)

**Issue**: Comprehensive test suite built for podman-compose needed updating

- All test classes used podman-compose commands and containers
- Port conflicts between test environments and system services
- Test framework compatibility with new Docker environment

**Root Cause**: Infrastructure change required test framework updates

**Solution**: Complete test framework migration

- Updated all test classes from PodmanManager to DockerManager
- Changed command references from `podman-compose` to `docker compose`
- Fixed port mappings to avoid conflicts (DB_PORT=5433 for tests)
- Verified integration tests working with Docker Compose

**Impact**: Maintained comprehensive test coverage through infrastructure transition

## Build System Evolution

### 5. Container Build Dependency Management (July 2025)

**Issue**: Complex parallel build system needed poststack container removal

- Build scripts still referenced removed poststack-cli container
- Dependency chains needed updating after poststack elimination
- Container registry references required Docker compatibility

**Root Cause**: Build system coupled to removed poststack infrastructure

**Solution**: Build system cleanup and optimization

- Removed poststack-cli from build pipeline
- Updated container configurations for Docker registry
- Maintained parallel build efficiency for remaining containers
- Preserved dependency-aware building (base-debian → others)

**Impact**: Cleaner build process with fewer dependencies to maintain

## Key Lessons Learned

1. **Industry Standards Over Custom Solutions**: Replacing custom poststack with Flyway eliminated massive maintenance burden while improving reliability

1. **Container Security Consistency**: Non-root security can be maintained across different container runtimes with proper configuration

1. **Dependency Management Importance**: Proper service dependency chains are critical for reliable deployments

1. **Test Framework Resilience**: Comprehensive test coverage enables confident infrastructure transitions

1. **Documentation Value**: Clear development journals help track decisions and solutions for future reference

## Ongoing Considerations

- Monitor Flyway migration performance as schema complexity grows
- Consider DNS container optimization for larger zone files
- Evaluate container resource limits based on production usage patterns
- Plan for horizontal scaling of individual services as needed
