"""Simple integration tests for static test environments.

This module tests basic environment management functionality:
- Start test environments
- Verify basic connectivity
- Stop and cleanup test environments
"""

import json
import logging
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List

import pytest

from unified.environments.config import EnvironmentConfig
from unified.environments.manager import UnifiedEnvironmentManager

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test data paths
TEST_DATA_DIR = Path(__file__).parent.parent.parent / "environments" / "test-data"
VALIDATION_DIR = TEST_DATA_DIR / "validation"


class TestEnvironmentConfig(EnvironmentConfig):
    """Test-specific environment configuration that uses test data structure."""

    def __init__(self, project_dir: Path):
        super().__init__(project_dir)
        self.test_data_dir = project_dir / "environments" / "test-data"
        self.environments_dir = self.test_data_dir

    def load_environment(self, environment: str) -> Dict[str, Any]:
        """Load configuration for a test environment."""
        logger.info(f"Loading test environment configuration for: {environment}")

        # Load environment variables from test data .env file
        env_dir = self.environments_dir / environment
        env_file = env_dir / f".env.{environment}"
        if not env_file.exists():
            msg = f"Test environment file not found: {env_file}"
            raise FileNotFoundError(msg)

        self.env_vars = self._parse_env_file(env_file)

        # Load docker-compose configuration from test data
        compose_file = env_dir / f"docker-compose.{environment}.yml"
        if not compose_file.exists():
            msg = f"Test docker compose file not found: {compose_file}"
            raise FileNotFoundError(msg)

        self.compose_config = self._parse_compose_file(compose_file)

        # Extract service configurations
        self.service_configs = self._extract_service_configs()

        # Return combined configuration
        return {
            "environment": environment,
            "env_vars": self.env_vars,
            "compose_config": self.compose_config,
            "service_configs": self.service_configs,
            **self.env_vars,  # Include all env vars at top level for backward compatibility
        }


class TestStaticEnvironments:
    """Basic test suite for static environment configurations."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.project_dir = Path(__file__).parent.parent.parent
        self.config = TestEnvironmentConfig(self.project_dir)
        self.manager = UnifiedEnvironmentManager(self.project_dir, environments_dir="environments/test-data")

        # Load validation data
        with open(VALIDATION_DIR / "expected_ports.json") as f:
            self.expected_ports = json.load(f)

        # Track started environments for cleanup
        self.started_environments: List[str] = []

    def teardown_method(self) -> None:
        """Clean up test environments."""
        for env_name in self.started_environments:
            try:
                logger.info(f"Cleaning up environment: {env_name}")
                self.manager.stop_environment(env_name)
                self.manager.cleanup_environment(env_name)
            except Exception as e:
                logger.warning(f"Error cleaning up {env_name}: {e}")
        self.started_environments.clear()

    def _check_port_listening(self, port: int, timeout: int = 30) -> bool:
        """Check if a port is listening."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                result = subprocess.run(["nc", "-z", "localhost", str(port)], capture_output=True, timeout=5)
                if result.returncode == 0:
                    return True
            except subprocess.TimeoutExpired:
                pass

            time.sleep(1)

        return False

    def test_environment_configuration_loading(self) -> None:
        """Test loading environment configurations."""
        for env_name in ["test-env-1", "test-env-2"]:
            # Load environment configuration
            env_config = self.config.load_environment(env_name)

            # Verify configuration structure
            assert isinstance(env_config, dict)
            assert "environment" in env_config
            assert env_config["environment"] == env_name

            # Verify expected ports match validation data
            if env_name in self.expected_ports["environments"]:
                expected_data = self.expected_ports["environments"][env_name]

                # Check database port
                if "postgres" in expected_data["ports"]:
                    expected_port = expected_data["ports"]["postgres"]
                    actual_port = int(env_config.get("DB_PORT", 5432))
                    assert (
                        actual_port == expected_port
                    ), f"Database port mismatch: expected {expected_port}, got {actual_port}"

    def test_environment_isolation(self) -> None:
        """Test that environments use different ports and don't conflict."""
        env1_config = self.config.load_environment("test-env-1")
        env2_config = self.config.load_environment("test-env-2")

        # Verify they use different ports
        env1_port = int(env1_config.get("DB_PORT", 5432))
        env2_port = int(env2_config.get("DB_PORT", 5432))

        assert env1_port != env2_port, f"Environments should use different ports: {env1_port} vs {env2_port}"

        # Verify expected ports match validation data
        assert env1_port == 5001, f"Expected test-env-1 to use port 5001, got {env1_port}"
        assert env2_port == 5002, f"Expected test-env-2 to use port 5002, got {env2_port}"

    @pytest.mark.parametrize("env_name", ["test-env-1", "test-env-2"])
    def test_basic_environment_startup(self, env_name: str) -> None:
        """Test basic environment startup and connectivity."""
        logger.info(f"Testing basic startup for environment: {env_name}")

        # Start the environment
        result = self.manager.start_environment(env_name)
        assert result["success"], f"Failed to start {env_name}: {result['message']}"
        self.started_environments.append(env_name)

        # Wait for services to be ready
        time.sleep(45)  # Give services time to start

        # Test basic connectivity to postgres
        expected_config = self.expected_ports["environments"][env_name]
        postgres_port = expected_config["ports"]["postgres"]

        logger.info(f"Testing postgres connectivity on port {postgres_port}")
        is_listening = self._check_port_listening(postgres_port)
        assert is_listening, f"Postgres port {postgres_port} is not listening"

    @pytest.mark.parametrize("env_name", ["test-env-1", "test-env-2"])
    def test_environment_cleanup(self, env_name: str) -> None:
        """Test environment cleanup removes resources."""
        logger.info(f"Testing cleanup for environment: {env_name}")

        # Start environment
        result = self.manager.start_environment(env_name)
        assert result["success"], f"Failed to start {env_name}: {result['message']}"

        # Verify postgres is running
        expected_config = self.expected_ports["environments"][env_name]
        postgres_port = expected_config["ports"]["postgres"]

        time.sleep(30)  # Give time for startup
        assert self._check_port_listening(postgres_port), f"Postgres port {postgres_port} not listening after startup"

        # Stop and cleanup
        stop_result = self.manager.stop_environment(env_name)
        assert stop_result["success"], f"Failed to stop {env_name}: {stop_result['message']}"

        cleanup_result = self.manager.cleanup_environment(env_name)
        assert cleanup_result["success"], f"Failed to cleanup {env_name}: {cleanup_result['message']}"

        # Verify port is no longer listening
        time.sleep(10)
        assert not self._check_port_listening(
            postgres_port, timeout=10
        ), f"Postgres port {postgres_port} still listening after cleanup"


class TestEnvironmentManagement:
    """Test environment management operations."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.project_dir = Path(__file__).parent.parent.parent
        self.manager = UnifiedEnvironmentManager(self.project_dir, environments_dir="environments/test-data")
        self.started_environments: List[str] = []

    def teardown_method(self) -> None:
        """Clean up test environments."""
        for env_name in self.started_environments:
            try:
                self.manager.stop_environment(env_name)
                self.manager.cleanup_environment(env_name)
            except Exception as e:
                logger.warning(f"Error cleaning up {env_name}: {e}")

    def test_environment_listing(self) -> None:
        """Test listing available environments."""
        environments = self.manager.list_environments()

        # Should have our two test environments
        assert "test-env-1" in environments
        assert "test-env-2" in environments
        assert len(environments) == 2

    def test_environment_lifecycle(self) -> None:
        """Test complete environment lifecycle."""
        env_name = "test-env-1"

        # Start environment
        result = self.manager.start_environment(env_name)
        assert result["success"], f"Failed to start {env_name}: {result['message']}"
        self.started_environments.append(env_name)

        # Stop environment
        result = self.manager.stop_environment(env_name)
        assert result["success"], f"Failed to stop {env_name}: {result['message']}"

        # Cleanup environment
        result = self.manager.cleanup_environment(env_name)
        assert result["success"], f"Failed to cleanup {env_name}: {result['message']}"

        # Remove from tracking since it's cleaned up
        self.started_environments.remove(env_name)
