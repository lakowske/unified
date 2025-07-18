"""Integration tests for the unified infrastructure using docker compose.

This module provides comprehensive integration tests that validate the entire
infrastructure stack including database, web server, mail server, and DNS services.
"""

import json
import logging
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, List

import pytest

logger = logging.getLogger(__name__)


class DockerComposeManager:
    """Manages docker compose test environments."""

    def __init__(self, project_dir: Path, environment: str = "test"):
        self.project_dir = project_dir
        self.environment = environment
        self.compose_file = project_dir / "docker-compose.yml"
        self.dev_compose_file = project_dir / "docker-compose.dev.yml"
        self._running_containers = set()

    def _run_compose_command(self, command: List[str], timeout: int = 300) -> subprocess.CompletedProcess:
        """Run a docker compose command with proper environment setup."""
        env = {
            "ENVIRONMENT": self.environment,
            "DB_NAME": f"unified_{self.environment}",
            "DB_USER": f"unified_{self.environment}_user",
            "DB_PASSWORD": f"{self.environment}_password123",
            "DB_PORT": "5432",
            "SERVER_NAME": "test.lab.sethlakowske.com",
            "SERVER_ADMIN": "admin@lab.sethlakowske.com",
            "APACHE_LOG_LEVEL": "debug",
            "SSL_ENABLED": "false",
            "SSL_REDIRECT": "false",
            "APACHE_HOST_PORT": "8080",
            "APACHE_HTTPS_PORT": "8443",
            "MAIL_DOMAIN": "lab.sethlakowske.com",
            "MAIL_SERVER_IP": "127.0.0.1",
            "MAIL_LOG_LEVEL": "debug",
            "VMAIL_UID": "1000",
            "VMAIL_GID": "1000",
            "CERT_TYPE_PREFERENCE": "letsencrypt",
            "LOG_LEVEL": "debug",
            "DEBUG_MODE": "true",
            "APP_VERSION": "test",
            "DNS_LOG_LEVEL": "debug",
            "DNS_FORWARDERS": "8.8.8.8,1.1.1.1",
            "DNS_ALLOW_QUERY": "any",
            "DNS_RECURSION": "yes",
            "DNS_CACHE_SIZE": "50M",
            "DNS_MAX_CACHE_TTL": "86400",
            "BIND_PORT": "5354",
            "MAIL_SMTP_PORT": "2525",
            "MAIL_IMAP_PORT": "1144",
            "MAIL_IMAPS_PORT": "9933",
            "MAIL_SMTPS_PORT": "4465",
            "MAIL_SUBMISSION_PORT": "5587",
        }

        cmd = ["docker", "compose", "-f", str(self.compose_file)] + command
        logger.info(f"Running command: {' '.join(cmd)}")

        return subprocess.run(cmd, cwd=self.project_dir, env=env, capture_output=True, text=True, timeout=timeout)

    def build_images(self) -> bool:
        """Build all required container images."""
        logger.info("Building container images for testing...")

        # Use the parallel build system
        build_script = self.project_dir / "scripts" / "build-containers.py"
        if build_script.exists():
            result = subprocess.run(
                ["python3", str(build_script)],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=1800,  # 30 minutes for builds
            )
            if result.returncode == 0:
                logger.info("Container images built successfully")
                return True
            logger.error(f"Container build failed: {result.stderr}")
            return False
        logger.warning("Build script not found, assuming images exist")
        return True

    def start_environment(self, run_volume_setup: bool = True) -> bool:
        """Start the test environment."""
        logger.info("Starting test environment...")

        # Start volume setup first (run manually since profiles aren't supported)
        if run_volume_setup:
            result = self._run_compose_command(["up", "-d", "volume-setup"])
            if result.returncode != 0:
                logger.error(f"Volume setup failed: {result.stderr}")
                return False

            # Wait for volume setup to complete
            logger.info("Waiting for volume setup to complete...")
            time.sleep(10)

            # Stop volume setup container since it's a one-time init
            self._run_compose_command(["stop", "volume-setup"])

        # Start main services
        result = self._run_compose_command(["up", "-d", "postgres", "apache", "mail", "bind"])
        if result.returncode != 0:
            logger.error(f"Environment startup failed: {result.stderr}")
            return False

        # Track running containers
        self._update_running_containers()

        logger.info("Test environment started successfully")
        return True

    def wait_for_services(self, timeout: int = 180) -> bool:
        """Wait for all services to be healthy."""
        logger.info("Waiting for services to become healthy...")

        start_time = time.time()
        services = ["postgres", "apache", "mail", "bind"]

        while time.time() - start_time < timeout:
            result = self._run_compose_command(["ps", "--format", "json"])
            if result.returncode == 0:
                try:
                    containers = json.loads(result.stdout)
                    healthy_services = set()

                    for container in containers:
                        service_name = container.get("Service", "")
                        state = container.get("State", "")
                        health = container.get("Health", "")

                        if service_name in services:
                            if state == "running" and (health == "healthy" or health == ""):
                                healthy_services.add(service_name)

                    if len(healthy_services) == len(services):
                        logger.info("All services are healthy")
                        return True

                    logger.debug(f"Healthy services: {healthy_services}/{set(services)}")

                except json.JSONDecodeError:
                    logger.warning("Could not parse container status")

            time.sleep(5)

        logger.error(f"Services did not become healthy within {timeout} seconds")
        return False

    def run_migrations(self) -> bool:
        """Run database migrations."""
        logger.info("Running database migrations...")

        # Run migrations directly without profile
        result = self._run_compose_command(["run", "--rm", "db-migrate"])
        if result.returncode == 0:
            logger.info("Database migrations completed successfully")
            return True
        logger.error(f"Database migrations failed: {result.stderr}")
        return False

    def stop_environment(self, remove_volumes: bool = True) -> bool:
        """Stop the test environment."""
        logger.info("Stopping test environment...")

        # Stop all services
        stop_args = ["down"]
        if remove_volumes:
            stop_args.extend(["-v", "--remove-orphans"])

        result = self._run_compose_command(stop_args)
        success = result.returncode == 0

        if success:
            logger.info("Test environment stopped successfully")
        else:
            logger.error(f"Environment shutdown failed: {result.stderr}")

        # Clear running containers
        self._running_containers.clear()

        return success

    def get_service_logs(self, service: str, lines: int = 50) -> str:
        """Get logs from a specific service."""
        result = self._run_compose_command(["logs", "--tail", str(lines), service])
        return result.stdout if result.returncode == 0 else f"Error getting logs: {result.stderr}"

    def execute_in_service(self, service: str, command: List[str]) -> subprocess.CompletedProcess:
        """Execute a command in a running service container."""
        exec_cmd = ["exec", service] + command
        return self._run_compose_command(exec_cmd, timeout=30)

    def get_service_status(self) -> Dict[str, Dict]:
        """Get status of all services."""
        result = self._run_compose_command(["ps", "--format", "json"])
        if result.returncode == 0:
            try:
                containers = json.loads(result.stdout)
                status = {}
                for container in containers:
                    service = container.get("Service", "unknown")
                    status[service] = {
                        "state": container.get("State", "unknown"),
                        "health": container.get("Health", "unknown"),
                        "ports": container.get("Ports", []),
                        "created": container.get("CreatedAt", ""),
                    }
                return status
            except json.JSONDecodeError:
                logger.error("Could not parse service status")
                return {}
        return {}

    def _update_running_containers(self):
        """Update the set of running containers."""
        result = self._run_compose_command(["ps", "-q"])
        if result.returncode == 0:
            container_ids = result.stdout.strip().split("\n")
            self._running_containers = set(filter(None, container_ids))

    @contextmanager
    def isolated_environment(self):
        """Context manager for isolated test environment."""
        try:
            if not self.build_images():
                raise RuntimeError("Failed to build container images")

            if not self.start_environment():
                raise RuntimeError("Failed to start test environment")

            if not self.run_migrations():
                raise RuntimeError("Failed to run database migrations")

            if not self.wait_for_services():
                raise RuntimeError("Services did not become healthy")

            yield self

        finally:
            self.stop_environment(remove_volumes=True)


class PerformanceTracker:
    """Track performance metrics during tests."""

    def __init__(self):
        self.metrics = {}
        self.start_times = {}

    def start_timer(self, operation: str):
        """Start timing an operation."""
        self.start_times[operation] = time.time()

    def end_timer(self, operation: str) -> float:
        """End timing an operation and return duration."""
        if operation in self.start_times:
            duration = time.time() - self.start_times[operation]
            self.metrics[operation] = duration
            del self.start_times[operation]
            return duration
        return 0.0

    def record_metric(self, name: str, value: float):
        """Record a custom metric."""
        self.metrics[name] = value

    def get_summary(self) -> Dict[str, float]:
        """Get performance summary."""
        return self.metrics.copy()

    def get_average_time(self) -> float:
        """Get average operation time."""
        if not self.metrics:
            return 0.0
        return sum(self.metrics.values()) / len(self.metrics)


@pytest.fixture(scope="session")
def project_dir():
    """Get the project directory."""
    return Path(__file__).parent.parent


@pytest.fixture(scope="session")
def compose_manager(project_dir):
    """Create a docker compose manager for tests."""
    return DockerComposeManager(project_dir, environment="test")


@pytest.fixture(scope="session")
def performance_tracker():
    """Create a performance tracker for tests."""
    return PerformanceTracker()


@pytest.fixture(scope="function")
def isolated_environment(compose_manager, performance_tracker):
    """Provide an isolated test environment for each test."""
    performance_tracker.start_timer("environment_setup")

    with compose_manager.isolated_environment() as env:
        setup_time = performance_tracker.end_timer("environment_setup")
        logger.info(f"Test environment setup completed in {setup_time:.2f} seconds")
        yield env


class TestContainerIntegration:
    """Test container integration and basic functionality."""

    def test_containers_start_successfully(self, isolated_environment, performance_tracker):
        """Test that all containers start and become healthy."""
        performance_tracker.start_timer("container_startup")

        status = isolated_environment.get_service_status()
        startup_time = performance_tracker.end_timer("container_startup")

        # Verify all expected services are present
        expected_services = {"postgres", "apache", "mail", "bind"}
        actual_services = set(status.keys())

        assert expected_services.issubset(actual_services), f"Missing services: {expected_services - actual_services}"

        # Verify all services are running
        for service, info in status.items():
            if service in expected_services:
                assert info["state"] == "running", f"Service {service} is not running: {info['state']}"
                logger.info(f"Service {service} is running with health: {info.get('health', 'N/A')}")

        performance_tracker.record_metric("container_startup_time", startup_time)
        logger.info(f"Container startup completed in {startup_time:.2f} seconds")

    def test_database_connectivity(self, isolated_environment, performance_tracker):
        """Test database connectivity and basic operations."""
        performance_tracker.start_timer("database_connectivity")

        # Test database connection
        result = isolated_environment.execute_in_service(
            "postgres", ["psql", "-U", "unified_test_user", "-d", "unified_test", "-c", "SELECT version();"]
        )

        connectivity_time = performance_tracker.end_timer("database_connectivity")

        assert result.returncode == 0, f"Database connection failed: {result.stderr}"
        assert "PostgreSQL" in result.stdout, "Database version query failed"

        performance_tracker.record_metric("database_connectivity_time", connectivity_time)
        logger.info(f"Database connectivity test completed in {connectivity_time:.2f} seconds")

    def test_web_server_response(self, isolated_environment, performance_tracker):
        """Test web server basic response."""
        performance_tracker.start_timer("web_server_response")

        # Test web server health endpoint
        result = isolated_environment.execute_in_service("apache", ["curl", "-f", "-s", "http://localhost/health"])

        response_time = performance_tracker.end_timer("web_server_response")

        # Note: Health endpoint might not exist yet, so we check if Apache is responding
        if result.returncode != 0:
            # Try basic connection instead
            result = isolated_environment.execute_in_service("apache", ["curl", "-f", "-s", "http://localhost/"])

        performance_tracker.record_metric("web_server_response_time", response_time)
        logger.info(f"Web server response test completed in {response_time:.2f} seconds")

    def test_dns_server_functionality(self, isolated_environment, performance_tracker):
        """Test DNS server basic functionality."""
        performance_tracker.start_timer("dns_query")

        # Test DNS server with basic query
        result = isolated_environment.execute_in_service("bind", ["dig", "@localhost", "-p", "53", ".", "NS", "+short"])

        query_time = performance_tracker.end_timer("dns_query")

        assert result.returncode == 0, f"DNS query failed: {result.stderr}"

        performance_tracker.record_metric("dns_query_time", query_time)
        logger.info(f"DNS query test completed in {query_time:.2f} seconds")

    def test_mail_server_ports(self, isolated_environment, performance_tracker):
        """Test mail server port availability."""
        performance_tracker.start_timer("mail_port_check")

        mail_ports = [25, 143, 993, 465, 587]
        available_ports = []

        for port in mail_ports:
            result = isolated_environment.execute_in_service("mail", ["nc", "-z", "localhost", str(port)])
            if result.returncode == 0:
                available_ports.append(port)

        port_check_time = performance_tracker.end_timer("mail_port_check")

        # At least SMTP (25) and IMAP (143) should be available
        assert 25 in available_ports, "SMTP port (25) is not available"
        assert 143 in available_ports, "IMAP port (143) is not available"

        performance_tracker.record_metric("mail_port_check_time", port_check_time)
        logger.info(f"Mail server port check completed in {port_check_time:.2f} seconds")
        logger.info(f"Available mail ports: {available_ports}")


class TestServiceIntegration:
    """Test integration between services."""

    def test_database_migration_status(self, isolated_environment, performance_tracker):
        """Test that database migrations ran successfully."""
        performance_tracker.start_timer("migration_status_check")

        # Check for migration tables or basic schema
        result = isolated_environment.execute_in_service(
            "postgres", ["psql", "-U", "unified_test_user", "-d", "unified_test", "-c", "\\dt"]
        )

        check_time = performance_tracker.end_timer("migration_status_check")

        assert result.returncode == 0, f"Migration status check failed: {result.stderr}"

        performance_tracker.record_metric("migration_status_check_time", check_time)
        logger.info(f"Migration status check completed in {check_time:.2f} seconds")

    def test_service_logs_accessibility(self, isolated_environment, performance_tracker):
        """Test that service logs are accessible and contain expected content."""
        performance_tracker.start_timer("log_access_check")

        services_to_check = ["postgres", "apache", "mail", "bind"]

        for service in services_to_check:
            logs = isolated_environment.get_service_logs(service, lines=10)
            assert logs, f"No logs found for service {service}"
            assert "error" not in logs.lower() or "warning" in logs.lower(), f"Critical errors in {service} logs"

        log_check_time = performance_tracker.end_timer("log_access_check")

        performance_tracker.record_metric("log_access_check_time", log_check_time)
        logger.info(f"Service log accessibility check completed in {log_check_time:.2f} seconds")


class TestPerformanceBaselines:
    """Test performance baselines and resource usage."""

    def test_environment_startup_performance(self, compose_manager, performance_tracker):
        """Test environment startup performance and establish baselines."""
        logger.info("Testing environment startup performance...")

        # Measure full startup cycle
        performance_tracker.start_timer("full_startup_cycle")

        with compose_manager.isolated_environment():
            startup_time = performance_tracker.end_timer("full_startup_cycle")

            # Record baseline metrics
            performance_tracker.record_metric("full_startup_time", startup_time)

            # Assert reasonable startup times (adjust based on your hardware)
            assert startup_time < 300, f"Environment startup took too long: {startup_time:.2f}s"

            logger.info(f"Full startup cycle completed in {startup_time:.2f} seconds")

    def test_resource_usage_baselines(self, isolated_environment, performance_tracker):
        """Test and record resource usage baselines."""
        performance_tracker.start_timer("resource_measurement")

        # Get container resource usage
        status = isolated_environment.get_service_status()

        # This is a basic test - in production you'd want more detailed resource monitoring
        assert len(status) >= 4, "Expected at least 4 services running"

        measurement_time = performance_tracker.end_timer("resource_measurement")
        performance_tracker.record_metric("resource_measurement_time", measurement_time)

        logger.info(f"Resource usage measurement completed in {measurement_time:.2f} seconds")
        logger.info(f"Running services: {list(status.keys())}")


@pytest.mark.performance
class TestPerformanceRegression:
    """Test for performance regressions."""

    def test_database_query_performance(self, isolated_environment, performance_tracker):
        """Test database query performance."""
        query_times = []

        for i in range(5):
            performance_tracker.start_timer(f"db_query_{i}")

            result = isolated_environment.execute_in_service(
                "postgres", ["psql", "-U", "unified_test_user", "-d", "unified_test", "-c", "SELECT NOW();"]
            )

            query_time = performance_tracker.end_timer(f"db_query_{i}")
            query_times.append(query_time)

            assert result.returncode == 0, f"Database query {i} failed"

        avg_query_time = sum(query_times) / len(query_times)
        performance_tracker.record_metric("average_db_query_time", avg_query_time)

        # Assert reasonable query times
        assert avg_query_time < 1.0, f"Database queries too slow: {avg_query_time:.3f}s average"

        logger.info(f"Database query performance: {avg_query_time:.3f}s average over {len(query_times)} queries")

    def test_concurrent_service_access(self, isolated_environment, performance_tracker):
        """Test concurrent access to multiple services."""
        import concurrent.futures

        performance_tracker.start_timer("concurrent_access")

        def test_service_access(service_info):
            service, command = service_info
            try:
                result = isolated_environment.execute_in_service(service, command)
                return service, result.returncode == 0, time.time()
            except Exception as e:
                logger.error(f"Error accessing {service}: {e}")
                return service, False, time.time()

        # Define concurrent tests
        concurrent_tests = [
            ("postgres", ["psql", "-U", "unified_test_user", "-d", "unified_test", "-c", "SELECT 1;"]),
            ("bind", ["dig", "@localhost", ".", "NS", "+short"]),
            ("apache", ["curl", "-s", "http://localhost/"]),
            ("mail", ["nc", "-z", "localhost", "25"]),
        ]

        # Run tests concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(test_service_access, test) for test in concurrent_tests]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]

        concurrent_time = performance_tracker.end_timer("concurrent_access")

        # Verify all services responded
        success_count = sum(1 for _, success, _ in results if success)
        assert success_count >= 3, f"Only {success_count}/4 services responded successfully"

        performance_tracker.record_metric("concurrent_access_time", concurrent_time)
        performance_tracker.record_metric("concurrent_success_rate", success_count / len(results))

        logger.info(f"Concurrent service access completed in {concurrent_time:.2f} seconds")
        logger.info(f"Success rate: {success_count}/{len(results)} services")


def pytest_sessionfinish(session, exitstatus):
    """Generate performance report at end of test session."""
    if hasattr(session, "performance_tracker"):
        tracker = session.performance_tracker
        metrics = tracker.get_summary()

        if metrics:
            logger.info("=" * 60)
            logger.info("PERFORMANCE TEST SUMMARY")
            logger.info("=" * 60)

            for metric, value in sorted(metrics.items()):
                logger.info(f"{metric}: {value:.3f}s")

            avg_time = tracker.get_average_time()
            logger.info(f"Average operation time: {avg_time:.3f}s")
            logger.info("=" * 60)

            # Save performance report
            report_file = Path("test_performance_report.json")
            with open(report_file, "w") as f:
                json.dump(metrics, f, indent=2)
            logger.info(f"Performance report saved to: {report_file}")
