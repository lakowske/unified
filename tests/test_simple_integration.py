"""Simple integration tests for docker compose validation.

This module provides basic integration tests to validate that the test framework
works correctly with docker compose and that basic container functionality is working.
"""

import logging
import os
import subprocess
import time
from pathlib import Path

import pytest

logger = logging.getLogger(__name__)


class SimpleDockerManager:
    """Simple docker compose manager for basic testing."""

    def __init__(self, project_dir: Path, environment: str = "test"):
        self.project_dir = project_dir
        self.environment = environment
        self.compose_file = project_dir / "docker-compose.yml"

    def _run_compose_command(self, command: list, timeout: int = 300) -> subprocess.CompletedProcess:
        """Run a docker compose command with proper environment setup."""
        env = os.environ.copy()
        env.update(
            {
                "ENVIRONMENT": self.environment,
                "DB_NAME": f"unified_{self.environment}",
                "DB_USER": f"unified_{self.environment}_user",
                "DB_PASSWORD": f"{self.environment}_password123",
                "DB_PORT": "5433",  # Use different port to avoid conflicts
            }
        )

        cmd = ["docker", "compose", "-f", str(self.compose_file)] + command
        logger.info(f"Running command: {' '.join(cmd)}")

        return subprocess.run(cmd, cwd=self.project_dir, env=env, capture_output=True, text=True, timeout=timeout)

    def start_postgres(self) -> bool:
        """Start just the postgres service for testing."""
        logger.info("Starting postgres service...")
        result = self._run_compose_command(["up", "-d", "postgres"])
        return result.returncode == 0

    def stop_all(self) -> bool:
        """Stop all services and clean up."""
        logger.info("Stopping all services...")
        result = self._run_compose_command(["down", "-v"])
        return result.returncode == 0

    def get_container_status(self, service: str) -> dict:
        """Get status of a specific container."""
        try:
            result = subprocess.run(
                ["docker", "ps", "--filter", f"name={service}-{self.environment}", "--format", "json"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0 and result.stdout.strip():
                import json

                containers = json.loads(result.stdout)
                return containers[0] if containers else {}
        except Exception as e:
            logger.error(f"Error getting container status: {e}")
        return {}

    def execute_in_container(self, service: str, command: list) -> subprocess.CompletedProcess:
        """Execute command in container."""
        container_name = f"{service}-{self.environment}"
        cmd = ["docker", "exec", container_name] + command
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30)


@pytest.fixture(scope="session")
def project_dir():
    """Get the project directory."""
    return Path(__file__).parent.parent


@pytest.fixture(scope="session")
def docker_manager(project_dir):
    """Create a docker manager for tests."""
    return SimpleDockerManager(project_dir, environment="test")


@pytest.fixture(scope="session")
def postgres_container(docker_manager):
    """Start postgres container for testing."""
    # Clean up any existing containers first
    docker_manager.stop_all()

    # Start postgres
    success = docker_manager.start_postgres()
    assert success, "Failed to start postgres container"

    # Wait for postgres to be ready
    logger.info("Waiting for postgres to be ready...")
    max_attempts = 30
    for attempt in range(max_attempts):
        status = docker_manager.get_container_status("postgres")
        logger.debug(f"Postgres status: {status}")

        if status:
            state = status.get("State", "").lower()
            status_text = status.get("Status", "").lower()

            # Check if container is running
            if "running" in state:
                # Check if healthy or try to connect
                if "healthy" in status_text:
                    logger.info("Postgres container is healthy")
                    break
                else:
                    # Try to connect to verify it's ready
                    result = docker_manager.execute_in_container(
                        "postgres", ["pg_isready", "-h", "localhost", "-p", "5432"]
                    )
                    if result.returncode == 0:
                        logger.info("Postgres container is ready (pg_isready check passed)")
                        break

        time.sleep(2)
        logger.debug(f"Waiting for postgres... attempt {attempt + 1}/{max_attempts}")
    else:
        # Final status check
        status = docker_manager.get_container_status("postgres")
        logger.error(f"Postgres container status: {status}")
        assert False, "Postgres container did not become ready in time"

    yield docker_manager

    # Cleanup
    docker_manager.stop_all()


class TestBasicIntegration:
    """Basic integration tests."""

    def test_postgres_container_starts(self, postgres_container):
        """Test that postgres container starts successfully."""
        status = postgres_container.get_container_status("postgres")

        assert status, "Postgres container not found"
        assert "running" in status.get("State", "").lower(), f"Postgres container not running: {status}"

        logger.info(f"Postgres container is running: {status.get('Names', 'unknown')}")

    def test_postgres_connection(self, postgres_container):
        """Test database connection."""
        result = postgres_container.execute_in_container(
            "postgres", ["psql", "-U", "unified_test_user", "-d", "unified_test", "-c", "SELECT version();"]
        )

        assert result.returncode == 0, f"Database connection failed: {result.stderr}"
        assert "PostgreSQL" in result.stdout, "Database version query failed"

        logger.info("Database connection test successful")

    def test_postgres_basic_operations(self, postgres_container):
        """Test basic database operations."""
        # Create a test table
        result = postgres_container.execute_in_container(
            "postgres",
            [
                "psql",
                "-U",
                "unified_test_user",
                "-d",
                "unified_test",
                "-c",
                "CREATE TABLE IF NOT EXISTS test_table (id SERIAL PRIMARY KEY, name TEXT);",
            ],
        )
        assert result.returncode == 0, f"Table creation failed: {result.stderr}"

        # Insert test data
        result = postgres_container.execute_in_container(
            "postgres",
            [
                "psql",
                "-U",
                "unified_test_user",
                "-d",
                "unified_test",
                "-c",
                "INSERT INTO test_table (name) VALUES ('test_integration');",
            ],
        )
        assert result.returncode == 0, f"Data insertion failed: {result.stderr}"

        # Query test data
        result = postgres_container.execute_in_container(
            "postgres",
            [
                "psql",
                "-U",
                "unified_test_user",
                "-d",
                "unified_test",
                "-c",
                "SELECT name FROM test_table WHERE name = 'test_integration';",
            ],
        )
        assert result.returncode == 0, f"Data query failed: {result.stderr}"
        assert "test_integration" in result.stdout, "Test data not found"

        logger.info("Database basic operations test successful")

    def test_postgres_performance_baseline(self, postgres_container):
        """Test basic database performance baseline."""
        start_time = time.time()

        # Run a simple query multiple times
        for i in range(10):
            result = postgres_container.execute_in_container(
                "postgres", ["psql", "-U", "unified_test_user", "-d", "unified_test", "-c", "SELECT NOW();"]
            )
            assert result.returncode == 0, f"Query {i} failed: {result.stderr}"

        end_time = time.time()
        total_time = end_time - start_time
        avg_time = total_time / 10

        # Basic performance assertion (should be fast for simple queries)
        assert avg_time < 1.0, f"Database queries too slow: {avg_time:.3f}s average"

        logger.info(f"Database performance baseline: {avg_time:.3f}s average for 10 queries")


class TestContainerHealthChecks:
    """Test container health check functionality."""

    def test_postgres_health_check(self, postgres_container):
        """Test that postgres health check is working."""
        # Get container details
        result = subprocess.run(["docker", "inspect", "postgres-test"], capture_output=True, text=True, timeout=30)

        assert result.returncode == 0, f"Container inspect failed: {result.stderr}"

        # Parse container info to check health
        import json

        container_info = json.loads(result.stdout)[0]
        health_config = container_info.get("Config", {}).get("Healthcheck", {})

        assert health_config, "Health check configuration not found"
        logger.info(f"Health check command: {health_config.get('Test', 'unknown')}")

    def test_container_resource_limits(self, postgres_container):
        """Test that container resource limits are applied."""
        result = subprocess.run(["docker", "inspect", "postgres-test"], capture_output=True, text=True, timeout=30)

        assert result.returncode == 0, f"Container inspect failed: {result.stderr}"

        import json

        container_info = json.loads(result.stdout)[0]
        host_config = container_info.get("HostConfig", {})

        # Check memory limit (should be 1GB = 1073741824 bytes)
        memory_limit = host_config.get("Memory", 0)
        assert memory_limit > 0, "Memory limit not set"

        # Check CPU limit
        cpu_period = host_config.get("CpuPeriod", 0)
        cpu_quota = host_config.get("CpuQuota", 0)

        logger.info(f"Container resource limits - Memory: {memory_limit} bytes, CPU: {cpu_quota}/{cpu_period}")


@pytest.mark.performance
class TestPerformanceBaseline:
    """Performance baseline tests."""

    def test_container_startup_time(self, project_dir):
        """Test container startup performance."""
        manager = SimpleDockerManager(project_dir, environment="perftest")

        try:
            # Clean up first
            manager.stop_all()

            # Measure startup time
            start_time = time.time()
            success = manager.start_postgres()
            assert success, "Failed to start postgres for performance test"

            # Wait for ready state
            max_wait = 60
            ready_time = None
            for i in range(max_wait):
                status = manager.get_container_status("postgres")
                if status and (
                    "healthy" in status.get("State", "").lower() or "running" in status.get("State", "").lower()
                ):
                    result = manager.execute_in_container("postgres", ["pg_isready", "-h", "localhost", "-p", "5432"])
                    if result.returncode == 0:
                        ready_time = time.time()
                        break
                time.sleep(1)

            assert ready_time, "Container did not become ready within timeout"

            startup_time = ready_time - start_time

            # Performance assertion (adjust based on your hardware)
            assert startup_time < 60, f"Container startup too slow: {startup_time:.2f}s"

            logger.info(f"Container startup performance: {startup_time:.2f}s")

        finally:
            manager.stop_all()


def test_simple_docker_compose_functionality():
    """Test that basic docker compose commands work."""
    project_dir = Path(__file__).parent.parent

    # Test that docker compose can read the compose file
    result = subprocess.run(
        ["docker", "compose", "-f", str(project_dir / "docker-compose.yml"), "config"],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=project_dir,
        env={**os.environ, "ENVIRONMENT": "test", "DB_NAME": "test", "DB_USER": "test", "DB_PASSWORD": "test"},
    )

    assert result.returncode == 0, f"docker compose config failed: {result.stderr}"
    assert "postgres:" in result.stdout, "Expected postgres service not found in config"

    logger.info("docker compose basic functionality test successful")
