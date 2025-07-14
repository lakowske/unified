# Mail Container Tests

This directory contains comprehensive Python tests for the mail container functionality. The tests verify SMTP and IMAP services against a live development environment.

## Test Structure

```
containers/mail/test/
├── conftest.py           # Test fixtures and configuration
├── test_connectivity.py  # Basic connection and health tests
├── test_smtp.py          # SMTP functionality tests
├── test_imap.py          # IMAP functionality tests
├── test_workflows.py     # End-to-end workflow tests
├── utils.py              # Helper functions for mail testing
└── README.md             # This file
```

## Test Categories

### 1. Connectivity Tests (`test_connectivity.py`)

- SMTP and IMAP port accessibility
- Database connection and schema validation
- Service health checks
- Mail domain configuration

### 2. SMTP Tests (`test_smtp.py`)

- Basic SMTP operations (EHLO, NOOP, HELP)
- Email delivery to local users
- Cross-user email sending
- Multipart email handling
- Error handling and validation
- Performance tests

### 3. IMAP Tests (`test_imap.py`)

- IMAP connection and authentication
- Folder operations and listing
- Message search and retrieval
- Email content parsing
- Message operations (mark read, delete)
- Concurrent connection handling

### 4. Workflow Tests (`test_workflows.py`)

- Complete send-receive cycles
- Cross-user email workflows
- Reply workflows
- Multi-recipient scenarios
- Volume and performance testing
- Database integration workflows

## Prerequisites

1. **Live Mail Container**: Tests run against a live mail server container
1. **Database Access**: PostgreSQL database with unified schema
1. **Python Dependencies**: Install with `pip install -e ".[dev]"`

## Environment Configuration

Set these environment variables for your test environment:

```bash
# Mail server configuration
export MAIL_SMTP_HOST=localhost
export MAIL_SMTP_PORT=2525
export MAIL_IMAP_HOST=localhost
export MAIL_IMAP_PORT=1143
export MAIL_DOMAIN=localhost

# Database configuration
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=unified
export DB_USER=unified_user
export DB_PASSWORD=your_password
export DB_SSLMODE=prefer
```

## Running Tests

### Run All Tests

```bash
cd /path/to/uni-tests
pytest containers/mail/test/ -v
```

### Run Specific Test Categories

```bash
# Basic connectivity only
pytest containers/mail/test/test_connectivity.py -v

# SMTP functionality
pytest containers/mail/test/test_smtp.py -v

# IMAP functionality
pytest containers/mail/test/test_imap.py -v

# End-to-end workflows
pytest containers/mail/test/test_workflows.py -v
```

### Run Tests by Markers

```bash
# Integration tests only
pytest containers/mail/test/ -m integration -v

# Skip slow tests
pytest containers/mail/test/ -m "not slow" -v
```

### Run with Coverage

```bash
pytest containers/mail/test/ --cov=containers.mail.test --cov-report=html -v
```

## Test Behavior

### User Management

- Tests create temporary users in the database for testing
- All test users are automatically cleaned up after tests complete
- Test users have unique identifiers to avoid conflicts

### Email Cleanup

- Tests send emails with unique subjects containing UUIDs
- All test emails are automatically deleted from mailboxes
- Cleanup occurs in test teardown even if tests fail

### Database Transactions

- Tests use database connections for user creation and verification
- All database changes made by tests are rolled back
- Original database state is preserved

### Retry Logic

- Tests include retry logic for service availability
- Timing delays account for email delivery latency
- Connection timeouts are configured appropriately

## Test Markers

- `@pytest.mark.integration` - Tests requiring full system integration
- `@pytest.mark.slow` - Tests that take longer to execute (> 10 seconds)

## Troubleshooting

### Common Issues

1. **Connection Refused**

   - Ensure mail container is running and healthy
   - Check port mappings match environment variables
   - Verify firewall settings

1. **Database Connection Failed**

   - Confirm PostgreSQL container is running
   - Verify database credentials and connection parameters
   - Check that unified schema migration has been applied

1. **Authentication Failed**

   - Ensure test users can be created in the database
   - Verify dovecot_auth and dovecot_users views are accessible
   - Check password format matches Dovecot configuration

1. **Emails Not Found**

   - Increase wait times for email delivery
   - Check mail server logs for delivery errors
   - Verify mailbox creation for test users

### Debugging

Enable verbose logging:

```bash
export PYTHONPATH=.
pytest containers/mail/test/ -v -s --log-cli-level=DEBUG
```

Run individual test methods:

```bash
pytest containers/mail/test/test_connectivity.py::TestMailConnectivity::test_smtp_port_accessible -v
```

## Integration with CI/CD

These tests are designed to run in development environments with live containers. For CI/CD integration:

1. Start mail container and dependencies
1. Wait for services to be healthy
1. Run database migrations
1. Execute tests with appropriate environment variables
1. Collect test results and coverage reports

Example GitHub Actions workflow:

```yaml
- name: Run Mail Container Tests
  run: |
    # Start containers
    poststack deploy dev

    # Wait for health checks
    sleep 30

    # Run tests
    pytest containers/mail/test/ -v --junitxml=test-results.xml
  env:
    MAIL_SMTP_HOST: localhost
    MAIL_SMTP_PORT: 2525
    MAIL_IMAP_HOST: localhost
    MAIL_IMAP_PORT: 1143
    MAIL_DOMAIN: localhost
    DB_HOST: localhost
    DB_PORT: 5432
    DB_NAME: unified
    DB_USER: unified_user
    DB_PASSWORD: ${{ secrets.DB_PASSWORD }}
```

## Contributing

When adding new tests:

1. Follow existing patterns for test organization
1. Use provided fixtures for user and configuration management
1. Implement proper cleanup in test teardown
1. Add appropriate test markers
1. Include comprehensive logging for debugging
1. Document any new environment variables or dependencies
