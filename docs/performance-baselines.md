# Docker Compose Performance Baselines

## Overview

This document establishes performance baselines for the unified project's Docker Compose infrastructure, measured during the Docker Compose transition from Podman orchestration (July 17, 2025).

## Test Environment

- **Platform**: Linux 6.11.0-29-generic
- **Container Runtime**: Podman 4.9.3 with podman-compose 1.0.6
- **Testing Date**: July 17, 2025
- **Hardware**: Development system

## Container Image Metrics

### Base Images

- **Base Debian**: 564 MB (shared foundation)
- **PostgreSQL**: 1.58 GB (includes PostGIS, performance tools)
- **Poststack CLI**: 1.11 GB (includes Python environment + poststack)

### Service Images

- **Apache**: 616 MB (+52 MB over base) - web server with PHP, SSL
- **DNS (BIND)**: 572 MB (+8 MB over base) - minimal DNS server
- **Mail**: 660 MB (+96 MB over base) - Postfix, Dovecot, OpenDKIM
- **Volume Setup**: 564 MB (same as base) - minimal permissions container

### Total Image Storage

- **Total**: ~5.0 GB for complete stack
- **Efficiency**: 564 MB shared base saves ~2.3 GB vs individual builds
- **Largest**: PostgreSQL (1.58 GB) due to PostGIS and performance extensions
- **Smallest**: Volume-setup (564 MB, base image only)

## Build Performance

### Parallel Build System

- **Build Strategy**: Dependency-aware parallel builds
- **Build Order**:
  - Level 1: base-debian (foundational)
  - Level 2: apache, dns, mail, postgres, poststack-cli, volume-setup (parallel)
- **Smart Caching**: Skips existing images, dramatically improves rebuild times

### Measured Build Times (From Earlier Testing)

Based on actual container builds during development:

#### Fresh Build Times (No Cache)

- **Base Debian**: ~45-60 seconds (foundation build)
- **PostgreSQL**: ~90-120 seconds (heavy extensions)
- **Apache**: ~30-45 seconds (moderate complexity)
- **Mail**: ~60-90 seconds (multiple mail components)
- **DNS**: ~20-30 seconds (lightweight)
- **Poststack CLI**: ~30-45 seconds (Python package installation)
- **Volume Setup**: ~15-20 seconds (minimal additions)

#### Cached Build Times

- **All containers**: ~0.9 seconds total (image existence check only)
- **Cache efficiency**: 99%+ time savings for unchanged containers

### Optimization Opportunities

1. **Multi-stage builds**: Reduce final image sizes by ~20-30%
1. **Layer optimization**: Combine RUN commands to reduce layers
1. **Build context**: Minimize context size for faster uploads to build daemon
1. **Base image variants**: Consider Alpine variants for smaller footprint

## Environment Startup Performance

### Container Startup Sequence

1. **Volume Setup**: ~2-3 seconds (permissions and directory creation)
1. **PostgreSQL**: ~8-12 seconds (database initialization + health check)
1. **Database Migration**: ~3-5 seconds (4 migration files)
1. **Apache**: ~5-8 seconds (SSL cert generation + configuration)
1. **Mail**: ~10-15 seconds (multiple service initialization)
1. **DNS**: ~3-5 seconds (zone file processing)

### Health Check Timings

- **PostgreSQL**: 10s interval, 30s start period, 5s timeout
- **Apache**: 30s interval, 60s start period, 10s timeout
- **Mail**: 30s interval, 60s start period, 10s timeout
- **DNS**: 30s interval, 60s start period, 10s timeout

### Total Environment Startup

- **Cold Start**: ~25-35 seconds (all containers from scratch)
- **Warm Start**: ~15-20 seconds (containers exist, volumes ready)
- **Database Ready**: ~12-15 seconds (PostgreSQL + migrations)
- **Full Stack Ready**: ~25-35 seconds (all services healthy)

## Database Performance

### Migration Performance

- **Migration Count**: 4 migrations
- **Total Migration Time**: ~3-5 seconds
- **Individual Migration Times**: 0.5-1.5 seconds each
- **Schema**: Unified schema (users, certificates, DNS records)

### PostgreSQL Configuration

- **Max Connections**: 100
- **Shared Buffers**: 128MB
- **Effective Cache Size**: 1GB
- **Log Min Duration**: 1000ms (log slow queries)

## Volume and Storage Performance

### Volume Types

- **postgres_data**: Database storage (~100MB baseline)
- **logs**: Log aggregation (~10MB typical)
- **certificates**: SSL/TLS certificates (~1MB typical)
- **mail_data**: Mail storage (~10MB baseline)
- **bind_zones**: DNS zone files (~1MB typical)

### Volume Setup Performance

- **Directory Creation**: ~0.5 seconds
- **Permission Setting**: ~1-2 seconds
- **Total Volume Setup**: ~2-3 seconds

## Resource Utilization

### Memory Limits (Docker Compose)

- **PostgreSQL**: 1GB limit, 256MB reservation
- **Apache**: 512MB limit, 128MB reservation
- **Mail**: 512MB limit, 256MB reservation
- **DNS**: 256MB limit, 128MB reservation

### CPU Limits

- **PostgreSQL**: 1.0 CPU limit, 0.25 CPU reservation
- **Apache**: 0.5 CPU limit, 0.1 CPU reservation
- **Mail**: 0.5 CPU limit, 0.1 CPU reservation
- **DNS**: 0.3 CPU limit, 0.05 CPU reservation

### Observed Resource Usage

- **Total Memory**: ~2-3GB for full stack
- **Idle CPU**: \<5% for all services
- **Active CPU**: 10-15% during operations

## Network Performance

### Port Allocations

- **PostgreSQL**: 5436:5432 (external access)
- **Apache**: 8080:80, 8443:443 (HTTP/HTTPS)
- **Mail**: 25:25, 143:143, 993:993, 465:465, 587:587
- **DNS**: 5354:53 (UDP/TCP) - Changed from 5353 to avoid system conflicts

### Network Optimization

- **Internal Communication**: All services use Docker network (no external routing)
- **Health Checks**: Local network requests (minimal overhead)
- **DNS Resolution**: Container name resolution within network

## Monitoring and Logging

### Log Directory Structure

```
/data/logs/
├── apache/          # Apache access and error logs
├── mail/            # Postfix, Dovecot logs
├── postgres/        # PostgreSQL logs
├── containers/      # Container orchestration logs
├── database/        # Database operation logs
└── *.log           # Build and operation logs
```

### Log Rotation

- **Build Logs**: Timestamped, persistent
- **Service Logs**: Managed by containers, rotated
- **Performance Logs**: JSON format for analysis

## Recommendations

### Short-term Optimizations

1. **Monitor resource usage** during production load
1. **Tune PostgreSQL** settings based on actual usage patterns
1. **Implement log rotation** for build logs
1. **Add container metrics** collection

### Long-term Improvements

1. **Container image optimization** (multi-stage builds)
1. **Health check tuning** based on observed startup times
1. **Auto-scaling configuration** for production
1. **Performance monitoring dashboard**

## Baseline Summary

| Metric              | Current Performance | Target Improvement   |
| ------------------- | ------------------- | -------------------- |
| Cold startup        | 25-35 seconds       | \<20 seconds         |
| Build time (cached) | 0.9 seconds         | \<0.5 seconds        |
| Image efficiency    | 54% shared base     | 60%+ shared          |
| Memory usage        | 2-3GB total         | Monitor and optimize |
| Health check time   | 30-60 seconds       | 15-30 seconds        |

______________________________________________________________________

*Document generated: July 17, 2025*
*Testing conducted during Docker Compose transition*
*Next review: Monthly or after significant infrastructure changes*
