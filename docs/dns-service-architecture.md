# DNS Service Architecture

## Overview

The DNS service provides authoritative DNS resolution for mail domains with integrated PostgreSQL backend for dynamic record management. This document covers the architecture, components, and operational aspects of the DNS service.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            DNS Service Architecture                             │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐           │
│  │   DNS Clients   │    │   DNS Queries   │    │   DNS Response  │           │
│  │                 │───►│                 │───►│                 │           │
│  │ • dig           │    │ • A Records     │    │ • Authoritative │           │
│  │ • nslookup      │    │ • MX Records    │    │ • Cached        │           │
│  │ • Mail Servers  │    │ • TXT Records   │    │ • Forwarded     │           │
│  │ • Web Browsers  │    │ • DKIM/SPF/DMARC│    │                 │           │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘           │
│                                │                                               │
│                                ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                      BIND 9 DNS Server                                 │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐      │   │
│  │  │  Zone Files     │  │  Configuration  │  │  Query Engine   │      │   │
│  │  │                 │  │                 │  │                 │      │   │
│  │  │ • Static Zones  │  │ • named.conf    │  │ • Recursive     │      │   │
│  │  │ • Dynamic Zones │  │ • Forwarders    │  │ • Authoritative │      │   │
│  │  │ • Mail Domain   │  │ • Security      │  │ • Caching       │      │   │
│  │  │ • DNSSEC        │  │ • Logging       │  │                 │      │   │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘      │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                │                                               │
│                                ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                    Database Integration                                 │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐      │   │
│  │  │  DNS Records    │  │  Zone Management│  │  Change Tracking│      │   │
│  │  │                 │  │                 │  │                 │      │   │
│  │  │ • dns_records   │  │ • dns_zones     │  │ • Triggers      │      │   │
│  │  │ • Dynamic Data  │  │ • Serial Numbers│  │ • Notifications │      │   │
│  │  │ • TTL Management│  │ • SOA Records   │  │ • Audit Logs    │      │   │
│  │  │ • Validation    │  │ • Validation    │  │                 │      │   │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘      │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                │                                               │
│                                ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                      Management Scripts                                │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐      │   │
│  │  │  DKIM Manager   │  │  Zone Generator │  │  Health Checker │      │   │
│  │  │                 │  │                 │  │                 │      │   │
│  │  │ • Key Updates   │  │ • Template Proc │  │ • Query Testing │      │   │
│  │  │ • DNS Propagate │  │ • File Generation│  │ • Performance   │      │   │
│  │  │ • Validation    │  │ • Reload Trigger│  │ • Monitoring    │      │   │
│  │  │                 │  │                 │  │                 │      │   │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘      │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Component Overview

### 1. BIND 9 DNS Server

**Purpose**: Authoritative DNS server for mail domains with caching and forwarding capabilities.

**Key Features**:

- Authoritative zones for mail domains
- Recursive query resolution
- DNS caching with configurable TTL
- Query forwarding to upstream servers
- Security features (rate limiting, access control)
- Comprehensive logging and monitoring

**Configuration Files**:

- `named.conf` - Main configuration
- `named.conf.options` - Server behavior settings
- `named.conf.local` - Local zone definitions
- Zone files in `/data/zones/`

### 2. PostgreSQL Database Backend

**Purpose**: Dynamic storage and management of DNS records with versioning and change tracking.

**Key Features**:

- Structured DNS record storage
- Zone metadata management
- Serial number tracking
- Change notifications via PostgreSQL LISTEN/NOTIFY
- Audit logging and history
- Validation and constraints

**Database Schema**:

- `dns_records` - Individual DNS records
- `dns_zones` - Zone metadata and settings
- Triggers for automatic serial number updates
- Views for mail service integration

### 3. Zone Management System

**Purpose**: Template-based zone file generation with dynamic content integration.

**Key Features**:

- Jinja2 template processing
- Environment variable substitution
- Dynamic record insertion
- Zone file validation
- Automatic reload triggering

**Template Structure**:

```
containers/dns/zones/
├── mail-domain.zone.template    # Main mail domain template
├── reverse-zone.template        # Reverse DNS template
└── custom-zones/               # Custom zone templates
```

### 4. DKIM Integration

**Purpose**: Automated DKIM key management and DNS record propagation.

**Key Features**:

- DKIM key generation monitoring
- Automatic DNS record updates
- Key rotation support
- Validation and verification
- Cross-service coordination

**Integration Points**:

- Mail server DKIM key generation
- Database record updates
- DNS zone file modifications
- Service reload coordination

## DNS Record Types and Management

### Authoritative Records

#### A Records

```dns
lab.sethlakowske.com.    IN    A    192.168.0.156
mail.lab.sethlakowske.com.    IN    A    192.168.0.156
```

#### MX Records

```dns
lab.sethlakowske.com.    IN    MX    10 mail.lab.sethlakowske.com.
```

#### TXT Records (Mail Authentication)

```dns
; SPF Record
lab.sethlakowske.com.    IN    TXT    "v=spf1 a mx ip4:192.168.0.156 include:_spf.google.com ~all"

; DMARC Record
_dmarc.lab.sethlakowske.com.    IN    TXT    "v=DMARC1; p=quarantine; rua=mailto:dmarc@lab.sethlakowske.com; ruf=mailto:dmarc@lab.sethlakowske.com; sp=quarantine; aspf=r; adkim=r; rf=afrf; fo=1"

; DKIM Record (Dynamic)
mail._domainkey.lab.sethlakowske.com.    IN    TXT    "v=DKIM1; h=sha256; k=rsa; p=<public-key>"
```

### Dynamic Records

Dynamic records are managed through the PostgreSQL database and automatically propagated to zone files.

#### Database-Managed Records

```sql
-- Example dynamic record insertion
INSERT INTO unified.dns_records (domain, name, type, value, ttl) VALUES
('lab.sethlakowske.com', 'mail', 'A', '192.168.0.156', 3600),
('lab.sethlakowske.com', '@', 'MX', '10 mail.lab.sethlakowske.com', 3600),
('lab.sethlakowske.com', 'mail._domainkey', 'TXT', 'v=DKIM1; k=rsa; p=<key>', 3600);
```

#### Automatic Updates

Records are automatically updated when:

- DKIM keys are generated or rotated
- IP addresses change
- Mail server configuration changes
- Certificate renewal occurs

## Security Architecture

### Access Control

#### Network Security

- DNS queries restricted to configured networks
- Rate limiting to prevent abuse
- DDoS protection mechanisms
- Secure zone transfer restrictions

#### Database Security

- Encrypted database connections
- Role-based access control
- Audit logging of all changes
- Backup and recovery procedures

### DNS Security Features

#### DNSSEC (Future Enhancement)

- Zone signing capabilities
- Key management infrastructure
- Validation chain maintenance
- Automated key rollover

#### Query Security

- Response rate limiting
- Query source validation
- Cache poisoning protection
- Secure forwarding configuration

## Performance and Monitoring

### Performance Optimization

#### Caching Strategy

```conf
# Cache configuration
max-cache-size 100m;
max-cache-ttl 3600;
min-cache-ttl 300;
```

#### Query Optimization

- Efficient database queries
- Connection pooling
- Index optimization
- Query result caching

### Monitoring and Metrics

#### Health Checks

```bash
# DNS health check
dig @localhost -p 53 lab.sethlakowske.com A
dig @localhost -p 53 lab.sethlakowske.com MX
dig @localhost -p 53 _dmarc.lab.sethlakowske.com TXT
```

#### Performance Metrics

- Query response times
- Cache hit rates
- Database connection metrics
- Zone update frequency

#### Logging and Alerting

- Comprehensive query logging
- Error rate monitoring
- Performance threshold alerts
- Capacity planning metrics

## Operational Procedures

### Deployment Process

#### Container Deployment

```bash
# Build DNS container
poststack build dns

# Deploy environment
poststack env start dev

# Verify deployment
poststack env status dev
```

#### Configuration Updates

1. Update configuration files
1. Validate configuration
1. Rebuild container
1. Rolling deployment
1. Verification testing

### Maintenance Tasks

#### Regular Maintenance

- Log rotation and cleanup
- Database vacuum and reindex
- Cache optimization
- Performance monitoring

#### Emergency Procedures

- DNS server failover
- Zone file recovery
- Database backup restoration
- Service dependency management

### Troubleshooting Guide

#### Common Issues

**DNS Resolution Failures**

```bash
# Check DNS server status
podman logs unified-dns-dev-dns-server-dns-server

# Test basic resolution
dig @localhost -p 53 . NS

# Verify configuration
named-checkconf /etc/bind/named.conf
```

**Database Connection Issues**

```bash
# Check database connectivity
psql -h localhost -p 5436 -U unified_dev_user -d unified_dev \
  -c "SELECT COUNT(*) FROM unified.dns_records;"

# Verify DNS records
psql -h localhost -p 5436 -U unified_dev_user -d unified_dev \
  -c "SELECT * FROM unified.dns_records WHERE domain = 'lab.sethlakowske.com';"
```

**Performance Issues**

```bash
# Monitor query performance
dig @localhost -p 53 lab.sethlakowske.com A +stats

# Check cache utilization
rndc stats
```

### Integration Testing

#### Automated Tests

```bash
# Run DNS integration tests
python tests/run_dns_mail_tests.py --verbose --report

# Run specific test suites
python tests/run_dns_mail_tests.py --performance
python tests/run_dns_mail_tests.py --integration
```

#### Manual Validation

```bash
# Test mail domain resolution
dig @localhost -p 53 lab.sethlakowske.com A MX TXT

# Test DMARC resolution
dig @localhost -p 53 _dmarc.lab.sethlakowske.com TXT

# Test performance
time dig @localhost -p 53 lab.sethlakowske.com A
```

## Configuration Management

### Environment Variables

#### DNS Service Configuration

```yaml
dns:
  variables:
    DNS_LOG_LEVEL: info
    DNS_FORWARDERS: "8.8.8.8;8.8.4.4;1.1.1.1;1.0.0.1"
    DNS_ALLOW_QUERY: "any"
    DNS_RECURSION: "yes"
    DNS_CACHE_SIZE: "100m"
    DNS_MAX_CACHE_TTL: "3600"
    MAIL_DOMAIN: lab.sethlakowske.com
    MAIL_SERVER_IP: "192.168.0.156"
```

#### Database Configuration

```yaml
dns:
  variables:
    DB_HOST: "localhost"
    DB_PORT: "5436"
    DB_NAME: unified_dev
    DB_USER: unified_dev_user
    DB_PASSWORD: "dev_password123"
```

### Volume Management

#### Persistent Storage

```yaml
volumes:
  dns_zones:
    type: named
    size: "1GB"
    description: "DNS zone files and cache"

  dns_logs:
    type: named
    size: "500MB"
    description: "DNS server logs"
```

#### Backup Strategy

- Daily zone file backups
- Database record exports
- Configuration file versioning
- Automated backup verification

## Future Enhancements

### Planned Features

#### DNSSEC Implementation

- Zone signing infrastructure
- Key management automation
- Validation chain maintenance
- Automated key rollover

#### Enhanced Monitoring

- Real-time performance dashboards
- Predictive alerting
- Capacity planning tools
- Integration with monitoring systems

#### High Availability

- Multi-server DNS setup
- Load balancing
- Failover automation
- Geographic distribution

### API Integration

#### REST API for DNS Management

```python
# Example API endpoints
POST /api/dns/records          # Create DNS record
GET  /api/dns/records/{domain} # Get domain records
PUT  /api/dns/records/{id}     # Update DNS record
DELETE /api/dns/records/{id}   # Delete DNS record
```

#### GraphQL Interface

```graphql
type DNSRecord {
    id: ID!
    domain: String!
    name: String!
    type: String!
    value: String!
    ttl: Int!
    created_at: DateTime!
    updated_at: DateTime!
}

type Query {
    dnsRecords(domain: String!): [DNSRecord]
    dnsRecord(id: ID!): DNSRecord
}

type Mutation {
    createDNSRecord(input: DNSRecordInput!): DNSRecord
    updateDNSRecord(id: ID!, input: DNSRecordInput!): DNSRecord
    deleteDNSRecord(id: ID!): Boolean
}
```

This DNS service architecture provides a robust, scalable, and secure foundation for mail domain DNS management with comprehensive monitoring, automation, and integration capabilities.
