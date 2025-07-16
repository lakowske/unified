"""Test configuration for DNS and Mail integration tests.

This module provides fixtures and configuration for DNS mail integration testing.
"""

import logging
import os
import subprocess
import time
from typing import Any, Dict

import pytest

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def dns_mail_config() -> Dict[str, Any]:
    """Configuration for DNS mail integration tests."""
    config = {
        "mail_domain": os.environ.get("MAIL_DOMAIN", "lab.sethlakowske.com"),
        "mail_server_ip": os.environ.get("MAIL_SERVER_IP", "192.168.0.156"),
        "dns_server": os.environ.get("DNS_SERVER", "localhost"),
        "dns_port": int(os.environ.get("DNS_PORT", "53")),
        "test_timeout": 30,
        "retry_attempts": 3,
        "retry_delay": 2,
    }

    logger.info(f"DNS mail integration test configuration: {config}")
    return config


@pytest.fixture(scope="session")
def ensure_services_running(dns_mail_config):
    """Ensure DNS and mail services are running before tests."""
    logger.info("Checking if DNS and mail services are running...")

    # Check DNS service
    dns_ok = False
    for attempt in range(dns_mail_config["retry_attempts"]):
        try:
            result = subprocess.run(
                [
                    "dig",
                    f"@{dns_mail_config['dns_server']}",
                    "-p",
                    str(dns_mail_config["dns_port"]),
                    ".",
                    "NS",
                    "+short",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0:
                dns_ok = True
                break
            logger.warning(f"DNS check attempt {attempt + 1} failed: {result.stderr}")

        except subprocess.TimeoutExpired:
            logger.warning(f"DNS check attempt {attempt + 1} timed out")
        except Exception as e:
            logger.warning(f"DNS check attempt {attempt + 1} error: {e}")

        if attempt < dns_mail_config["retry_attempts"] - 1:
            time.sleep(dns_mail_config["retry_delay"])

    if not dns_ok:
        pytest.skip("DNS server not running - skipping DNS integration tests")

    # Check mail domain DNS resolution
    mail_domain_ok = False
    for attempt in range(dns_mail_config["retry_attempts"]):
        try:
            result = subprocess.run(
                [
                    "dig",
                    f"@{dns_mail_config['dns_server']}",
                    "-p",
                    str(dns_mail_config["dns_port"]),
                    dns_mail_config["mail_domain"],
                    "A",
                    "+short",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0 and result.stdout.strip():
                mail_domain_ok = True
                break
            logger.warning(f"Mail domain check attempt {attempt + 1} failed: {result.stderr}")

        except subprocess.TimeoutExpired:
            logger.warning(f"Mail domain check attempt {attempt + 1} timed out")
        except Exception as e:
            logger.warning(f"Mail domain check attempt {attempt + 1} error: {e}")

        if attempt < dns_mail_config["retry_attempts"] - 1:
            time.sleep(dns_mail_config["retry_delay"])

    if not mail_domain_ok:
        pytest.skip(f"Mail domain {dns_mail_config['mail_domain']} not resolvable - skipping tests")

    logger.info("DNS and mail services verified as running")
    return True


@pytest.fixture
def dns_query_helper(dns_mail_config):
    """Helper function for DNS queries."""

    def query_dns(domain: str, record_type: str, timeout: int = 5):
        """Query DNS with retry logic."""
        for attempt in range(dns_mail_config["retry_attempts"]):
            try:
                result = subprocess.run(
                    [
                        "dig",
                        f"@{dns_mail_config['dns_server']}",
                        "-p",
                        str(dns_mail_config["dns_port"]),
                        domain,
                        record_type,
                        "+short",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )

                if result.returncode == 0:
                    records = [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
                    return True, records
                logger.warning(f"DNS query attempt {attempt + 1} failed for {domain} {record_type}: {result.stderr}")

            except subprocess.TimeoutExpired:
                logger.warning(f"DNS query attempt {attempt + 1} timed out for {domain} {record_type}")
            except Exception as e:
                logger.warning(f"DNS query attempt {attempt + 1} error for {domain} {record_type}: {e}")

            if attempt < dns_mail_config["retry_attempts"] - 1:
                time.sleep(dns_mail_config["retry_delay"])

        return False, []

    return query_dns


@pytest.fixture
def mail_record_validator():
    """Validator for mail-related DNS records."""

    class MailRecordValidator:
        @staticmethod
        def validate_spf(record: str, expected_ip: str) -> bool:
            """Validate SPF record."""
            record = record.strip('"')
            return (
                record.startswith("v=spf1")
                and f"ip4:{expected_ip}" in record
                and ("~all" in record or "-all" in record)
            )

        @staticmethod
        def validate_dmarc(record: str, domain: str) -> bool:
            """Validate DMARC record."""
            record = record.strip('"')
            return record.startswith("v=DMARC1") and "p=" in record and "rua=mailto:" in record and domain in record

        @staticmethod
        def validate_dkim(record: str) -> bool:
            """Validate DKIM record."""
            record = record.strip('"')
            return (
                "v=DKIM1" in record
                and "k=rsa" in record
                and "p=" in record
                and len(record) > 100  # Should have substantial public key
            )

        @staticmethod
        def validate_mx(record: str, domain: str) -> bool:
            """Validate MX record."""
            parts = record.split()
            return len(parts) >= 2 and parts[0].isdigit() and parts[1].rstrip(".").endswith(domain)

    return MailRecordValidator()


@pytest.fixture
def performance_tracker():
    """Track DNS query performance."""

    class PerformanceTracker:
        def __init__(self):
            self.measurements = {}

        def measure_query(self, query_func, domain: str, record_type: str):
            """Measure DNS query performance."""
            start_time = time.time()
            success, records = query_func(domain, record_type)
            end_time = time.time()

            query_time = end_time - start_time
            key = f"{domain}:{record_type}"
            self.measurements[key] = query_time

            return success, records, query_time

        def get_average_time(self) -> float:
            """Get average query time."""
            if not self.measurements:
                return 0.0
            return sum(self.measurements.values()) / len(self.measurements)

        def get_slowest_query(self) -> tuple:
            """Get slowest query."""
            if not self.measurements:
                return None, 0.0
            slowest = max(self.measurements.items(), key=lambda x: x[1])
            return slowest[0], slowest[1]

    return PerformanceTracker()


def pytest_configure(config):
    """Configure pytest for DNS mail integration tests."""
    # Add custom markers
    config.addinivalue_line("markers", "dns_integration: mark test as DNS integration test")
    config.addinivalue_line("markers", "mail_integration: mark test as mail integration test")
    config.addinivalue_line("markers", "requires_dns_server: mark test as requiring DNS server")
    config.addinivalue_line("markers", "requires_mail_server: mark test as requiring mail server")


def pytest_collection_modifyitems(config, items):
    """Modify test collection for DNS mail integration tests."""
    # Skip tests if DNS server not available
    dns_server = os.environ.get("DNS_SERVER", "localhost")
    dns_port = int(os.environ.get("DNS_PORT", "53"))

    try:
        import socket

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(1)
        result = sock.connect_ex((dns_server, dns_port))
        sock.close()
        dns_available = result == 0
    except Exception:
        dns_available = False

    if not dns_available:
        skip_dns = pytest.mark.skip(reason="DNS server not available")
        for item in items:
            if "dns_integration" in item.keywords or "requires_dns_server" in item.keywords:
                item.add_marker(skip_dns)


@pytest.fixture(scope="session", autouse=True)
def setup_logging():
    """Setup logging for DNS mail integration tests."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
    )

    # Set specific log levels for noisy modules
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)

    logger.info("DNS mail integration test logging configured")
