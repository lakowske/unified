# Unified Infrastructure Test Framework

## Overview

The Unified Infrastructure project includes a comprehensive testing framework built on pytest that validates all aspects of the containerized infrastructure. The framework tests everything from individual container builds to full multi-service integration scenarios.

## Test Structure

### Test Files Organization

```
tests/
├── test_core.py                    # Core functionality unit tests
├── test_simple_integration.py      # Simple Docker integration tests
├── test_integration.py             # Comprehensive integration tests
├── test_dns_mail_integration.py    # DNS/Mail integration tests
├── test_api_endpoints.py           # API endpoint tests (NEW)
├── test_database_schema.py         # Database schema tests (NEW)
├── test_container_builds.py        # Container build tests (NEW)
├── run_integration_tests.py        # Test runner script
└── conftest.py                     # Shared test configuration
```

### Container-Specific Tests

```
containers/
├── mail/test/
│   ├── test_smtp.py
│   ├── test_imap.py
│   ├── test_dkim.py
│   ├── test_connectivity.py
│   └── test_workflows.py
└── dns/test/
    └── test_connectivity.py
```

## Test Categories

### 1. Unit Tests (`test_core.py`)

- Basic functionality validation
- Utility function testing
- Configuration validation

### 2. Integration Tests (`test_integration.py`)

- Full Docker Compose environment testing
- Multi-service coordination
- Performance baseline measurement
- Service health validation

### 3. API Endpoint Tests (`test_api_endpoints.py`)

- PHP API endpoint validation
- Authentication and authorization
- User management operations
- Database integration validation
- Error handling and edge cases

### 4. Database Schema Tests (`test_database_schema.py`)

- Schema integrity validation
- Migration verification
- Referential integrity
- Performance testing
- Data consistency checks

### 5. Container Build Tests (`test_container_builds.py`)

- Image building validation
- Dockerfile syntax checking
- Build system dependency testing
- Image size and security validation
- Make-based build system testing

### 6. Simple Integration Tests (`test_simple_integration.py`)

- Basic Docker functionality
- Single service testing
- Quick validation scenarios

### 7. DNS/Mail Integration Tests (`test_dns_mail_integration.py`)

- Email authentication testing
- DKIM validation
- DNS resolution testing

## Running Tests

### Prerequisites

1. **Environment Setup**:

   ```bash
   # Install development dependencies
   pip install -e ".[dev]"

   # Ensure Docker is running
   docker --version

   # Ensure containers are built
   make all
   ```

1. **Environment Variables**:

   ```bash
   # Optional: Set API key for API tests
   export UNIFIED_API_KEY="your-api-key-here"
   ```

### Basic Test Commands

```bash
# Run all tests
pytest

# Run tests with verbose output
pytest -v

# Run specific test file
pytest tests/test_api_endpoints.py

# Run specific test class
pytest tests/test_integration.py::TestContainerIntegration

# Run specific test method
pytest tests/test_api_endpoints.py::TestUserManagement::test_create_user_success
```

### Test Categories with Markers

```bash
# Run only integration tests
pytest -m integration

# Run only performance tests
pytest -m performance

# Run only API tests
pytest -k "api"

# Run only database tests
pytest -k "database"

# Skip slow tests
pytest -m "not slow"
```

### Environment-Specific Testing

```bash
# Run tests against development environment
pytest --env=dev

# Run tests against test environment
pytest --env=test

# Run with custom configuration
pytest --config=tests/config/custom.ini
```

## Test Configuration

### pytest.ini Configuration

```ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short --strict-markers --color=yes
markers =
    integration: marks tests as integration tests
    performance: marks tests as performance tests
    slow: marks tests as slow running
    api: marks tests as API tests
    database: marks tests as database tests
    container: marks tests as container build tests
```

### pyproject.toml Configuration

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py", "*_test.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = [
    "--strict-markers",
    "--strict-config",
    "--verbose",
]
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "integration: marks tests as integration tests",
    "performance: marks tests as performance tests",
    "api: marks tests as API tests",
    "database: marks tests as database tests",
    "container: marks tests as container build tests",
]
```

## Advanced Test Scenarios

### Integration Test Runner

Use the comprehensive test runner for full infrastructure validation:

```bash
# Run all integration tests
python tests/run_integration_tests.py

# Run with performance testing
python tests/run_integration_tests.py --performance

# Run with DNS integration tests
python tests/run_integration_tests.py --dns-integration

# Generate detailed report
python tests/run_integration_tests.py --report

# Custom output directory
python tests/run_integration_tests.py --output test_results/
```

### Performance Testing

```bash
# Run performance baselines
pytest -m performance

# Run specific performance tests
pytest tests/test_integration.py::TestPerformanceBaselines

# Run API performance tests
pytest tests/test_api_endpoints.py::TestAPIPerformance
```

### Database Testing

```bash
# Run all database tests
pytest tests/test_database_schema.py

# Test schema integrity
pytest tests/test_database_schema.py::TestDatabaseSchema

# Test migrations
pytest tests/test_database_schema.py::TestMigrations

# Test data integrity
pytest tests/test_database_schema.py::TestDataIntegrity
```

### Container Build Testing

```bash
# Test build system
pytest tests/test_container_builds.py

# Test individual builds
pytest tests/test_container_builds.py::TestImageBuilds

# Test build performance
pytest tests/test_container_builds.py::TestBuildPerformance -m performance
```

## Test Data Management

### Fixtures

The framework includes comprehensive fixtures for:

- **Database connections** (`db_manager`)
- **API clients** (`api_manager`)
- **Container environments** (`isolated_environment`)
- **Build managers** (`build_manager`)
- **Performance tracking** (`performance_tracker`)

### Test Data Cleanup

Tests automatically clean up:

- Created users and database records
- Temporary containers and images
- Test environment resources
- Performance tracking data

## Continuous Integration

### GitHub Actions Integration

```yaml
name: Test Suite
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
      run: |
        pip install -e ".[dev]"
    - name: Run tests
      run: |
        pytest --cov=src --cov-report=xml
    - name: Upload coverage
      uses: codecov/codecov-action@v3
```

### Pre-commit Hooks

```yaml
repos:
  - repo: local
    hooks:
      - id: pytest-check
        name: pytest-check
        entry: pytest --maxfail=1 tests/test_core.py
        language: system
        pass_filenames: false
        always_run: true
```

## Performance Baselines

### Expected Performance Metrics

| Operation         | Baseline | Acceptable Range |
| ----------------- | -------- | ---------------- |
| Container startup | \< 20s   | \< 30s           |
| Database query    | \< 1s    | \< 2s            |
| API response      | \< 0.5s  | \< 1s            |
| User creation     | \< 2s    | \< 5s            |
| Environment setup | \< 60s   | \< 120s          |

### Performance Monitoring

```bash
# Generate performance report
python tests/run_integration_tests.py --performance --report

# View performance metrics
cat test_performance_report.json

# Compare with baselines
pytest tests/test_integration.py::TestPerformanceBaselines -v
```

## Troubleshooting

### Common Issues

1. **Docker Connection Issues**:

   ```bash
   # Check Docker daemon
   docker info

   # Check container status
   docker ps -a

   # Check logs
   docker logs <container_name>
   ```

1. **Database Connection Issues**:

   ```bash
   # Check database connectivity
   docker exec postgres-dev pg_isready -h localhost -p 5432

   # Check database logs
   docker exec postgres-dev tail -f /data/logs/postgres/postgresql.log
   ```

1. **API Key Issues**:

   ```bash
   # Check API key exists
   docker exec apache-dev cat /var/local/unified_api_key

   # Set API key environment variable
   export UNIFIED_API_KEY="$(docker exec apache-dev cat /var/local/unified_api_key)"
   ```

1. **Build Issues**:

   ```bash
   # Clean build cache
   make clean-images

   # Rebuild from scratch
   make rebuild

   # Check build logs
   docker build --no-cache -f containers/base-debian/Dockerfile . -t localhost/unified/base-debian:latest
   ```

### Debug Mode

```bash
# Run tests with debug output
pytest -v -s --tb=long

# Run specific test with debug
pytest tests/test_api_endpoints.py::TestUserManagement::test_create_user_success -v -s

# Enable logging
pytest --log-cli-level=DEBUG
```

### Test Environment Reset

```bash
# Clean test environment
make clean-all

# Rebuild everything
make all

# Reset database
docker compose --env-file .env.dev down -v
docker compose --env-file .env.dev up -d
```

## Coverage Reports

### Generate Coverage

```bash
# Run with coverage
pytest --cov=src --cov-report=html

# View HTML report
open htmlcov/index.html

# Generate terminal report
pytest --cov=src --cov-report=term
```

### Coverage Thresholds

- **Overall coverage**: > 80%
- **API endpoints**: > 90%
- **Database operations**: > 85%
- **Core functionality**: > 95%

## Best Practices

### Writing Tests

1. **Use descriptive test names**:

   ```python
   def test_user_creation_with_valid_data_returns_success(self):
       """Test that user creation with valid data returns success."""
   ```

1. **Follow AAA pattern** (Arrange, Act, Assert):

   ```python
   def test_create_user_success(self, api_ready):
       # Arrange
       username = f"test_user_{int(time.time())}"
       email = f"{username}@example.com"

       # Act
       result = api_ready.create_user(username, "password123", email)

       # Assert
       assert result["status_code"] == 201
       assert result["response"]["success"] is True
   ```

1. **Use fixtures for setup**:

   ```python
   @pytest.fixture
   def test_user_data():
       return {
           "username": "testuser",
           "password": "password123",
           "email": "test@example.com"
       }
   ```

1. **Clean up resources**:

   ```python
   def test_with_cleanup(self, api_manager):
       # Create test data
       user_id = create_test_user()

       try:
           # Run test
           result = api_manager.get_user(user_id)
           assert result["status_code"] == 200
       finally:
           # Clean up
           api_manager.delete_user(user_id)
   ```

### Test Organization

1. **Group related tests** in classes
1. **Use meaningful test categories** with markers
1. **Separate unit tests** from integration tests
1. **Document complex test scenarios**
1. **Keep tests independent** and isolated

## Extending the Framework

### Adding New Test Categories

1. **Create test file**:

   ```python
   # tests/test_new_feature.py
   import pytest

   class TestNewFeature:
       def test_new_functionality(self):
           """Test new functionality."""
           pass
   ```

1. **Add marker** to pytest configuration:

   ```ini
   markers =
       new_feature: marks tests as new feature tests
   ```

1. **Create fixtures** if needed:

   ```python
   @pytest.fixture
   def new_feature_manager():
       return NewFeatureManager()
   ```

### Adding Performance Tests

1. **Use performance marker**:

   ```python
   @pytest.mark.performance
   def test_performance_baseline(self):
       """Test performance baseline."""
       pass
   ```

1. **Track metrics**:

   ```python
   def test_with_metrics(self, performance_tracker):
       performance_tracker.start_timer("operation")
       # Run operation
       duration = performance_tracker.end_timer("operation")
       assert duration < 1.0  # Should be fast
   ```

### Adding Container Tests

1. **Use container marker**:

   ```python
   @pytest.mark.container
   def test_container_functionality(self):
       """Test container functionality."""
       pass
   ```

1. **Use build manager**:

   ```python
   def test_custom_build(self, build_manager):
       result = build_manager.build_image("test-image", "path/to/Dockerfile")
       assert result["success"]
   ```

## Summary

The Unified Infrastructure test framework provides comprehensive coverage of:

- ✅ **API endpoint validation** - All PHP API endpoints tested
- ✅ **Database schema integrity** - Schema, migrations, and data consistency
- ✅ **Container build validation** - Image building and build system testing
- ✅ **Integration testing** - Full multi-service environment validation
- ✅ **Performance monitoring** - Baseline measurement and regression detection
- ✅ **Error handling** - Edge cases and failure scenarios
- ✅ **Security validation** - Authentication, authorization, and container security

The framework is designed to be:

- **Reliable**: Consistent test environments and reproducible results
- **Comprehensive**: Full coverage of all infrastructure components
- **Maintainable**: Well-organized, documented, and extensible
- **Performant**: Fast execution with parallel testing capabilities
- **Developer-friendly**: Clear documentation and helpful error messages

Use this framework to ensure the reliability, security, and performance of the unified infrastructure across all environments and deployments.
