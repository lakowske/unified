import logging
import os
import socket

import pytest

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
)
logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def dns_config():
    """Configuration for DNS server connection."""
    return {
        "dns_host": os.getenv("DNS_HOST", "localhost"),
        "dns_port": int(os.getenv("DNS_PORT", "53")),
        "dns_tcp_port": int(os.getenv("DNS_TCP_PORT", "53")),
        "dns_control_port": int(os.getenv("DNS_CONTROL_PORT", "953")),
        "test_domain": os.getenv("TEST_DOMAIN", "example.com"),
        "upstream_dns": os.getenv("UPSTREAM_DNS", "8.8.8.8"),
    }


@pytest.fixture
def dns_client(dns_config):
    """Create a DNS client socket for testing."""

    def _create_udp_client():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(5)
        return sock

    def _create_tcp_client():
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        return sock

    return {
        "udp": _create_udp_client,
        "tcp": _create_tcp_client,
        "host": dns_config["dns_host"],
        "port": dns_config["dns_port"],
    }
