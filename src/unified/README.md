# Unified Environment Management System

A comprehensive Python package for managing Docker Compose environments with network queries, environment isolation, and CLI tools.

## Features

- **Environment Configuration**: Parse and validate Docker Compose environments
- **Network Queries**: Query service ports, URLs, and network topology
- **Environment Isolation**: Create isolated test and feature branch environments
- **CLI Tools**: Command-line interfaces for all functionality
- **Docker Compose Integration**: Full support for Docker Compose orchestration

## Quick Start

### Basic Usage

```python
from unified.environments import EnvironmentConfig, NetworkInfo

# Load environment configuration
config = EnvironmentConfig('.')
env_config = config.load_environment('dev')

# Query network information
network = NetworkInfo('.')
dns_port = network.get_service_port('dev', 'bind')  # DNS service
print(f"DNS is bound to port: {dns_port}")
```

### CLI Usage

```bash
# Query what port DNS is bound to
python -m unified.cli.query port dev bind

# List all service URLs
python -m unified.cli.query urls dev

# Create a feature branch environment
python -m unified.cli.environment create-feature my-feature-branch

# List all environments
python -m unified.cli.environment list --status
```

## Core Classes

### EnvironmentConfig

Parses and manages environment configurations from .env files and docker-compose.yml files.

```python
from unified.environments import EnvironmentConfig

config = EnvironmentConfig('.')
env_config = config.load_environment('dev')

# Get service port
port = config.get_service_port('apache')
print(f"Apache port: {port}")

# Get service URL
url = config.get_service_url('apache')
print(f"Apache URL: {url}")

# Validate configuration
validation = config.validate_configuration()
print(f"Configuration valid: {validation['valid']}")
```

### NetworkInfo

Provides network information queries about services and environments.

```python
from unified.environments import NetworkInfo

network = NetworkInfo('.')

# Get service port
port = network.get_service_port('dev', 'bind')
print(f"DNS port: {port}")

# Get all service URLs
urls = network.get_all_service_urls('dev')
print(f"Service URLs: {urls}")

# Test connectivity
connectivity = network.test_service_connectivity('dev', 'apache')
print(f"Apache accessible: {connectivity['accessible']}")

# Get network topology
topology = network.get_network_topology('dev')
print(f"Services: {list(topology['services'].keys())}")
```

### EnvironmentManager

Manages environment lifecycle operations (create, start, stop, remove).

```python
from unified.environments import EnvironmentManager

manager = EnvironmentManager('.')

# List environments
environments = manager.list_environments()
print(f"Available environments: {environments}")

# Create new environment
success = manager.create_environment(
    'my-test-env',
    'dev',
    {'CUSTOM_VAR': 'custom_value'}
)

# Start environment
if success:
    manager.start_environment('my-test-env')

# Get environment status
status = manager.get_environment_status('my-test-env')
print(f"Environment status: {status}")

# Clean up
manager.remove_environment('my-test-env', force=True)
```

### EnvironmentIsolation

Creates isolated environments for testing and feature development.

```python
from unified.environments import EnvironmentIsolation

isolation = EnvironmentIsolation('.')

# Create isolated test environment
test_env = isolation.create_isolated_environment(
    base_environment='dev',
    prefix='test',
    port_offset=1000
)

# Create feature branch environment
feature_env = isolation.create_feature_branch_environment(
    'feature/new-api',
    auto_start=False
)

# List isolated environments
isolated_envs = isolation.list_isolated_environments()
print(f"Isolated environments: {[env['name'] for env in isolated_envs]}")

# Clean up
isolation.cleanup_isolated_environment(test_env)
isolation.cleanup_isolated_environment(feature_env)
```

## CLI Tools

### Environment Management CLI

```bash
# List environments
python -m unified.cli.environment list

# Create environment
python -m unified.cli.environment create my-env --template dev

# Start environment
python -m unified.cli.environment start my-env

# Stop environment
python -m unified.cli.environment stop my-env

# Remove environment
python -m unified.cli.environment remove my-env --force

# Create isolated environment
python -m unified.cli.environment create-isolated --prefix test --port-offset 2000

# Create feature branch environment
python -m unified.cli.environment create-feature my-feature-branch

# List isolated environments
python -m unified.cli.environment list-isolated

# Clean up isolated environments
python -m unified.cli.environment cleanup --all
```

### Network Query CLI

```bash
# Get service port
python -m unified.cli.query port dev apache

# Get service URL
python -m unified.cli.query url dev apache --protocol https

# List all ports
python -m unified.cli.query ports dev

# List all URLs
python -m unified.cli.query urls dev

# Test connectivity
python -m unified.cli.query connectivity dev apache

# Get service health
python -m unified.cli.query health dev apache

# Get network topology
python -m unified.cli.query topology dev

# Find service by port
python -m unified.cli.query find-service dev 8080

# Natural language queries
python -m unified.cli.query quick dev "what port is dns"
```

## Common Use Cases

### 1. Answering Network Questions

```python
from unified.environments import NetworkInfo

network = NetworkInfo('.')

# What port is the DNS container bound to?
dns_port = network.get_service_port('dev', 'bind')
print(f"DNS is bound to port: {dns_port}")

# What services are running?
topology = network.get_network_topology('dev')
services = list(topology['services'].keys())
print(f"Running services: {services}")

# What's the Apache URL?
apache_url = network.get_service_url('dev', 'apache')
print(f"Apache URL: {apache_url}")
```

### 2. Creating Isolated Test Environments

```python
from unified.environments import EnvironmentIsolation

isolation = EnvironmentIsolation('.')

# Create isolated environment that doesn't interfere with others
with isolation.temporary_environment('dev') as temp_env:
    print(f"Using temporary environment: {temp_env}")
    # Run tests in isolated environment
    # Environment is automatically cleaned up on exit
```

### 3. Feature Branch Development

```python
from unified.environments import EnvironmentIsolation

isolation = EnvironmentIsolation('.')

# Create environment for feature branch
feature_env = isolation.create_feature_branch_environment(
    'feature/user-authentication',
    auto_start=True
)

print(f"Feature branch environment: {feature_env}")
# Work on feature with isolated environment
# Clean up when done
isolation.cleanup_isolated_environment(feature_env)
```

## Configuration

The system expects the following project structure:

```
project/
├── docker-compose.yml          # Base compose file
├── docker-compose.dev.yml      # Development overrides
├── docker-compose.staging.yml  # Staging overrides
├── .env.dev                    # Development environment variables
├── .env.staging               # Staging environment variables
├── .env.test                  # Test environment variables
└── src/unified/               # This package
```

## Environment Variables

Common environment variables used by the system:

- `ENVIRONMENT`: Environment name (dev, staging, test, etc.)
- `COMPOSE_PROJECT_NAME`: Docker Compose project name
- `DB_NAME`, `DB_USER`, `DB_PASSWORD`: Database configuration
- Service-specific port variables (e.g., `APACHE_PORT`, `POSTGRES_PORT`)

## Testing

Run the test suite:

```bash
# Run all tests
python -m pytest tests/

# Run specific test file
python -m pytest tests/test_environment_management.py

# Run with verbose output
python -m pytest tests/ -v
```

## Examples

See the `examples/` directory for complete examples:

- `environment_demo.py`: Comprehensive demo of all features
- Various CLI usage examples

## Development

To contribute to the project:

1. Follow the existing code style
1. Add tests for new functionality
1. Update documentation
1. Ensure all tests pass

The system is designed to be extensible and maintainable, with clear separation of concerns between configuration parsing, network queries, environment management, and CLI interfaces.
