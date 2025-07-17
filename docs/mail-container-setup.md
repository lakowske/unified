# Mail Container Setup and Testing Guide

## Overview

The unified project now includes a mail server container that provides SMTP (Postfix) and IMAP (Dovecot) services with PostgreSQL authentication. This document covers implementation details, deployment, and testing procedures.

## Architecture

### Components

- **Postfix**: SMTP server for mail delivery and relay
- **Dovecot**: IMAP server for mail access
- **PostgreSQL**: Authentication backend using `unified` schema
- **Supervisor**: Process manager for running multiple services

### Authentication Integration

The mail server integrates with the existing PostgreSQL database using views defined in the `unified` schema:

- `unified.dovecot_auth` - Password authentication for IMAP
- `unified.dovecot_users` - User mailbox and system information
- `unified.users` - Core user table with email domains

### File Structure

```
containers/mail/
├── Dockerfile                      # Mail server container image
├── entrypoint.sh                  # Container startup script
├── dovecot.conf.template          # Dovecot IMAP configuration
├── dovecot-sql.conf.template      # Dovecot PostgreSQL queries
├── (pod files removed - now uses Docker Compose)
├── postfix/
│   ├── main.cf.template           # Postfix main configuration
│   └── master.cf.template         # Postfix service configuration
└── scripts/
    ├── create_mailboxes.sh        # Bulk mailbox creation
    └── create_user_mailbox.sh     # Individual mailbox creation
```

## Configuration

### Environment Variables

| Variable         | Description           | Default     | Example            |
| ---------------- | --------------------- | ----------- | ------------------ |
| `MAIL_DOMAIN`    | Primary mail domain   | `localhost` | `unified.local`    |
| `MAIL_LOG_LEVEL` | Logging verbosity     | `info`      | `debug`, `warn`    |
| `MAIL_SMTP_PORT` | Host SMTP port        | `2525`      | `25` (production)  |
| `MAIL_IMAP_PORT` | Host IMAP port        | `1144`      | `143` (production) |
| `VMAIL_UID`      | Mail storage user ID  | `5000`      | `5000`             |
| `VMAIL_GID`      | Mail storage group ID | `5000`      | `5000`             |

### Database Variables

The mail container uses the same PostgreSQL connection variables as the Apache container:

- `DB_HOST` - PostgreSQL server hostname
- `DB_PORT` - PostgreSQL server port
- `DB_NAME` - Database name
- `DB_USER` - Database username
- `DB_PASSWORD` - Database password
- `DB_SSLMODE` - SSL connection mode

## Deployment

### Environment-Specific Configurations

#### Development Environment

- SMTP Port: `2525` (to avoid conflicts)
- IMAP Port: `1143` (to avoid conflicts)
- Mail Domain: `dev.unified.local`
- Storage: 1GB mail data, 200MB logs

#### Staging Environment

- SMTP Port: `2526`
- IMAP Port: `1144`
- Mail Domain: `staging.unified.local`
- Storage: 5GB mail data, 500MB logs

#### Production Environment

- SMTP Port: `25` (standard)
- IMAP Port: `143` (standard)
- Mail Domain: `unified.example.com`
- Storage: 50GB mail data, 2GB logs

### Volume Mounts

- `mail_data` → `/var/mail` - User mailbox storage (Maildir format)
- `mail_logs` → `/var/log/mail` - Dovecot and Postfix logs
- `mail_config` → `/etc/dovecot/conf.d` - Runtime configuration

## User Management

### Mailbox Structure

Mailboxes are stored in Maildir format under `/var/mail/{domain}/{username}/`:

```
/var/mail/unified.local/user1/
├── cur/                    # Current messages
├── new/                    # New messages
├── tmp/                    # Temporary files
├── .Drafts/               # Drafts folder
├── .Sent/                 # Sent folder
├── .Trash/                # Trash folder
├── .Junk/                 # Spam folder
├── subscriptions          # IMAP folder subscriptions
└── dovecot-uidlist       # IMAP UID tracking
```

### Creating User Mailboxes

#### Bulk Creation

Creates mailboxes for all active users in the database:

```bash
# Inside the mail container
/usr/local/bin/mail-scripts/create_mailboxes.sh
```

#### Individual Creation

Creates a mailbox for a specific user:

```bash
# Inside the mail container
/usr/local/bin/mail-scripts/create_user_mailbox.sh user@domain.com
```

### User Requirements

For a user to access mail services, they must:

1. Be active (`is_active = true`)
1. Have email verified (`email_verified = true`) for authentication
1. Have a password entry for `dovecot` service in `user_passwords`
1. Not have `no_email` role in `user_roles` for `dovecot` service

## Testing Workflow

### 1. Container Build and Deployment

```bash
# Build the mail container
poststack build mail

# Deploy the development environment
poststack deploy dev

# Check container status
podman ps | grep mail
```

### 2. Database Connectivity Test

```bash
# Exec into the mail container
podman exec -it unified-mail-dev /bin/bash

# Test database connection
PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
  -c "SELECT username, domain FROM unified.dovecot_auth LIMIT 5;"
```

### 3. Service Status Check

```bash
# Check running processes
supervisorctl status

# Check mail logs
tail -f /var/log/mail/dovecot.log
tail -f /var/log/mail/postfix.log
```

### 4. Port Connectivity Tests

```bash
# Test SMTP port (from host)
telnet localhost 2525

# Test IMAP port (from host)
telnet localhost 1143

# Test from within container
nc -z localhost 25
nc -z localhost 143
```

### 5. SMTP Testing

```bash
# Send test email via SMTP
cat << EOF | nc localhost 2525
HELO test.local
MAIL FROM: test@unified.local
RCPT TO: user@unified.local
DATA
Subject: Test Message

This is a test message.
.
QUIT
EOF
```

### 6. IMAP Authentication Testing

```bash
# Test IMAP login (replace with actual user credentials)
cat << EOF | nc localhost 143
a1 LOGIN user@unified.local password123
a2 SELECT INBOX
a3 LOGOUT
EOF
```

### 7. Mailbox Verification

```bash
# Check if mailboxes were created
ls -la /var/mail/

# Check specific user mailbox
ls -la /var/mail/unified.local/testuser/

# Verify permissions
ls -ld /var/mail/unified.local/testuser/
# Should show: drwxr-x--- vmail vmail
```

### 8. Log Analysis

```bash
# Check for authentication errors
grep -i "auth" /var/log/mail/dovecot.log

# Check for delivery errors
grep -i "error" /var/log/mail/postfix.log

# Check database connection issues
grep -i "postgresql" /var/log/mail/*.log
```

## Troubleshooting

### Common Issues

#### Database Connection Failures

- Verify PostgreSQL container is running
- Check database credentials and network connectivity
- Ensure `unified` schema migration has been applied

#### Permission Errors

- Verify `vmail` user exists with UID/GID 5000
- Check `/var/mail` directory ownership and permissions
- Ensure volume mounts are properly configured

#### Service Startup Failures

- Check supervisor logs: `/var/log/mail/supervisord.log`
- Verify configuration template processing completed
- Check for port conflicts on the host system

#### Authentication Failures

- Verify user exists in `unified.dovecot_auth` view
- Check password hashing scheme matches configuration
- Ensure user has `dovecot` service password entry

### Health Check Commands

```bash
# Overall container health
/usr/local/bin/mail-health-check.sh

# Individual service checks
pgrep dovecot
pgrep postfix
supervisorctl status

# Configuration validation
dovecot -n
postconf -n
```

## Production Considerations

### Security

- Enable SSL/TLS for IMAP and SMTP connections
- Configure proper firewall rules for mail ports
- Use strong passwords and consider certificate-based authentication
- Regular security updates for mail server components

### Monitoring

- Set up log aggregation for mail server logs
- Monitor disk usage for mail storage volumes
- Configure alerts for service failures
- Monitor authentication failure rates

### Backup

- Regular backups of mail data volumes
- Database backup includes user authentication data
- Test restore procedures for mail data
- Document recovery procedures

### Performance

- Monitor connection counts and resource usage
- Configure appropriate resource limits
- Consider mail quotas for users
- Regular maintenance tasks (log rotation, cleanup)

## Integration Notes

The mail container is designed to integrate seamlessly with the existing unified project:

- Shares PostgreSQL database with Apache container
- Uses consistent environment variable patterns
- Follows the same volume and logging conventions
- Integrates with poststack deployment orchestration

For user management, use the existing admin API endpoints or poststack CLI commands to create users with appropriate mail access permissions.
