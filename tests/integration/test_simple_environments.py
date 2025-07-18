"""Simple integration tests for isolated test environments.

This module tests the basic environment management functionality:
- Parse environment configurations
- Start/stop isolated environments
- Query environment network information
- Verify environment isolation
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
from unified.environments.network import NetworkInfo

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test data paths
TEST_DATA_DIR = Path(__file__).parent.parent.parent / "environments" / "test-data"
ENVIRONMENTS_DIR = TEST_DATA_DIR
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


class TestSimpleEnvironments:
    """Test simple isolated environments."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.project_dir = Path(__file__).parent.parent.parent
        self.config = TestEnvironmentConfig(self.project_dir)
        self.manager = UnifiedEnvironmentManager(self.project_dir, environments_dir="environments/test-data")
        self.network = NetworkInfo(self.project_dir)

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

    def test_environment_startup_basic(self) -> None:
        """Test basic environment startup and full service stack connectivity."""
        env_name = "test-env-1"

        logger.info(f"Testing basic startup for environment: {env_name}")

        # Start the environment
        result = self.manager.start_environment(env_name)
        assert result["success"], f"Failed to start {env_name}: {result['message']}"
        self.started_environments.append(env_name)

        # Wait for services to be ready
        time.sleep(60)

        # Test full service stack connectivity
        expected_ports = {"postgres": 5001, "apache": 8001, "mail_smtp": 2501, "mail_imap": 1401, "dns": 5301}

        for service, port in expected_ports.items():
            try:
                result = subprocess.run(["nc", "-z", "localhost", str(port)], capture_output=True, timeout=10)
                assert result.returncode == 0, f"{service} port {port} is not listening"
            except subprocess.TimeoutExpired:
                pytest.fail(f"Timeout testing {service} connectivity on port {port}")

    def test_parallel_environments(self) -> None:
        """Test that both environments can run simultaneously."""
        env_names = ["test-env-1", "test-env-2"]

        logger.info(f"Testing parallel startup for environments: {env_names}")

        # Start both environments
        results = []
        for env_name in env_names:
            result = self.manager.start_environment(env_name)
            results.append((env_name, result))
            if result["success"]:
                self.started_environments.append(env_name)

        # Verify both started successfully
        for env_name, result in results:
            assert result["success"], f"Failed to start {env_name}: {result['message']}"

        # Wait for services to be ready
        time.sleep(30)

        # Test both environments' services are accessible on different ports
        for env_name in env_names:
            base_port = 5001 if env_name == "test-env-1" else 5002
            env_number = "1" if env_name == "test-env-1" else "2"

            expected_ports = {
                "postgres": base_port,
                "apache": int(f"800{env_number}"),
                "mail_smtp": int(f"250{env_number}"),
                "mail_imap": int(f"140{env_number}"),
                "dns": int(f"530{env_number}"),
            }

            for service, port in expected_ports.items():
                try:
                    result = subprocess.run(["nc", "-z", "localhost", str(port)], capture_output=True, timeout=10)
                    assert result.returncode == 0, f"{service} port {port} for {env_name} is not listening"
                except subprocess.TimeoutExpired:
                    pytest.fail(f"Timeout testing {service} connectivity for {env_name} on port {port}")

    def test_environment_cleanup(self) -> None:
        """Test environment cleanup removes resources."""
        env_name = "test-env-1"

        logger.info(f"Testing cleanup for environment: {env_name}")

        # Start environment
        result = self.manager.start_environment(env_name)
        assert result["success"], f"Failed to start {env_name}: {result['message']}"

        # Verify services are running
        expected_ports = {"postgres": 5001, "apache": 8001, "mail_smtp": 2501, "dns": 5301}
        time.sleep(60)

        for service, port in expected_ports.items():
            try:
                result = subprocess.run(["nc", "-z", "localhost", str(port)], capture_output=True, timeout=10)
                assert result.returncode == 0, f"{service} port {port} not listening after startup"
            except subprocess.TimeoutExpired:
                pytest.fail(f"Timeout testing {service} connectivity on port {port}")

        # Stop and cleanup
        stop_result = self.manager.stop_environment(env_name)
        assert stop_result["success"], f"Failed to stop {env_name}: {stop_result['message']}"

        cleanup_result = self.manager.cleanup_environment(env_name)
        assert cleanup_result["success"], f"Failed to cleanup {env_name}: {cleanup_result['message']}"

        # Verify ports are no longer listening
        time.sleep(10)
        for service, port in expected_ports.items():
            try:
                result = subprocess.run(["nc", "-z", "localhost", str(port)], capture_output=True, timeout=5)
                assert result.returncode != 0, f"{service} port {port} still listening after cleanup"
            except subprocess.TimeoutExpired:
                # Timeout is actually good here - means the port isn't responding
                pass

    def test_network_port_queries(self) -> None:
        """Test querying network information about environments."""
        env_name = "test-env-1"

        logger.info(f"Testing network queries for environment: {env_name}")

        # Load environment configuration
        env_config = self.config.load_environment(env_name)

        # Test port query from configuration
        expected_port = 5001
        actual_port = int(env_config.get("DB_PORT", 5432))
        assert actual_port == expected_port, f"Expected port {expected_port}, got {actual_port}"

        # Test service configuration queries
        compose_config = env_config.get("compose_config", {})
        services = compose_config.get("services", {})

        # Verify all expected services are configured
        expected_services = ["postgres", "apache", "mail", "bind", "flyway", "volume-setup"]
        for service in expected_services:
            assert service in services, f"{service} service not found in compose config"

        # Verify postgres service port mapping
        postgres_config = services["postgres"]
        assert "ports" in postgres_config, "Postgres service has no port configuration"
        port_mapping = postgres_config["ports"][0]  # Should be "5001:5432"
        assert port_mapping.startswith(
            "5001:"
        ), f"Expected postgres port mapping to start with '5001:', got {port_mapping}"

        # Verify apache service port mapping
        apache_config = services["apache"]
        assert "ports" in apache_config, "Apache service has no port configuration"
        apache_port_mapping = apache_config["ports"][0]  # Should be "8001:80"
        assert apache_port_mapping.startswith(
            "8001:"
        ), f"Expected apache port mapping to start with '8001:', got {apache_port_mapping}"

        # Verify mail service port mappings
        mail_config = services["mail"]
        assert "ports" in mail_config, "Mail service has no port configuration"
        mail_ports = mail_config["ports"]
        assert len(mail_ports) >= 2, "Mail service should have at least 2 port mappings"

        # Verify bind service port mapping
        bind_config = services["bind"]
        assert "ports" in bind_config, "Bind service has no port configuration"
        bind_port_mapping = bind_config["ports"][0]  # Should be "5301:53/udp"
        assert bind_port_mapping.startswith(
            "5301:"
        ), f"Expected bind port mapping to start with '5301:', got {bind_port_mapping}"


class TestEnvironmentManagerOperations:
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

        # Create environment (should already exist)
        result = self.manager.create_environment(env_name)
        assert result["success"], f"Failed to create {env_name}: {result['message']}"

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
