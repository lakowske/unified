"""Tests for the environment management system.

This module tests the core functionality of the environment management system
including configuration parsing, network queries, and environment isolation.
"""

from unittest.mock import Mock, patch

import pytest

from src.unified.cli import EnvironmentCLI, QueryCLI
from src.unified.environments import EnvironmentConfig, EnvironmentIsolation, EnvironmentManager, NetworkInfo


class TestEnvironmentConfig:
    """Test environment configuration parsing."""

    def test_parse_env_file(self, tmp_path):
        """Test parsing .env files."""
        # Create test environment file
        env_file = tmp_path / ".env.test"
        env_file.write_text("""
# Test environment file
ENVIRONMENT=test
DB_NAME=test_db
DB_USER=test_user
DB_PASSWORD="test_password"
API_KEY='secret_key'
PORT=8080
""")

        config = EnvironmentConfig(tmp_path)
        env_vars = config._parse_env_file(env_file)

        assert env_vars["ENVIRONMENT"] == "test"
        assert env_vars["DB_NAME"] == "test_db"
        assert env_vars["DB_USER"] == "test_user"
        assert env_vars["DB_PASSWORD"] == "test_password"
        assert env_vars["API_KEY"] == "secret_key"
        assert env_vars["PORT"] == "8080"

    def test_parse_compose_file(self, tmp_path):
        """Test parsing docker-compose.yml files."""
        # Create test compose file
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("""
version: '3.8'
services:
  web:
    image: nginx:latest
    ports:
      - "${WEB_PORT:-8080}:80"
    environment:
      - ENV=test
  db:
    image: postgres:13
    ports:
      - "5432:5432"
    environment:
      - POSTGRES_DB=testdb
""")

        config = EnvironmentConfig(tmp_path)
        compose_config = config._parse_compose_file(compose_file)

        assert compose_config["version"] == "3.8"
        assert "web" in compose_config["services"]
        assert "db" in compose_config["services"]
        assert compose_config["services"]["web"]["image"] == "nginx:latest"
        assert compose_config["services"]["db"]["image"] == "postgres:13"

    def test_port_mapping_parsing(self, tmp_path):
        """Test parsing port mappings."""
        # Create test files
        env_file = tmp_path / ".env.test"
        env_file.write_text("WEB_PORT=8080\nDB_PORT=5432")

        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("""
version: '3.8'
services:
  web:
    image: nginx:latest
    ports:
      - "${WEB_PORT}:80"
  db:
    image: postgres:13
    ports:
      - "${DB_PORT}:5432"
""")

        config = EnvironmentConfig(tmp_path)
        env_config = config.load_environment("test")

        # Check service configurations
        web_ports = env_config["service_configs"]["web"]["ports"]
        db_ports = env_config["service_configs"]["db"]["ports"]

        assert len(web_ports) == 1
        assert web_ports[0]["host_port"] == "8080"
        assert web_ports[0]["container_port"] == "80"

        assert len(db_ports) == 1
        assert db_ports[0]["host_port"] == "5432"
        assert db_ports[0]["container_port"] == "5432"

    def test_get_service_port(self, tmp_path):
        """Test getting service port."""
        # Create test files
        env_file = tmp_path / ".env.test"
        env_file.write_text("WEB_PORT=8080")

        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("""
version: '3.8'
services:
  web:
    image: nginx:latest
    ports:
      - "${WEB_PORT}:80"
""")

        config = EnvironmentConfig(tmp_path)
        config.load_environment("test")

        # Test getting port
        port = config.get_service_port("web")
        assert port == "8080"

        # Test getting specific container port
        port = config.get_service_port("web", "80")
        assert port == "8080"

        # Test non-existent service
        port = config.get_service_port("nonexistent")
        assert port is None


class TestNetworkInfo:
    """Test network information queries."""

    @patch("subprocess.run")
    def test_get_service_status(self, mock_run, tmp_path):
        """Test getting service status."""
        # Mock docker compose ps output
        mock_run.return_value = Mock(
            returncode=0, stdout='{"Service": "web", "State": "running", "Health": "healthy", "Ports": ["8080:80"]}\n'
        )

        # Create test files
        env_file = tmp_path / ".env.test"
        env_file.write_text("WEB_PORT=8080")

        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("""
version: '3.8'
services:
  web:
    image: nginx:latest
    ports:
      - "${WEB_PORT}:80"
""")

        network = NetworkInfo(tmp_path)
        status = network._get_service_status("test", "web")

        assert status["state"] == "running"
        assert status["health"] == "healthy"
        assert status["ports"] == ["8080:80"]

    def test_guess_protocol(self, tmp_path):
        """Test protocol guessing from port numbers."""
        network = NetworkInfo(tmp_path)

        assert network._guess_protocol("80") == "http"
        assert network._guess_protocol("443") == "https"
        assert network._guess_protocol("5432") == "postgresql"
        assert network._guess_protocol("25") == "smtp"
        assert network._guess_protocol("53") == "dns"
        assert network._guess_protocol("9999") == "tcp"  # Unknown port

    def test_find_service_by_port(self, tmp_path):
        """Test finding service by port."""
        # Create test files
        env_file = tmp_path / ".env.test"
        env_file.write_text("WEB_PORT=8080\nDB_PORT=5432")

        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("""
version: '3.8'
services:
  web:
    image: nginx:latest
    ports:
      - "${WEB_PORT}:80"
  db:
    image: postgres:13
    ports:
      - "${DB_PORT}:5432"
""")

        network = NetworkInfo(tmp_path)

        # Mock the get_network_topology method
        with patch.object(network, "get_network_topology") as mock_topology:
            mock_topology.return_value = {
                "port_mappings": {
                    "8080": {"service": "web", "container_port": "80"},
                    "5432": {"service": "db", "container_port": "5432"},
                }
            }

            assert network.find_service_by_port("test", "8080") == "web"
            assert network.find_service_by_port("test", "5432") == "db"
            assert network.find_service_by_port("test", "3000") is None


class TestEnvironmentIsolation:
    """Test environment isolation utilities."""

    def test_sanitize_branch_name(self, tmp_path):
        """Test branch name sanitization."""
        isolation = EnvironmentIsolation(tmp_path)

        assert isolation._sanitize_branch_name("feature/user-auth") == "feature_user_auth"
        assert isolation._sanitize_branch_name("bugfix/fix-login") == "bugfix_fix_login"
        assert isolation._sanitize_branch_name("FEATURE/USER-AUTH") == "feature_user_auth"
        assert isolation._sanitize_branch_name("very-long-branch-name-that-exceeds-limit" * 2)[
            :50
        ] == isolation._sanitize_branch_name("very-long-branch-name-that-exceeds-limit" * 2)

    def test_is_isolated_environment(self, tmp_path):
        """Test isolated environment detection."""
        isolation = EnvironmentIsolation(tmp_path)

        assert isolation._is_isolated_environment("test_123456_abc123") == True
        assert isolation._is_isolated_environment("feature_user_auth") == True
        assert isolation._is_isolated_environment("temp_987654_def456") is True
        assert not isolation._is_isolated_environment("dev")
        assert not isolation._is_isolated_environment("production")

    def test_get_environment_type(self, tmp_path):
        """Test environment type detection."""
        isolation = EnvironmentIsolation(tmp_path)

        assert isolation._get_environment_type("test_123456_abc123") == "test"
        assert isolation._get_environment_type("feature_user_auth") == "feature"
        assert isolation._get_environment_type("temp_987654_def456") == "temporary"
        assert isolation._get_environment_type("isolated_env") == "isolated"
        assert isolation._get_environment_type("dev") == "unknown"

    def test_find_available_ports(self, tmp_path):
        """Test finding available ports."""
        isolation = EnvironmentIsolation(tmp_path)

        # Mock socket operations
        with patch("socket.socket") as mock_socket:
            mock_socket.return_value.__enter__.return_value.bind.return_value = None

            ports = isolation.find_available_ports(3, 8000)

            assert len(ports) == 3
            assert all(port >= 8000 for port in ports)
            assert len(set(ports)) == 3  # All ports should be unique


class TestCLI:
    """Test CLI interfaces."""

    def test_environment_cli_parser(self):
        """Test environment CLI parser creation."""
        cli = EnvironmentCLI()
        parser = cli.create_parser()

        # Test basic parsing
        args = parser.parse_args(["list"])
        assert args.command == "list"

        args = parser.parse_args(["create", "test-env", "--template", "dev"])
        assert args.command == "create"
        assert args.name == "test-env"
        assert args.template == "dev"

        args = parser.parse_args(["start", "test-env", "--services", "web", "db"])
        assert args.command == "start"
        assert args.name == "test-env"
        assert args.services == ["web", "db"]

    def test_query_cli_parser(self):
        """Test query CLI parser creation."""
        cli = QueryCLI()
        parser = cli.create_parser()

        # Test basic parsing
        args = parser.parse_args(["port", "dev", "web"])
        assert args.command == "port"
        assert args.environment == "dev"
        assert args.service == "web"

        args = parser.parse_args(["url", "dev", "web", "--protocol", "https"])
        assert args.command == "url"
        assert args.environment == "dev"
        assert args.service == "web"
        assert args.protocol == "https"

        args = parser.parse_args(["quick", "dev", "what", "port", "is", "dns"])
        assert args.command == "quick"
        assert args.environment == "dev"
        assert args.query == ["what", "port", "is", "dns"]

    def test_parse_variables(self):
        """Test variable parsing in CLI."""
        cli = EnvironmentCLI()

        vars_list = ["KEY1=value1", "KEY2=value2", "KEY3=value with spaces"]
        result = cli._parse_variables(vars_list)

        expected = {"KEY1": "value1", "KEY2": "value2", "KEY3": "value with spaces"}

        assert result == expected

    def test_guess_protocol_in_query_cli(self):
        """Test protocol guessing in query CLI."""
        cli = QueryCLI()

        assert cli._guess_protocol("80") == "http"
        assert cli._guess_protocol("443") == "https"
        assert cli._guess_protocol("5432") == "postgresql"
        assert cli._guess_protocol("25") == "smtp"
        assert cli._guess_protocol("53") == "dns"
        assert cli._guess_protocol("9999") == "http"  # Default for unknown ports


class TestIntegration:
    """Integration tests for the environment management system."""

    def test_environment_lifecycle(self, tmp_path):
        """Test complete environment lifecycle."""
        # Create test files
        env_file = tmp_path / ".env.dev"
        env_file.write_text("ENVIRONMENT=dev\nWEB_PORT=8080")

        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("""
version: '3.8'
services:
  web:
    image: nginx:latest
    ports:
      - "${WEB_PORT}:80"
""")

        manager = EnvironmentManager(tmp_path)

        # Test listing environments
        environments = manager.list_environments()
        assert "dev" in environments

        # Test creating environment
        success = manager.create_environment("test", "dev", {"TEST_VAR": "test_value"})
        assert success

        # Verify test environment was created
        test_env_file = tmp_path / ".env.test"
        assert test_env_file.exists()

        content = test_env_file.read_text()
        assert "ENVIRONMENT=test" in content
        assert "TEST_VAR=test_value" in content

    def test_network_queries(self, tmp_path):
        """Test network information queries."""
        # Create test files
        env_file = tmp_path / ".env.test"
        env_file.write_text("WEB_PORT=8080\nDB_PORT=5432")

        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("""
version: '3.8'
services:
  web:
    image: nginx:latest
    ports:
      - "${WEB_PORT}:80"
  db:
    image: postgres:13
    ports:
      - "${DB_PORT}:5432"
""")

        config = EnvironmentConfig(tmp_path)
        config.load_environment("test")

        # Test getting service ports
        web_port = config.get_service_port("web")
        assert web_port == "8080"

        db_port = config.get_service_port("db")
        assert db_port == "5432"

        # Test getting service URLs
        web_url = config.get_service_url("web")
        assert web_url == "http://localhost:8080"

        # Test listing services
        services = config.list_services()
        assert "web" in services
        assert "db" in services

    def test_configuration_validation(self, tmp_path):
        """Test configuration validation."""
        # Create test files with missing required variables
        env_file = tmp_path / ".env.test"
        env_file.write_text("ENVIRONMENT=test")  # Missing DB_* variables

        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("""
version: '3.8'
services:
  web:
    image: nginx:latest
    ports:
      - "8080:80"
  db:
    image: postgres:13
    ports:
      - "5432:5432"
""")

        config = EnvironmentConfig(tmp_path)
        config.load_environment("test")

        validation = config.validate_configuration()

        # Should have errors for missing variables
        assert not validation["valid"]
        assert len(validation["errors"]) > 0
        assert any("DB_NAME" in error for error in validation["errors"])
        assert any("DB_USER" in error for error in validation["errors"])
        assert any("DB_PASSWORD" in error for error in validation["errors"])


# Integration test fixtures
@pytest.fixture
def sample_environment(tmp_path):
    """Create a sample environment for testing."""
    # Create .env.test file
    env_file = tmp_path / ".env.test"
    env_file.write_text("""
ENVIRONMENT=test
DB_NAME=test_db
DB_USER=test_user
DB_PASSWORD=test_password
WEB_PORT=8080
DB_PORT=5432
""")

    # Create docker-compose.yml
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text("""
version: '3.8'
services:
  web:
    image: nginx:latest
    ports:
      - "${WEB_PORT}:80"
    depends_on:
      - db
  db:
    image: postgres:13
    ports:
      - "${DB_PORT}:5432"
    environment:
      - POSTGRES_DB=${DB_NAME}
      - POSTGRES_USER=${DB_USER}
      - POSTGRES_PASSWORD=${DB_PASSWORD}
""")

    return tmp_path
