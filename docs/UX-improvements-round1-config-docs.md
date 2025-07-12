# Unified Project UX Improvements - Round 1: Configuration & Documentation

## Executive Summary

During the implementation of Apache database authentication using mod_authn_dbd, several configuration and documentation issues were identified that slowed development and created confusion. This document outlines specific improvements needed for the unified project's documentation and configuration patterns.

## Issues Encountered

### 1. Apache mod_authn_dbd Configuration Complexity

**Problem**: Apache's database authentication required multiple interconnected configuration pieces that weren't well documented.

**Configuration Challenges**:

- Database connection parameters in `apache2.conf.template`
- Authentication queries in virtual host configuration
- Environment variable propagation to PHP scripts
- Password hashing format requirements

**Time Lost**: ~60 minutes figuring out correct configuration patterns

**What Worked**:

```apache
# Database configuration
DBDriver pgsql
DBDParams "host=${DB_HOST} port=${DB_PORT} dbname=${DB_NAME} user=${DB_USER} password=${DB_PASSWORD}"
DBDMin 1
DBDKeep 2
DBDMax 10
DBDExptime 300

# Pass environment variables to PHP
SetEnv DB_HOST ${DB_HOST}
SetEnv DB_PORT ${DB_PORT}
SetEnv DB_NAME ${DB_NAME}
SetEnv DB_USER ${DB_USER}
SetEnv DB_PASSWORD ${DB_PASSWORD}
```

### 2. Password Hashing Format Requirements

**Problem**: Apache mod_authn_dbd requires specifically formatted password hashes, but initial test data used plain text passwords.

**Discovery Process**:

1. Authentication consistently returned 401
1. No clear error messages about password format
1. Had to research Apache documentation to understand requirements
1. Discovered need for bcrypt hashing with `htpasswd -nbB`

**Time Lost**: ~45 minutes debugging authentication failures

**Correct Format**:

```bash
# Generate bcrypt hash
htpasswd -nbB username password | cut -d: -f2
# Result: $2y$05$taWLPhOtInwdUEL3jsHkSe62v3x8Fu071o7rvAKki7Sorz25gbBIq
```

### 3. Environment Variable Propagation

**Problem**: Environment variables set in container weren't automatically available to PHP scripts.

**Discovery**:

- Variables visible in shell: `printenv | grep DB_`
- Variables not visible in PHP: `$_ENV['DB_PORT']` returned null
- Solution required Apache `SetEnv` directives
- PHP needed to use `$_SERVER` instead of `$_ENV`

### 4. Container Entrypoint Script Conflicts

**Problem**: Entrypoint script was overwriting copied web content with its own generated files.

**Issues**:

- `health.php` was overwritten with version using wrong environment variables
- Old hardcoded database configuration in entrypoint
- No coordination between Dockerfile COPY and entrypoint script

### 5. Service Startup Dependencies

**Problem**: Apache tried to initialize database connections before PostgreSQL schema was ready.

**Solution Required**: Custom wait logic in entrypoint script to check for database readiness.

## Recommended Improvements

### 1. Comprehensive Authentication Documentation

**Create**: `docs/apache-database-authentication.md`

**Contents**:

````markdown
# Apache Database Authentication Setup

## Overview
This guide covers setting up Apache mod_authn_dbd for database-backed authentication.

## Password Hashing
Apache requires specifically formatted password hashes. Use these commands:

### Bcrypt (Recommended)
```bash
htpasswd -nbB username password | cut -d: -f2
````

### SHA-256 (Alternative)

```bash
htpasswd -nbs username password | cut -d: -f2
```

## Configuration Templates

### apache2.conf.template

\[Include complete working example\]

### Virtual Host Configuration

\[Include complete working example\]

## Troubleshooting

### 401 Unauthorized

1. Check password hash format
1. Verify database connection
1. Test query manually
   \[More solutions...\]

````

### 2. Environment Variable Best Practices

**Create**: `docs/environment-variables.md`

**Key Points**:
- Difference between shell environment and Apache/PHP environment
- When to use `PassEnv` vs `SetEnv`
- How to access variables in PHP (`$_SERVER` vs `$_ENV`)
- Container networking considerations

**Example Code**:
```php
// Correct way to access Apache-set environment variables
$db_host = $_SERVER['DB_HOST'] ?? 'localhost';

// Health check example
if (isset($_SERVER['DB_HOST'])) {
    $dsn = sprintf(
        'pgsql:host=%s;port=%s;dbname=%s',
        $_SERVER['DB_HOST'],
        $_SERVER['DB_PORT'] ?? '5432',
        $_SERVER['DB_NAME']
    );
    $pdo = new PDO($dsn, $_SERVER['DB_USER'], $_SERVER['DB_PASSWORD']);
}
````

### 3. Database Schema Documentation Improvements

**Update**: `docs/unified-user-schema-v1.md`

**Add Sections**:

- Password hashing requirements for each service
- Example commands for creating test users
- View usage examples for Apache, Dovecot, etc.

**Example**:

```sql
-- Create test user with proper Apache authentication
INSERT INTO unified.users (username, email, domain, is_active, email_verified)
VALUES ('testuser', 'test@example.com', 'example.com', true, true);

-- Add bcrypt password for Apache
INSERT INTO unified.user_passwords (user_id, service, password_hash, hash_scheme)
VALUES (
    (SELECT id FROM unified.users WHERE username = 'testuser'),
    'apache',
    '$2y$05$x5r2pwHTXZNfpFUx4J5k7ORS0Zuamzrut/rdwuTleozXG0D5cqBoW',  -- "testpass"
    'BCRYPT'
);
```

### 4. Container Configuration Templates

**Create**: `docs/container-best-practices.md`

**Cover**:

- When to use Dockerfile COPY vs entrypoint script generation
- Environment variable substitution patterns
- Service readiness checking
- Health check endpoints

**Entrypoint Pattern**:

```bash
# Wait for required services
echo "Waiting for database to be ready..."
max_attempts=30
attempt=0

while [ $attempt -lt $max_attempts ]; do
    if php -r "
        try {
            \$pdo = new PDO('pgsql:host=${DB_HOST};port=${DB_PORT};dbname=${DB_NAME}', '${DB_USER}', '${DB_PASSWORD}');
            \$stmt = \$pdo->query('SELECT 1 FROM unified.apache_auth LIMIT 1');
            exit(0);
        } catch (Exception \$e) {
            exit(1);
        }
    " 2>/dev/null; then
        echo "Database ready!"
        break
    fi

    attempt=$((attempt + 1))
    echo "Attempt $attempt/$max_attempts: waiting..."
    sleep 2
done
```

### 5. Debugging Guide

**Create**: `docs/debugging-guide.md`

**Include**:

- Common authentication issues and solutions
- How to check container logs
- Database connection testing
- Environment variable debugging
- Apache mod_dbd troubleshooting

**Quick Reference**:

```bash
# Check environment variables in container
podman exec container-name printenv | grep DB_

# Test database connection from container
podman exec container-name php -r "
\$pdo = new PDO('pgsql:host=host.containers.internal;port=5436;dbname=db', 'user', 'pass');
echo 'Connected successfully';
"

# Check Apache error logs
podman exec container-name tail -f /var/log/apache2/error.log

# Test authentication query manually
psql -h localhost -p 5436 -U user -d db -c "SELECT password FROM unified.apache_auth WHERE username = 'admin';"
```

### 6. Example Configurations

**Create**: `examples/` directory with:

- Complete working Apache + PostgreSQL setup
- Different authentication scenarios (admin-only, role-based)
- Health check implementations
- Docker Compose equivalents for comparison

### 7. Migration Documentation

**Update**: `docs/unified-user-schema-v1.md`

**Add**:

- How to update existing plain-text passwords to hashed
- Migration between different hash formats
- Bulk user creation scripts

**Example Migration**:

```sql
-- Update existing plain-text passwords to bcrypt
-- (Run this outside the database, then update the table)

-- Generate hashes with:
-- echo -n "plaintext_password" | htpasswd -niB username | cut -d: -f2

UPDATE unified.user_passwords
SET
    password_hash = '$2y$05$hash_here',
    hash_scheme = 'BCRYPT'
WHERE service = 'apache' AND hash_scheme = 'PLAIN';
```

### 8. Configuration Validation

**Add**: Scripts to validate configuration

**Create**: `scripts/validate-config.sh`

```bash
#!/bin/bash
# Validate unified project configuration

echo "Checking Apache configuration..."
# Test template substitution
# Validate database connectivity
# Check required views exist
# Test authentication query

echo "Checking database schema..."
# Verify all tables exist
# Check view definitions
# Validate test data

echo "Configuration validation complete!"
```

## Implementation Priority

1. **High Priority** (Immediate documentation needs):

   - Apache database authentication guide
   - Environment variable best practices
   - Debugging guide

1. **Medium Priority** (Prevent future issues):

   - Container configuration best practices
   - Example configurations
   - Configuration validation scripts

1. **Lower Priority** (Nice to have):

   - Advanced authentication scenarios
   - Performance tuning guides
   - Multi-service integration examples

## Key Takeaways

1. **Configuration Complexity**: Database authentication involves many moving parts that need clear documentation
1. **Password Formats**: This is a major gotcha that should be prominently documented
1. **Environment Variables**: Container vs application environment is confusing and needs explanation
1. **Service Dependencies**: Startup order matters and should be handled gracefully
1. **Debugging Tools**: Need better guidance for troubleshooting common issues

## Success Metrics

After implementing these improvements, new developers should be able to:

- Set up database authentication in under 30 minutes
- Understand password hashing requirements immediately
- Debug environment variable issues quickly
- Follow clear examples for their use case

The goal is to eliminate the trial-and-error debugging that consumed significant time during this implementation.
