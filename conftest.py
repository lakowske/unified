"""Global pytest configuration and fixtures.

This file registers custom markers and provides global fixtures for the unified
infrastructure test suite.
"""

import pytest


def pytest_configure(config):
    """Configure pytest with custom markers."""
    # Register custom markers to avoid warnings
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "performance: marks tests as performance tests")
    config.addinivalue_line("markers", "dns_integration: marks tests as DNS integration tests")
    config.addinivalue_line("markers", "mail_integration: marks tests as mail integration tests")
    config.addinivalue_line("markers", "requires_dns_server: marks tests as requiring DNS server")
    config.addinivalue_line("markers", "requires_mail_server: marks tests as requiring mail server")
    config.addinivalue_line("markers", "slow: marks tests as slow running")
    config.addinivalue_line("markers", "api: marks tests as API endpoint tests")
    config.addinivalue_line("markers", "database: marks tests as database schema tests")
    config.addinivalue_line("markers", "container: marks tests as container build tests")


@pytest.fixture(scope="session")
def development_environment():
    """Fixture to ensure development environment is running."""
    import subprocess

    # Check if development environment is running
    try:
        result = subprocess.run(  # noqa: S603
            ["docker", "ps", "--format", "table {{.Names}}\t{{.Status}}", "--filter", "name=dev"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0 and "Up" in result.stdout:
            return True
        # Environment not running, skip tests that require it
        pytest.skip("Development environment not running")

    except subprocess.TimeoutExpired:
        pytest.skip("Could not check development environment status")
    except Exception as e:
        pytest.skip(f"Error checking development environment: {e}")


@pytest.fixture(scope="session")
def test_cleanup():
    """Fixture to clean up test data after test session."""
    yield

    # Cleanup logic could go here if needed
    # For now, we'll let the development environment handle cleanup


@pytest.fixture(scope="function")
def test_isolation():
    """Fixture to provide test isolation for integration tests."""
    import time

    # Create a unique test database prefix to avoid conflicts
    test_id = f"test_{int(time.time() * 1000)}"

    # Store original test data if needed
    test_data = {"test_id": test_id}

    yield test_data

    # Cleanup: Remove any test data created during the test
    # This could include cleaning up test users, test databases, etc.
    # For now, we'll rely on the development environment's cleanup mechanisms
