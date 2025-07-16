# DNS, Mail, and PostgreSQL Integration Architecture

## Overview

The unified project implements a comprehensive mail infrastructure with integrated DNS services and PostgreSQL database backend. This document covers the architecture, configuration, and operational aspects of the DNS-Mail-PostgreSQL integration.

## Architecture Overview

### System Components

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   DNS Server    │    │   Mail Server   │    │   PostgreSQL    │
│   (BIND 9)      │    │ (Postfix+Dovecot)│    │   Database      │
├─────────────────┤    ├─────────────────┤    ├─────────────────┤
│ • Authoritative │    │ • SMTP (Postfix)│    │ • User Auth     │
│   DNS for mail  │    │ • IMAP (Dovecot)│    │ • DNS Records   │
│ • SPF Records   │◄──►│ • DKIM Signing  │◄──►│ • Certificates  │
│ • DMARC Records │    │ • SSL/TLS       │    │ • Mail Aliases  │
│ • DKIM Records  │    │ • OpenDKIM      │    │ • System Config │
│ • MX Records    │    │ • Cert Mgmt     │    │ • Audit Logs    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Integration Flow

1. **DNS Resolution**: Client queries DNS server for mail domain records
1. **Mail Authentication**: Mail server authenticates against PostgreSQL
1. **Certificate Management**: Automated SSL/TLS certificate provisioning
1. **Record Updates**: Dynamic DNS record updates via database triggers
1. **Monitoring**: Centralized logging and health monitoring

## DNS Service Integration

### DNS Server Configuration

**Location**: `containers/dns/`

**Key Components**:

- **BIND 9** authoritative DNS server
- **PostgreSQL backend** for dynamic record management
- **Zone templates** for mail domain configuration
- **DKIM integration** for email authentication

#### DNS Zone Structure

```dns
; Example zone for lab.sethlakowske.com
$TTL 3600
@    IN    SOA    lab.sethlakowske.com. root.lab.sethlakowske.com. (
                    2025071501    ; serial
                    3600          ; refresh
                    1800          ; retry
                    604800        ; expire
                    3600          ; minimum
                    )

; Mail server records
@    IN    MX     10 mail.lab.sethlakowske.com.
mail IN    A      192.168.0.156

; SPF record for email authentication
@    IN    TXT    "v=spf1 a mx ip4:192.168.0.156 include:_spf.google.com ~all"

; DMARC record for email policy
_dmarc    IN    TXT    "v=DMARC1; p=quarantine; rua=mailto:dmarc@lab.sethlakowske.com; ruf=mailto:dmarc@lab.sethlakowske.com; sp=quarantine; aspf=r; adkim=r; rf=afrf; fo=1"

; DKIM record (populated by mail server)
mail._domainkey    IN    TXT    "v=DKIM1; h=sha256; k=rsa; p=<public-key>"
```

#### DNS Database Schema

```sql
-- DNS records table
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

-- DNS zones metadata
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

### DNS Management Scripts

#### DKIM Record Management

**Location**: `containers/dns/manage-dkim-records.py`

```python
class DKIMRecordManager:
    def update_dkim_record(self, domain, selector, public_key):
        """Update DKIM record in database and zone file"""
        # Update database record
        self.db.execute("""
            INSERT INTO unified.dns_records (domain, name, type, value)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (domain, name, type) DO UPDATE SET
                value = EXCLUDED.value,
                updated_at = CURRENT_TIMESTAMP
        """, (domain, f"{selector}._domainkey", "TXT", f"v=DKIM1; k=rsa; p={public_key}"))

        # Update zone file
        self.update_zone_file(domain)

        # Reload DNS server
        self.reload_dns_server()
```

## Mail Server Integration

### Mail Server Configuration

**Location**: `containers/mail/`

**Key Components**:

- **Postfix** SMTP server with PostgreSQL lookup
- **Dovecot** IMAP server with PostgreSQL authentication
- **OpenDKIM** for DKIM signing
- **SSL/TLS** certificate management
- **Supervisor** for process management

#### Postfix Configuration

```conf
# PostgreSQL virtual domain lookup (with proxy for connection pooling)
virtual_mailbox_domains = proxy:pgsql:/etc/postfix/sql/virtual_domains.cf
virtual_mailbox_maps = proxy:pgsql:/etc/postfix/sql/virtual_users.cf
virtual_alias_maps = proxy:pgsql:/etc/postfix/sql/virtual_aliases.cf

# OpenDKIM integration
milter_protocol = 6
milter_default_action = accept
smtpd_milters = inet:localhost:8891
non_smtpd_milters = inet:localhost:8891

# SSL/TLS configuration (dynamically configured)
smtpd_use_tls = yes
smtpd_tls_cert_file = /data/certificates/live/lab.sethlakowske.com/fullchain.pem
smtpd_tls_key_file = /data/certificates/live/lab.sethlakowske.com/privkey.pem
smtpd_tls_security_level = may
```

#### Dovecot Configuration

```conf
# PostgreSQL authentication
auth_mechanisms = plain login
passdb {
    driver = sql
    args = /etc/dovecot/dovecot-sql.conf.ext
}
userdb {
    driver = sql
    args = /etc/dovecot/dovecot-sql.conf.ext
}

# SSL/TLS configuration
ssl = yes
ssl_cert = </data/certificates/live/lab.sethlakowske.com/fullchain.pem
ssl_key = </data/certificates/live/lab.sethlakowske.com/privkey.pem
```

### OpenDKIM Integration

#### DKIM Key Generation

**Location**: `containers/mail/generate-dkim-keys.sh`

```bash
#!/bin/bash
# Generate DKIM keys for domain
MAIL_DOMAIN=${MAIL_DOMAIN:-localhost}
KEY_DIR="/etc/opendkim/keys/${MAIL_DOMAIN}"

# Generate key pair
opendkim-genkey -b 2048 -d "$MAIL_DOMAIN" -D "$KEY_DIR" -r -s mail -v

# Set permissions
chown -R opendkim:opendkim "$KEY_DIR"
chmod 600 "$KEY_DIR/mail.private"
chmod 644 "$KEY_DIR/mail.txt"
```

#### DKIM Configuration Templates

**Location**: `containers/mail/opendkim/`

```conf
# opendkim.conf.template
Syslog yes
SyslogSuccess yes
LogWhy yes
Canonicalization relaxed/simple
Mode sv
SubDomains no
KeyTable /etc/opendkim/key.table
SigningTable /etc/opendkim/signing.table
ExternalIgnoreList /etc/opendkim/trusted.hosts
InternalHosts /etc/opendkim/trusted.hosts
Socket inet:8891@localhost
```

## PostgreSQL Database Integration

### Database Schema

#### User Authentication

```sql
-- Users table with email domains
CREATE TABLE unified.users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    domain VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    email_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Password storage for multiple services
CREATE TABLE unified.user_passwords (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES unified.users(id),
    service VARCHAR(50) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, service)
);

-- Email aliases
CREATE TABLE unified.email_aliases (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES unified.users(id),
    alias_email VARCHAR(255) NOT NULL UNIQUE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### Certificate Management

```sql
-- SSL/TLS certificates
CREATE TABLE unified.certificates (
    id SERIAL PRIMARY KEY,
    domain VARCHAR(255) NOT NULL,
    certificate_type VARCHAR(50) NOT NULL,
    certificate_data TEXT,
    private_key_data TEXT,
    certificate_chain TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    UNIQUE(domain, certificate_type)
);

-- Service certificate status
CREATE TABLE unified.service_certificates (
    id SERIAL PRIMARY KEY,
    service_name VARCHAR(100) NOT NULL,
    domain VARCHAR(255) NOT NULL,
    certificate_type VARCHAR(50) NOT NULL,
    ssl_enabled BOOLEAN DEFAULT FALSE,
    certificate_path VARCHAR(500),
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    UNIQUE(service_name, domain)
);
```

### Database Views for Mail Services

#### Dovecot Authentication View

```sql
CREATE VIEW unified.dovecot_auth AS
SELECT
    u.email as user,
    u.domain,
    up.password_hash as password,
    u.is_active
FROM unified.users u
JOIN unified.user_passwords up ON u.id = up.user_id
WHERE up.service = 'dovecot'
  AND u.is_active = true
  AND u.email_verified = true;
```

#### Dovecot Users View

```sql
CREATE VIEW unified.dovecot_users AS
SELECT
    u.email as user,
    u.domain,
    CONCAT(u.domain, '/', u.username, '/') as maildir,
    5000 as uid,
    5000 as gid
FROM unified.users u
WHERE u.is_active = true;
```

### Database Triggers and Notifications

#### DNS Record Updates

```sql
-- Function to update DNS zone serial
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

-- Trigger for DNS record changes
CREATE TRIGGER dns_record_update_trigger
    AFTER INSERT OR UPDATE ON unified.dns_records
    FOR EACH ROW
    EXECUTE FUNCTION unified.update_dns_zone_serial();
```

#### Certificate Change Notifications

```sql
-- Certificate change notification
CREATE OR REPLACE FUNCTION unified.notify_certificate_change()
RETURNS TRIGGER AS $$
BEGIN
    PERFORM pg_notify('certificate_change',
        NEW.service_name || ':' || NEW.domain || ':' || NEW.certificate_type);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for certificate changes
CREATE TRIGGER certificate_change_trigger
    AFTER INSERT OR UPDATE ON unified.service_certificates
    FOR EACH ROW
    EXECUTE FUNCTION unified.notify_certificate_change();
```

## Certificate Management Integration

### Certificate Watcher Service

**Location**: `containers/mail/certificate-watcher.py`

The certificate watcher monitors PostgreSQL for certificate changes and automatically reloads mail server SSL configuration.

```python
class CertificateWatcher:
    def listen_for_notifications(self):
        """Listen for PostgreSQL NOTIFY messages"""
        with self.db_connection.cursor() as cur:
            cur.execute("LISTEN certificate_change")

            while self.running:
                if self.db_connection.poll() is not None:
                    while self.db_connection.notifies:
                        notify = self.db_connection.notifies.pop(0)
                        if notify.payload.startswith(f"mail:{self.mail_domain}"):
                            self.reload_ssl_configuration()
```

### SSL Configuration Management

**Location**: `containers/mail/configure-ssl.sh`

```bash
#!/bin/bash
# Configure SSL certificates with preference logic

configure_ssl_certificates() {
    local domain="$MAIL_DOMAIN"

    # Certificate preference: live > staged > self-signed
    if check_certificate_exists "$domain" "live"; then
        use_certificate "$domain" "live"
    elif check_certificate_exists "$domain" "staged"; then
        use_certificate "$domain" "staged"
    elif check_certificate_exists "$domain" "self-signed"; then
        use_certificate "$domain" "self-signed"
    else
        disable_ssl
    fi
}
```

## Deployment Configuration

### Environment Variables

#### DNS Service Variables

```yaml
# .poststack.yml
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

#### Mail Service Variables

```yaml
# .poststack.yml
mail:
  variables:
    MAIL_DOMAIN: lab.sethlakowske.com
    MAIL_LOG_LEVEL: info
    MAIL_SMTP_PORT: "2525"
    MAIL_IMAP_PORT: "1144"
    MAIL_IMAPS_PORT: "9933"
    MAIL_SMTPS_PORT: "4465"
    MAIL_SUBMISSION_PORT: "5587"
    SSL_ENABLED: "true"
    CERT_TYPE_PREFERENCE: ""
    VMAIL_UID: "5000"
    VMAIL_GID: "5000"
```

### Volume Configuration

```yaml
# .poststack.yml
volumes:
  mail_data:
    type: named
  mail_logs:
    type: named
  dns_zones:
    type: named
  certificates:
    type: named
```

## Monitoring and Logging

### Log Locations

- **DNS Logs**: `/data/logs/dns/`
- **Mail Logs**: `/data/logs/mail/`
- **PostgreSQL Logs**: `/data/logs/postgres/`
- **Certificate Logs**: `/data/logs/mail/certificate_watcher.log`

### Health Checks

#### DNS Health Check

```bash
#!/bin/bash
# DNS health check
dig @localhost -p 53 $MAIL_DOMAIN A +short
dig @localhost -p 53 $MAIL_DOMAIN MX +short
dig @localhost -p 53 _dmarc.$MAIL_DOMAIN TXT +short
```

#### Mail Health Check

```bash
#!/bin/bash
# Mail health check
nc -z localhost 25 && echo "SMTP OK" || echo "SMTP FAIL"
nc -z localhost 143 && echo "IMAP OK" || echo "IMAP FAIL"
nc -z localhost 993 && echo "IMAPS OK" || echo "IMAPS FAIL"
```

### Performance Monitoring

#### Database Connection Monitoring

```sql
-- Monitor database connections
SELECT
    datname,
    usename,
    client_addr,
    state,
    backend_start,
    query_start,
    query
FROM pg_stat_activity
WHERE datname = 'unified_dev'
  AND state != 'idle';
```

#### DNS Query Monitoring

```bash
# Monitor DNS queries
tail -f /data/logs/dns/named.log | grep "query:"
```

## Security Considerations

### Network Security

- **DNS**: Port 53 (UDP/TCP) exposed on host network
- **Mail**: Ports 25, 143, 465, 587, 993 exposed on host network
- **PostgreSQL**: Port 5432 exposed only on bridge network

### Certificate Security

- **Automatic Renewal**: Certificates monitored for expiration
- **Secure Storage**: Private keys stored with restricted permissions
- **Preference System**: Automatic selection of best available certificate

### Email Security

- **SPF**: Sender Policy Framework for email authentication
- **DKIM**: DomainKeys Identified Mail for message signing
- **DMARC**: Domain-based Message Authentication for policy enforcement
- **TLS**: Transport Layer Security for encrypted connections

## Troubleshooting

### DNS Issues

```bash
# Check DNS server status
podman logs unified-dns-dev-dns-server-dns-server

# Test DNS resolution
dig @localhost -p 53 lab.sethlakowske.com A
dig @localhost -p 53 _dmarc.lab.sethlakowske.com TXT

# Check DNS database records
psql -h localhost -p 5436 -U unified_dev_user -d unified_dev \
  -c "SELECT * FROM unified.dns_records WHERE domain = 'lab.sethlakowske.com';"
```

### Mail Issues

```bash
# Check mail server logs
podman logs unified-mail-dev-mail-server

# Test SMTP connection
telnet localhost 2525

# Test IMAP connection
telnet localhost 1144

# Check mail database authentication
psql -h localhost -p 5436 -U unified_dev_user -d unified_dev \
  -c "SELECT * FROM unified.dovecot_auth LIMIT 5;"
```

### Certificate Issues

```bash
# Check certificate status
podman exec unified-mail-dev-mail-server \
  /usr/local/bin/configure-ssl.sh

# Monitor certificate watcher
podman exec unified-mail-dev-mail-server \
  tail -f /data/logs/mail/certificate_watcher.log

# Check certificate database
psql -h localhost -p 5436 -U unified_dev_user -d unified_dev \
  -c "SELECT * FROM unified.service_certificates WHERE service_name = 'mail';"
```

## Best Practices

### Database Management

1. **Regular Backups**: Backup PostgreSQL database including DNS and certificate data
1. **Connection Pooling**: Use connection pooling for high-load environments
1. **Index Optimization**: Monitor and optimize database indexes for performance
1. **Monitoring**: Set up monitoring for database performance and connectivity

### DNS Management

1. **Zone Serial Updates**: Ensure zone serial numbers are updated for DNS propagation
1. **TTL Configuration**: Set appropriate TTL values for different record types
1. **Redundancy**: Consider secondary DNS servers for production environments
1. **Monitoring**: Monitor DNS query performance and error rates

### Mail Security

1. **Regular Updates**: Keep mail server software and security patches current
1. **Log Monitoring**: Monitor mail logs for security threats and anomalies
1. **Rate Limiting**: Implement rate limiting to prevent abuse
1. **Backup**: Regular backups of mail data and configuration

This integration provides a robust, scalable mail infrastructure with automated DNS management and comprehensive security features.
