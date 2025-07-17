-- Migration: Add DNS records management for mail domain
-- This migration adds support for managing DNS records in the database

-- Create DNS records table
CREATE TABLE IF NOT EXISTS unified.dns_records (
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

-- Create unique constraint on domain, name, and type
ALTER TABLE unified.dns_records
ADD CONSTRAINT dns_records_unique_domain_name_type
UNIQUE (domain, name, type);

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_dns_records_domain
ON unified.dns_records(domain);

CREATE INDEX IF NOT EXISTS idx_dns_records_type
ON unified.dns_records(type);

-- Create DNS zones table for managing zone metadata
CREATE TABLE IF NOT EXISTS unified.dns_zones (
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

-- Function to automatically update serial number when zone is modified
CREATE OR REPLACE FUNCTION unified.update_dns_zone_serial()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE unified.dns_zones
    SET serial_number = EXTRACT(epoch FROM CURRENT_TIMESTAMP)::bigint,
        updated_at = CURRENT_TIMESTAMP
    WHERE domain = NEW.domain;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to update serial number when DNS records are modified
CREATE TRIGGER dns_record_update_serial
    AFTER INSERT OR UPDATE OR DELETE
    ON unified.dns_records
    FOR EACH ROW
    EXECUTE FUNCTION unified.update_dns_zone_serial();

-- Grant permissions to unified user
GRANT SELECT, INSERT, UPDATE, DELETE ON unified.dns_records TO unified_dev_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON unified.dns_zones TO unified_dev_user;
GRANT USAGE ON SEQUENCE unified.dns_records_id_seq TO unified_dev_user;
GRANT USAGE ON SEQUENCE unified.dns_zones_id_seq TO unified_dev_user;

-- Insert default zone for mail domain (will be updated by application)
INSERT INTO unified.dns_zones (domain, primary_ns, admin_email)
VALUES ('PLACEHOLDER_MAIL_DOMAIN', 'ns1.PLACEHOLDER_MAIL_DOMAIN', 'admin@PLACEHOLDER_MAIL_DOMAIN')
ON CONFLICT (domain) DO UPDATE SET
    primary_ns = EXCLUDED.primary_ns,
    admin_email = EXCLUDED.admin_email,
    updated_at = CURRENT_TIMESTAMP;

-- Insert basic DNS records for mail domain
INSERT INTO unified.dns_records (domain, name, type, value, ttl, priority) VALUES
-- A record for domain
('PLACEHOLDER_MAIL_DOMAIN', '@', 'A', 'PLACEHOLDER_MAIL_SERVER_IP', 3600, NULL),
-- Name servers
('PLACEHOLDER_MAIL_DOMAIN', 'ns1', 'A', 'PLACEHOLDER_MAIL_SERVER_IP', 3600, NULL),
('PLACEHOLDER_MAIL_DOMAIN', 'ns2', 'A', 'PLACEHOLDER_MAIL_SERVER_IP', 3600, NULL),
-- MX record
('PLACEHOLDER_MAIL_DOMAIN', '@', 'MX', 'mail.PLACEHOLDER_MAIL_DOMAIN', 3600, 10),
-- Mail server
('PLACEHOLDER_MAIL_DOMAIN', 'mail', 'A', 'PLACEHOLDER_MAIL_SERVER_IP', 3600, NULL),
-- SPF record
('PLACEHOLDER_MAIL_DOMAIN', '@', 'TXT', 'v=spf1 a mx ip4:PLACEHOLDER_MAIL_SERVER_IP include:_spf.google.com ~all', 3600, NULL),
-- DMARC record
('PLACEHOLDER_MAIL_DOMAIN', '_dmarc', 'TXT', 'v=DMARC1; p=quarantine; rua=mailto:dmarc@PLACEHOLDER_MAIL_DOMAIN; ruf=mailto:dmarc@PLACEHOLDER_MAIL_DOMAIN; sp=quarantine; aspf=r; adkim=r; rf=afrf; fo=1', 3600, NULL),
-- SMTP TLS Policy
('PLACEHOLDER_MAIL_DOMAIN', '_smtp._tls', 'TXT', 'v=TLSRPTv1; rua=mailto:tlsrpt@PLACEHOLDER_MAIL_DOMAIN', 3600, NULL),
-- MTA-STS
('PLACEHOLDER_MAIL_DOMAIN', '_mta-sts', 'TXT', 'v=STSv1; id=20250715T120000Z;', 3600, NULL),
('PLACEHOLDER_MAIL_DOMAIN', 'mta-sts', 'A', 'PLACEHOLDER_MAIL_SERVER_IP', 3600, NULL),
-- Common mail subdomains
('PLACEHOLDER_MAIL_DOMAIN', 'imap', 'A', 'PLACEHOLDER_MAIL_SERVER_IP', 3600, NULL),
('PLACEHOLDER_MAIL_DOMAIN', 'smtp', 'A', 'PLACEHOLDER_MAIL_SERVER_IP', 3600, NULL),
('PLACEHOLDER_MAIL_DOMAIN', 'pop3', 'A', 'PLACEHOLDER_MAIL_SERVER_IP', 3600, NULL),
('PLACEHOLDER_MAIL_DOMAIN', 'webmail', 'A', 'PLACEHOLDER_MAIL_SERVER_IP', 3600, NULL),
-- Autodiscover
('PLACEHOLDER_MAIL_DOMAIN', 'autodiscover', 'A', 'PLACEHOLDER_MAIL_SERVER_IP', 3600, NULL),
('PLACEHOLDER_MAIL_DOMAIN', 'autoconfig', 'A', 'PLACEHOLDER_MAIL_SERVER_IP', 3600, NULL)
ON CONFLICT (domain, name, type) DO UPDATE SET
    value = EXCLUDED.value,
    ttl = EXCLUDED.ttl,
    priority = EXCLUDED.priority,
    updated_at = CURRENT_TIMESTAMP;
