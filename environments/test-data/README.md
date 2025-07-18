# Static Test Data for Unified Infrastructure

This directory contains comprehensive static test data for the unified infrastructure project, providing real environment configurations and validation data for integration testing.

## Overview

The static test data system provides:

- **Multiple Test Environments**: Pre-configured environments for different testing scenarios
- **Validation Data**: Expected values and configurations for automated testing
- **Test Fixtures**: Static data for users, DNS records, mail configuration, and more
- **Integration Testing**: Real container management and verification

## Directory Structure

```
test_data/
├── environments/           # Environment configurations
│   ├── test-env-1/        # Full-stack test environment 1
│   └── test-env-2/        # Full-stack test environment 2
├── validation/            # Expected values and test validation
│   ├── expected_ports.json     # Port mappings and conflict detection
│   ├── service_health.json     # Health check configurations
│   └── startup_order.json      # Service startup sequences
├── fixtures/              # Static test data
│   ├── test_users.json         # User accounts and authentication
│   ├── dns_records.json        # DNS zone and record data
│   └── mail_config.json        # Mail server configurations
└── README.md              # This file
```

## Test Environments

### Test Environment 1 (`test-env-1/`)

Full-stack test environment with complete service stack:

- **Services**: PostgreSQL, Apache, Mail (Postfix/Dovecot), BIND DNS, Flyway, Volume Setup
- **Ports**: 5001 (PostgreSQL), 8001 (Apache), 2501/1401 (Mail), 5301 (DNS)
- **Domain**: test-env-1.local
- **Use Case**: Full system testing, integration testing, feature development

### Test Environment 2 (`test-env-2/`)

Second full-stack test environment for parallel testing:

- **Services**: PostgreSQL, Apache, Mail (Postfix/Dovecot), BIND DNS, Flyway, Volume Setup
- **Ports**: 5002 (PostgreSQL), 8002 (Apache), 2502/1402 (Mail), 5302 (DNS)
- **Domain**: test-env-2.local
- **Use Case**: Parallel testing, environment isolation testing, port conflict validation

## Validation Data

### Expected Ports (`validation/expected_ports.json`)

Defines expected port mappings for each environment:

```json
{
  "environments": {
    "test-env-1": {
      "ports": {
        "postgres": 5001,
        "apache": 8001,
        "mail_smtp": 2501,
        "mail_imap": 1401,
        "dns": 5301
      },
      "services": ["postgres", "apache", "mail", "bind", "flyway", "volume-setup"]
    },
    "test-env-2": {
      "ports": {
        "postgres": 5002,
        "apache": 8002,
        "mail_smtp": 2502,
        "mail_imap": 1402,
        "dns": 5302
      },
      "services": ["postgres", "apache", "mail", "bind", "flyway", "volume-setup"]
    }
  }
}
```

### Service Health (`validation/service_health.json`)

Health check configurations and expected responses:

```json
{
  "health_checks": {
    "postgres": {
      "command": "pg_isready",
      "expected_response": "accepting connections",
      "timeout": 5,
      "retries": 5
    }
  }
}
```

### Startup Order (`validation/startup_order.json`)

Service startup sequences and dependency management:

```json
{
  "startup_sequences": {
    "test-env-1": {
      "phases": [
        {
          "phase": 1,
          "services": ["volume-setup"],
          "parallel": false
        },
        {
          "phase": 2,
          "services": ["postgres"],
          "depends_on": ["volume-setup"]
        },
        {
          "phase": 3,
          "services": ["flyway"],
          "depends_on": ["postgres"]
        },
        {
          "phase": 4,
          "services": ["apache", "mail", "bind"],
          "depends_on": ["postgres", "flyway"],
          "parallel": true
        }
      ]
    }
  }
}
```

## Test Fixtures

### Test Users (`fixtures/test_users.json`)

Pre-configured user accounts for testing:

- **admin_env1/admin_env2**: Administrators with full permissions for each environment
- **test_env1/test_env2**: Standard users for each environment
- **User Groups**: Administrative and standard user groups
- **Test Scenarios**: Login, permission, and authentication testing

### DNS Records (`fixtures/dns_records.json`)

DNS zone data and test queries:

- **Zones**: test-env-1.local, test-env-2.local
- **Records**: A, MX, TXT, CNAME records for each domain
- **Test Queries**: Expected DNS resolution results for both environments

### Mail Configuration (`fixtures/mail_config.json`)

Mail server configurations and test scenarios:

- **Domains**: Mail domain configurations for test-env-1.local and test-env-2.local
- **Mailboxes**: Test email accounts and passwords for each environment
- **Test Scenarios**: SMTP, IMAP, authentication, security tests

## Usage

### Running Tests

Use the comprehensive test runner:

```bash
# Run all tests
./scripts/run_static_tests.py

# Run validation tests only
./scripts/run_static_tests.py --validation-only

# Test specific environments
./scripts/run_static_tests.py --environments test-env-1 test-env-2

# Generate detailed output
./scripts/run_static_tests.py --output test_results.json --verbose
```

### Using the Environment Management API

```python
from unified.environments.config import EnvironmentConfig
from unified.environments.manager import UnifiedEnvironmentManager
from unified.environments.network import NetworkInfo

# Load environment configuration
config = EnvironmentConfig(project_dir)
env_config = config.load_environment("test-env-1")

# Start environment
manager = UnifiedEnvironmentManager(project_dir, environments_dir="environments/test-data")
result = manager.start_environment("test-env-1")

# Query network information
network = NetworkInfo(project_dir)
postgres_port = network.get_service_port("test-env-1", "postgres")
```

### Manual Environment Testing

```bash
# Start a specific environment
cd test_data/environments/test-env-1
docker compose -f docker-compose.test-env-1.yml up -d

# Check service health
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Test connectivity
nc -z localhost 5001  # PostgreSQL
curl -f http://localhost:8001/  # Apache
nc -z localhost 2501  # Mail SMTP
nc -z localhost 1401  # Mail IMAP
dig @localhost -p 5301 test-env-1.local  # DNS
```

## Integration with CI/CD

### GitHub Actions Example

```yaml
name: Static Environment Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run static tests
        run: ./scripts/run_static_tests.py --environments test-env-1
```

### Pre-commit Hook

```bash
#!/bin/bash
# .git/hooks/pre-commit
./scripts/run_static_tests.py --validation-only
```

## Development Workflow

### Adding New Environments

1. Create environment directory: `test_data/environments/new-env/`
1. Create configuration files:
   - `.env.new-env` - Environment variables
   - `docker-compose.new-env.yml` - Service definitions
1. Update validation data:
   - Add port mappings to `expected_ports.json`
   - Add health checks to `service_health.json`
   - Add startup sequence to `startup_order.json`
1. Run validation: `./scripts/run_static_tests.py --validation-only`

### Updating Test Data

1. Modify fixture files in `test_data/fixtures/`
1. Update validation data if needed
1. Run tests to verify changes: `./scripts/run_static_tests.py`
1. Update documentation if necessary

### Troubleshooting

#### Common Issues

1. **Port Conflicts**: Check `expected_ports.json` for conflicting port assignments
1. **Docker Issues**: Ensure Docker is running and containers can be built
1. **Permission Issues**: Verify file permissions for test data files
1. **Network Issues**: Check if test ports are available on the host

#### Debug Commands

```bash
# Check test environments
PYTHONPATH=src python -c "from unified.environments.test_manager import TestEnvironmentManager; print(TestEnvironmentManager('.').list_environments())"

# Check environment configuration
PYTHONPATH=src python -c "from unified.environments.config import EnvironmentConfig; print(EnvironmentConfig('.').load_environment('test-env-1'))"

# Run integration tests
PYTHONPATH=src python -m pytest tests/integration/test_simple_environments.py -v
```

## Performance Considerations

### Resource Requirements

- **Test Environment 1**: ~2GB RAM, 2.0 CPU cores
- **Test Environment 2**: ~2GB RAM, 2.0 CPU cores
- **Both Environments**: ~3GB RAM, 3.0 CPU cores (parallel execution)

### Startup Times

- **Single Environment**: ~180 seconds (full service stack)
- **Both Environments**: ~180 seconds (parallel startup)

### Optimization Tips

1. **Build Base Images**: Pre-build the base-debian image for faster startup
1. **Parallel Testing**: Use different environments in parallel for faster CI/CD
1. **Resource Limits**: Set appropriate Docker resource limits
1. **Clean Up**: Always clean up test environments after testing

## Contributing

When contributing to the static test data system:

1. Follow the existing directory structure and naming conventions
1. Add comprehensive validation data for new environments
1. Update this README with new environments or significant changes
1. Test all changes with the test runner before submitting
1. Ensure backward compatibility with existing tests

## Security Notes

### Test Data Security

- All passwords and secrets in test data are for testing only
- Never use test credentials in production environments
- Test data is committed to the repository for reproducible testing
- Use environment-specific secrets for production deployments

### Network Security

- Test environments bind to localhost only
- No external network access for test containers
- Use non-privileged ports when possible
- Implement proper firewall rules for test hosts

## License

This test data system is part of the unified infrastructure project and follows the same licensing terms as the main project.
