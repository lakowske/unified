# PostgreSQL DNS Schema Documentation

## Overview

This document describes the PostgreSQL database schema for DNS record management in the unified project. The schema supports dynamic DNS record management, zone configuration, and integration with mail services.

## Database Schema Architecture

### Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         PostgreSQL DNS Schema                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐  │
│  │   dns_zones     │         │   dns_records   │         │   dns_history   │  │
│  │                 │         │                 │         │                 │  │
│  │ • id (PK)       │────────►│ • id (PK)       │────────►│ • id (PK)       │  │
│  │ • domain (UK)   │         │ • domain (FK)   │         │ • record_id (FK)│  │
│  │ • serial_number │         │ • name          │         │ • action        │  │
│  │ • refresh_int   │         │ • type          │         │ • old_value     │  │
│  │ • retry_int     │         │ • value         │         │ • new_value     │  │
│  │ • expire_int    │         │ • ttl           │         │ • changed_at    │  │
│  │ • minimum_ttl   │         │ • priority      │         │ • changed_by    │  │
│  │ • primary_ns    │         │ • created_at    │         │                 │  │
│  │ • admin_email   │         │ • updated_at    │         │                 │  │
│  │ • created_at    │         │ • is_active     │         │                 │  │
│  │ • updated_at    │         │                 │         │                 │  │
│  │ • is_active     │         │                 │         │                 │  │
│  └─────────────────┘         └─────────────────┘         └─────────────────┘  │
│                                        │                                        │
│                                        ▼                                        │
│  ┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐  │
│  │  certificates   │         │service_certificates│      │   dns_views     │  │
│  │                 │         │                 │         │                 │  │
│  │ • id (PK)       │────────►│ • id (PK)       │         │ • domain        │  │
│  │ • domain        │         │ • service_name  │         │ • record_type   │  │
│  │ • cert_type     │         │ • domain        │         │ • record_count  │  │
│  │ • cert_data     │         │ • cert_type     │         │ • last_updated  │  │
│  │ • private_key   │         │ • ssl_enabled   │         │                 │  │
│  │ • cert_chain    │         │ • cert_path     │         │                 │  │
│  │ • created_at    │         │ • last_updated  │         │                 │  │
│  │ • expires_at    │         │ • is_active     │         │                 │  │
│  │ • is_active     │         │                 │         │                 │  │
│  └─────────────────┘         └─────────────────┘         └─────────────────┘  │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Core Tables

### dns_zones

**Purpose**: Stores DNS zone metadata and configuration settings.

```sql
CREATE TABLE unified.dns_zones (
    id SERIAL PRIMARY KEY,
    domain VARCHAR(255) NOT NULL UNIQUE,
    serial_number BIGINT NOT NULL DEFAULT 2025071501,
    refresh_interval INTEGER DEFAULT 3600,
    retry_interval INTEGER DEFAULT 1800,
    expire_interval INTEGER DEFAULT 604800,
    minimum_ttl INTEGER DEFAULT 3600,
    primary_ns VARCHAR(255) NOT NULL,
    admin_email VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);
```

**Key Features**:

- Unique domain constraint
- SOA record parameters
- Automatic serial number management
- Timestamped records
- Soft delete capability

**Indexes**:

```sql
CREATE INDEX idx_dns_zones_domain ON unified.dns_zones(domain);
CREATE INDEX idx_dns_zones_active ON unified.dns_zones(is_active);
CREATE INDEX idx_dns_zones_updated ON unified.dns_zones(updated_at);
```

### dns_records

**Purpose**: Stores individual DNS records with support for all standard record types.

```sql
CREATE TABLE unified.dns_records (
    id SERIAL PRIMARY KEY,
    domain VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(10) NOT NULL,
    value TEXT NOT NULL,
    ttl INTEGER DEFAULT 3600,
    priority INTEGER DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);
```

**Key Features**:

- Flexible record type support
- Priority field for MX records
- Text value storage for complex records
- TTL per record
- Soft delete capability

**Constraints**:

```sql
-- Unique constraint for active records
CREATE UNIQUE INDEX idx_dns_records_unique
ON unified.dns_records(domain, name, type)
WHERE is_active = TRUE;

-- Foreign key to dns_zones
ALTER TABLE unified.dns_records
ADD CONSTRAINT fk_dns_records_domain
FOREIGN KEY (domain) REFERENCES unified.dns_zones(domain)
ON DELETE CASCADE;
```

**Indexes**:

```sql
CREATE INDEX idx_dns_records_domain ON unified.dns_records(domain);
CREATE INDEX idx_dns_records_type ON unified.dns_records(type);
CREATE INDEX idx_dns_records_name ON unified.dns_records(name);
CREATE INDEX idx_dns_records_active ON unified.dns_records(is_active);
```

### dns_history

**Purpose**: Audit trail for DNS record changes.

```sql
CREATE TABLE unified.dns_history (
    id SERIAL PRIMARY KEY,
    record_id INTEGER REFERENCES unified.dns_records(id),
    action VARCHAR(10) NOT NULL, -- INSERT, UPDATE, DELETE
    old_value JSONB,
    new_value JSONB,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    changed_by VARCHAR(255) DEFAULT 'system'
);
```

**Key Features**:

- Complete audit trail
- JSONB storage for flexible data
- Action tracking
- User attribution
- Timestamp tracking

**Indexes**:

```sql
CREATE INDEX idx_dns_history_record_id ON unified.dns_history(record_id);
CREATE INDEX idx_dns_history_changed_at ON unified.dns_history(changed_at);
CREATE INDEX idx_dns_history_action ON unified.dns_history(action);
```

## Database Functions and Triggers

### Serial Number Management

**Purpose**: Automatically update zone serial numbers when records change.

```sql
-- Function to update DNS zone serial number
CREATE OR REPLACE FUNCTION unified.update_dns_zone_serial()
RETURNS TRIGGER AS $$
BEGIN
    -- Update serial number to current timestamp
    UPDATE unified.dns_zones
    SET serial_number = EXTRACT(epoch FROM CURRENT_TIMESTAMP)::bigint,
        updated_at = CURRENT_TIMESTAMP
    WHERE domain = COALESCE(NEW.domain, OLD.domain);

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- Trigger for DNS record changes
CREATE TRIGGER dns_record_update_trigger
    AFTER INSERT OR UPDATE OR DELETE ON unified.dns_records
    FOR EACH ROW
    EXECUTE FUNCTION unified.update_dns_zone_serial();
```

### Change Notifications

**Purpose**: Notify external systems of DNS record changes.

```sql
-- Function to send change notifications
CREATE OR REPLACE FUNCTION unified.notify_dns_change()
RETURNS TRIGGER AS $$
BEGIN
    -- Send notification with domain and record type
    PERFORM pg_notify(
        'dns_change',
        COALESCE(NEW.domain, OLD.domain) || ':' || COALESCE(NEW.type, OLD.type)
    );

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- Trigger for DNS change notifications
CREATE TRIGGER dns_change_notification_trigger
    AFTER INSERT OR UPDATE OR DELETE ON unified.dns_records
    FOR EACH ROW
    EXECUTE FUNCTION unified.notify_dns_change();
```

### History Tracking

**Purpose**: Maintain audit trail of all DNS record changes.

```sql
-- Function to track DNS record history
CREATE OR REPLACE FUNCTION unified.track_dns_history()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO unified.dns_history (record_id, action, new_value)
        VALUES (NEW.id, 'INSERT', to_jsonb(NEW));
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO unified.dns_history (record_id, action, old_value, new_value)
        VALUES (NEW.id, 'UPDATE', to_jsonb(OLD), to_jsonb(NEW));
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO unified.dns_history (record_id, action, old_value)
        VALUES (OLD.id, 'DELETE', to_jsonb(OLD));
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Trigger for DNS history tracking
CREATE TRIGGER dns_history_trigger
    AFTER INSERT OR UPDATE OR DELETE ON unified.dns_records
    FOR EACH ROW
    EXECUTE FUNCTION unified.track_dns_history();
```

## Database Views

### dns_summary

**Purpose**: Provides summary statistics for DNS zones and records.

```sql
CREATE VIEW unified.dns_summary AS
SELECT
    z.domain,
    z.serial_number,
    z.updated_at as zone_updated,
    COUNT(r.id) as record_count,
    COUNT(CASE WHEN r.type = 'A' THEN 1 END) as a_records,
    COUNT(CASE WHEN r.type = 'MX' THEN 1 END) as mx_records,
    COUNT(CASE WHEN r.type = 'TXT' THEN 1 END) as txt_records,
    COUNT(CASE WHEN r.type = 'CNAME' THEN 1 END) as cname_records,
    MAX(r.updated_at) as last_record_update
FROM unified.dns_zones z
LEFT JOIN unified.dns_records r ON z.domain = r.domain AND r.is_active = TRUE
WHERE z.is_active = TRUE
GROUP BY z.domain, z.serial_number, z.updated_at;
```

### mail_dns_records

**Purpose**: Filtered view of DNS records specifically for mail services.

```sql
CREATE VIEW unified.mail_dns_records AS
SELECT
    domain,
    name,
    type,
    value,
    ttl,
    priority,
    created_at,
    updated_at
FROM unified.dns_records
WHERE is_active = TRUE
  AND (
    type IN ('A', 'MX', 'TXT') OR
    name LIKE '%mail%' OR
    name LIKE '%dmarc%' OR
    name LIKE '%domainkey%'
  )
ORDER BY domain, type, name;
```

### dns_validation_report

**Purpose**: Validation report for DNS configuration completeness.

```sql
CREATE VIEW unified.dns_validation_report AS
SELECT
    domain,
    -- Check for essential records
    BOOL_OR(type = 'A' AND name = '@') as has_root_a,
    BOOL_OR(type = 'MX') as has_mx,
    BOOL_OR(type = 'TXT' AND value LIKE 'v=spf1%') as has_spf,
    BOOL_OR(type = 'TXT' AND name = '_dmarc') as has_dmarc,
    BOOL_OR(type = 'TXT' AND name LIKE '%._domainkey') as has_dkim,
    -- Record counts
    COUNT(*) as total_records,
    COUNT(CASE WHEN type = 'A' THEN 1 END) as a_count,
    COUNT(CASE WHEN type = 'MX' THEN 1 END) as mx_count,
    COUNT(CASE WHEN type = 'TXT' THEN 1 END) as txt_count,
    -- Validation status
    CASE
        WHEN BOOL_OR(type = 'A' AND name = '@')
         AND BOOL_OR(type = 'MX')
         AND BOOL_OR(type = 'TXT' AND value LIKE 'v=spf1%')
         AND BOOL_OR(type = 'TXT' AND name = '_dmarc')
        THEN 'VALID'
        ELSE 'INCOMPLETE'
    END as validation_status
FROM unified.dns_records
WHERE is_active = TRUE
GROUP BY domain;
```

## Data Types and Constraints

### Supported Record Types

```sql
-- Constraint for supported DNS record types
ALTER TABLE unified.dns_records
ADD CONSTRAINT chk_dns_record_type
CHECK (type IN (
    'A', 'AAAA', 'CNAME', 'MX', 'TXT', 'NS', 'SOA',
    'PTR', 'SRV', 'CAA', 'DNAME', 'NAPTR'
));
```

### Domain Validation

```sql
-- Function to validate domain names
CREATE OR REPLACE FUNCTION unified.validate_domain(domain_name VARCHAR)
RETURNS BOOLEAN AS $$
BEGIN
    -- Basic domain name validation
    RETURN domain_name ~ '^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$';
END;
$$ LANGUAGE plpgsql;

-- Add domain validation constraint
ALTER TABLE unified.dns_zones
ADD CONSTRAINT chk_valid_domain
CHECK (unified.validate_domain(domain));
```

### TTL Validation

```sql
-- TTL should be between 60 seconds and 1 week
ALTER TABLE unified.dns_records
ADD CONSTRAINT chk_ttl_range
CHECK (ttl >= 60 AND ttl <= 604800);
```

## Performance Optimization

### Partitioning Strategy

**Purpose**: Partition large tables for better performance.

```sql
-- Partition dns_history by date
CREATE TABLE unified.dns_history_2025 PARTITION OF unified.dns_history
FOR VALUES FROM ('2025-01-01') TO ('2026-01-01');

-- Create indexes on partitioned table
CREATE INDEX idx_dns_history_2025_changed_at
ON unified.dns_history_2025(changed_at);
```

### Query Optimization

**Purpose**: Optimized queries for common DNS operations.

```sql
-- Function to get all records for a domain
CREATE OR REPLACE FUNCTION unified.get_domain_records(domain_name VARCHAR)
RETURNS TABLE (
    name VARCHAR,
    type VARCHAR,
    value TEXT,
    ttl INTEGER,
    priority INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        r.name,
        r.type,
        r.value,
        r.ttl,
        r.priority
    FROM unified.dns_records r
    WHERE r.domain = domain_name
      AND r.is_active = TRUE
    ORDER BY r.type, r.name;
END;
$$ LANGUAGE plpgsql;
```

### Connection Pooling

**Purpose**: Optimize database connections for DNS services.

```sql
-- Connection pool configuration
-- This would be configured in the application layer
-- Example connection string:
-- postgresql://user:pass@host:port/db?pool_size=10&max_overflow=20
```

## Security Considerations

### Access Control

**Purpose**: Role-based access control for DNS operations.

```sql
-- Create roles for different access levels
CREATE ROLE dns_reader;
CREATE ROLE dns_writer;
CREATE ROLE dns_admin;

-- Grant appropriate permissions
GRANT SELECT ON unified.dns_records TO dns_reader;
GRANT SELECT ON unified.dns_zones TO dns_reader;

GRANT SELECT, INSERT, UPDATE ON unified.dns_records TO dns_writer;
GRANT SELECT, UPDATE ON unified.dns_zones TO dns_writer;

GRANT ALL ON unified.dns_records TO dns_admin;
GRANT ALL ON unified.dns_zones TO dns_admin;
GRANT ALL ON unified.dns_history TO dns_admin;
```

### Data Encryption

**Purpose**: Encrypt sensitive DNS data at rest.

```sql
-- Enable row-level security
ALTER TABLE unified.dns_records ENABLE ROW LEVEL SECURITY;

-- Create policy for domain access
CREATE POLICY dns_domain_policy ON unified.dns_records
    FOR ALL TO dns_writer
    USING (domain = current_setting('app.current_domain', true));
```

### Audit Logging

**Purpose**: Enhanced audit logging for security monitoring.

```sql
-- Function for security audit logging
CREATE OR REPLACE FUNCTION unified.audit_dns_access()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO unified.security_audit (
        table_name,
        operation,
        user_name,
        client_ip,
        timestamp,
        data_accessed
    ) VALUES (
        TG_TABLE_NAME,
        TG_OP,
        session_user,
        inet_client_addr(),
        NOW(),
        CASE
            WHEN TG_OP = 'DELETE' THEN to_jsonb(OLD)
            ELSE to_jsonb(NEW)
        END
    );

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;
```

## Maintenance and Operations

### Backup Strategy

**Purpose**: Comprehensive backup strategy for DNS data.

```sql
-- Daily backup of DNS tables
CREATE OR REPLACE FUNCTION unified.backup_dns_data()
RETURNS VOID AS $$
BEGIN
    -- Create backup tables with timestamp
    EXECUTE format('CREATE TABLE dns_backup_%s AS SELECT * FROM unified.dns_records',
                   to_char(now(), 'YYYY_MM_DD'));

    EXECUTE format('CREATE TABLE dns_zones_backup_%s AS SELECT * FROM unified.dns_zones',
                   to_char(now(), 'YYYY_MM_DD'));

    -- Log backup completion
    INSERT INTO unified.maintenance_log (operation, status, completed_at)
    VALUES ('dns_backup', 'SUCCESS', NOW());
END;
$$ LANGUAGE plpgsql;
```

### Cleanup Procedures

**Purpose**: Regular cleanup of old data and logs.

```sql
-- Function to clean up old history records
CREATE OR REPLACE FUNCTION unified.cleanup_dns_history()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    -- Delete history records older than 90 days
    DELETE FROM unified.dns_history
    WHERE changed_at < (NOW() - INTERVAL '90 days');

    GET DIAGNOSTICS deleted_count = ROW_COUNT;

    -- Log cleanup operation
    INSERT INTO unified.maintenance_log (operation, status, details, completed_at)
    VALUES ('dns_history_cleanup', 'SUCCESS',
            format('Deleted %s old records', deleted_count), NOW());

    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;
```

### Health Monitoring

**Purpose**: Monitor database health and performance.

```sql
-- View for database health monitoring
CREATE VIEW unified.dns_health_status AS
SELECT
    -- Record statistics
    COUNT(*) as total_records,
    COUNT(CASE WHEN is_active THEN 1 END) as active_records,
    COUNT(CASE WHEN NOT is_active THEN 1 END) as inactive_records,

    -- Zone statistics
    (SELECT COUNT(*) FROM unified.dns_zones WHERE is_active = TRUE) as active_zones,

    -- Recent activity
    COUNT(CASE WHEN updated_at > NOW() - INTERVAL '1 hour' THEN 1 END) as recent_updates,

    -- Performance metrics
    pg_database_size(current_database()) as database_size,
    (SELECT COUNT(*) FROM unified.dns_history WHERE changed_at > NOW() - INTERVAL '24 hours') as daily_changes
FROM unified.dns_records;
```

This PostgreSQL schema provides a robust foundation for DNS record management with comprehensive auditing, security, and performance optimization features.
