# Unified User Schema v1.0

## Overview

The Unified User Schema provides centralized authentication and authorization for multiple services including Apache, Dovecot/Postfix, WebDAV, and potentially Samba. This schema is designed to support real-world integration requirements while maintaining flexibility for future service additions.

## Design Principles

1. **Service Compatibility**: Views and structures match what Apache and Dovecot expect
1. **Multiple Password Formats**: Each service can have its own password hash format
1. **Role-Based Access Control**: Fine-grained permissions per service
1. **Email Verification**: Built-in email verification workflow
1. **Audit Trail**: Comprehensive logging of user actions
1. **Performance**: Optimized indexes for common authentication queries

## Schema Structure

### Core Tables

#### `unified.users`

Central user identity table containing core user information.

```sql
-- Key fields:
username VARCHAR(255) NOT NULL UNIQUE
email VARCHAR(255) NOT NULL UNIQUE
domain VARCHAR(255) NOT NULL        -- Auto-extracted from email
system_uid/system_gid INTEGER       -- For Dovecot mailbox access
home_directory VARCHAR(500)         -- Mailbox location path
is_active/email_verified BOOLEAN    -- Account status
```

**Key Features:**

- Domain is automatically extracted from email via trigger
- Home directory defaults to `/var/mail/{domain}/{username}`
- Supports email verification workflow
- Account locking and status tracking

#### `unified.user_passwords`

Service-specific password storage supporting multiple hash formats.

```sql
-- Key fields:
user_id INTEGER                     -- References users.id
service VARCHAR(50)                 -- 'apache', 'dovecot', 'samba'
password_hash TEXT                  -- Service-specific hash
hash_scheme VARCHAR(50)             -- 'PLAIN', 'BCRYPT', 'SSHA', etc.
```

**Supported Hash Schemes:**

- **Apache**: `BCRYPT`, `PLAIN`, `CRYPT`
- **Dovecot**: `SSHA`, `SHA256`, `PLAIN`, `CRYPT`
- **Samba**: `NTLM`, `LANMAN` (future)

#### `unified.user_roles`

Simplified role-based access control per service.

```sql
-- Key fields:
user_id INTEGER                     -- References users.id
role_name VARCHAR(50)               -- 'admin', 'user', 'customer', 'no_email'
service VARCHAR(50)                 -- Service this role applies to
```

**Standard Roles:**

- `admin`: Full administrative access
- `user`: Standard user access
- `customer`: Limited access (e.g., WebDAV only)
- `no_email`: Explicitly deny email access

#### `unified.user_quotas`

Service-specific quotas and limits.

```sql
-- Key fields:
user_id INTEGER                     -- References users.id
service VARCHAR(50)                 -- Service name
quota_type VARCHAR(50)              -- 'storage', 'bandwidth', 'connections'
quota_value BIGINT                  -- Quota amount
quota_unit VARCHAR(20)              -- 'bytes', 'MB', 'count'
```

### Integration Views

#### `unified.apache_auth`

Optimized view for Apache mod_authn_dbd authentication.

```sql
SELECT username, password, role, is_active, email_verified
FROM unified.apache_auth
WHERE username = %s;
```

#### `unified.dovecot_auth`

Password authentication view for Dovecot.

```sql
SELECT "user", password, scheme
FROM unified.dovecot_auth
WHERE "user" = '%u';
```

**Note**: The `user` column is quoted to avoid conflicts with PostgreSQL's built-in `user` function.

#### `unified.dovecot_users`

User information view for Dovecot mailbox configuration.

```sql
SELECT "user", home, uid, gid, quota_bytes
FROM unified.dovecot_users
WHERE "user" = '%u';
```

**Note**: The `user` column is quoted to avoid conflicts with PostgreSQL's built-in `user` function.

## Service Integration

### Apache Configuration

#### mod_authn_dbd Setup

```apache
# Load required modules
LoadModule dbd_module modules/mod_dbd.so
LoadModule authn_dbd_module modules/mod_authn_dbd.so

# Database connection
DBDriver pgsql
DBDParams "host=localhost dbname=unified_dev user=apache_user password=your_password"

# Authentication configuration
<Directory "/var/www/protected">
    AuthType Basic
    AuthName "Protected Area"
    AuthBasicProvider dbd
    AuthDBDUserPWQuery "SELECT password FROM unified.apache_auth WHERE username = %s"
    Require valid-user
</Directory>
```

#### Role-Based Authorization

```apache
# Different access levels based on roles
<Directory "/var/www/admin">
    AuthType Basic
    AuthName "Admin Area"
    AuthBasicProvider dbd
    AuthDBDUserPWQuery "SELECT password FROM unified.apache_auth WHERE username = %s AND role = 'admin'"
    Require valid-user
</Directory>
```

### Dovecot Configuration

#### SQL Configuration (`dovecot-sql.conf.ext`)

```conf
# Database connection
driver = pgsql
connect = host=localhost dbname=unified_dev user=dovecot_user password=your_password

# Password query
password_query = SELECT "user", password, scheme FROM unified.dovecot_auth WHERE "user" = '%u'

# User query
user_query = SELECT home, uid, gid, CONCAT('*:bytes=', quota_bytes) as quota_rule FROM unified.dovecot_users WHERE "user" = '%u'
```

#### Postfix Integration

```conf
# main.cf - Use same database for SMTP auth
smtpd_sasl_type = dovecot
smtpd_sasl_path = private/auth
smtpd_sasl_auth_enable = yes
```

## User Management Examples

### Creating Users

```sql
-- Create a new user (domain and home_directory auto-populated)
INSERT INTO unified.users (username, email, first_name, last_name, email_verified)
VALUES ('johndoe', 'johndoe@example.com', 'John', 'Doe', false);

-- Set passwords for different services
INSERT INTO unified.user_passwords (user_id, service, password_hash, hash_scheme) VALUES
(CURRVAL('unified.users_id_seq'), 'apache', '$2b$12$...', 'BCRYPT'),
(CURRVAL('unified.users_id_seq'), 'dovecot', '{SSHA}...', 'SSHA');

-- Assign roles
INSERT INTO unified.user_roles (user_id, role_name, service) VALUES
(CURRVAL('unified.users_id_seq'), 'user', 'apache'),
(CURRVAL('unified.users_id_seq'), 'user', 'dovecot');

-- Set quotas
INSERT INTO unified.user_quotas (user_id, service, quota_type, quota_value, quota_unit) VALUES
(CURRVAL('unified.users_id_seq'), 'dovecot', 'storage', 2147483648, 'bytes'); -- 2GB
```

### Role-Based Access Examples

```sql
-- Customer with WebDAV access but no email
INSERT INTO unified.user_roles (user_id, role_name, service) VALUES
(user_id, 'customer', 'apache'),    -- Can access web services
(user_id, 'no_email', 'dovecot');   -- Explicitly no email access

-- Admin with full access
INSERT INTO unified.user_roles (user_id, role_name, service) VALUES
(user_id, 'admin', 'apache'),
(user_id, 'admin', 'dovecot');
```

## Security Considerations

### Password Storage

- **Never store plaintext passwords in production**
- Use service-appropriate hash formats:
  - Apache: `BCRYPT` (recommended) or `CRYPT`
  - Dovecot: `SSHA` or `SHA256-CRYPT`
- Consider password expiration policies via `expires_at` field

### Database Access

- Create service-specific database users with minimal privileges:
  ```sql
  -- Apache user - read-only access to auth view
  CREATE USER apache_user WITH PASSWORD 'secure_password';
  GRANT SELECT ON unified.apache_auth TO apache_user;

  -- Dovecot user - read-only access to auth views
  CREATE USER dovecot_user WITH PASSWORD 'secure_password';
  GRANT SELECT ON unified.dovecot_auth TO dovecot_user;
  GRANT SELECT ON unified.dovecot_users TO dovecot_user;
  ```

### Audit Logging

All authentication attempts and user modifications should be logged:

```sql
-- Log successful login
INSERT INTO unified.audit_log (user_id, service, action, ip_address, success)
VALUES (user_id, 'apache', 'login', '192.168.1.100', true);

-- Log failed login attempt
INSERT INTO unified.audit_log (user_id, service, action, ip_address, success, error_message)
VALUES (user_id, 'apache', 'login', '192.168.1.100', false, 'Invalid password');
```

## Migration and Deployment

### Prerequisites

1. PostgreSQL 12+ with `plpgsql` extension
1. Database user with `CREATE SCHEMA` privileges
1. Service users for Apache and Dovecot

### Deployment Steps

1. Run migration: `psql -f migrations/004_unified_user_schema.sql`
1. Create service-specific database users
1. Configure Apache and Dovecot with connection details
1. Test authentication with sample users
1. Migrate existing users if needed

### Testing

```bash
# Test Apache authentication
curl -u testuser:testpass http://localhost/protected/

# Test Dovecot authentication
doveadm auth test testuser@unified.local testpass

# Check user creation
psql -c "SELECT * FROM unified.apache_auth;"
psql -c "SELECT \"user\", home, uid, gid FROM unified.dovecot_users;"
```

## Troubleshooting

### Common Issues

#### Apache "User not found"

- Check `unified.apache_auth` view returns data
- Verify user has `is_active=true` and `email_verified=true`
- Ensure password hash format matches Apache expectations

#### Dovecot Authentication Fails

- Verify password scheme matches what Dovecot expects
- Check user has appropriate role (not `no_email`)
- Confirm `dovecot_auth` view returns correct fields

#### Permission Denied

- Check service-specific database user permissions
- Verify connection parameters in service configs
- Review PostgreSQL logs for connection errors

### Useful Queries

```sql
-- Check user authentication status
SELECT u.username, u.email, u.is_active, u.email_verified,
       string_agg(ur.service || ':' || ur.role_name, ', ') as roles
FROM unified.users u
LEFT JOIN unified.user_roles ur ON u.id = ur.user_id
WHERE u.username = 'testuser'
GROUP BY u.id, u.username, u.email, u.is_active, u.email_verified;

-- Find users without email access
SELECT u.username, u.email
FROM unified.users u
LEFT JOIN unified.user_roles ur ON u.id = ur.user_id
WHERE ur.service = 'dovecot' AND ur.role_name = 'no_email';

-- Check password schemes by service
SELECT service, hash_scheme, COUNT(*)
FROM unified.user_passwords
GROUP BY service, hash_scheme;
```

## Future Enhancements

### Planned Features

1. **Samba Integration**: NTLM password support and domain membership
1. **LDAP Compatibility**: Optional LDAP interface for legacy systems
1. **Multi-Factor Authentication**: TOTP token support
1. **Advanced Quotas**: Bandwidth limits and connection throttling
1. **Group Management**: User groups for simplified role assignment

### Schema Evolution

- Version 1.1: Add group support and enhanced audit logging
- Version 1.2: Multi-factor authentication tables
- Version 1.3: LDAP integration and directory sync

This schema provides a solid foundation for unified authentication while maintaining compatibility with existing Apache and Dovecot installations.
