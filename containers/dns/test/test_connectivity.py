import logging
import socket
import struct
import subprocess
import time

import pytest

logger = logging.getLogger(__name__)


class TestDNSConnectivity:
    """Test basic DNS server connectivity."""

    def test_dns_udp_port_accessible(self, dns_config):
        """Test that DNS UDP port is accessible."""
        host = dns_config["dns_host"]
        port = dns_config["dns_port"]

        logger.info(f"Testing DNS UDP port accessibility - host: {host}, port: {port}")

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(5)

            # Send a basic DNS query (root NS query)
            query = self._create_dns_query(".", "NS")
            sock.sendto(query, (host, port))

            # Receive response
            response, _ = sock.recvfrom(512)
            assert len(response) > 0, "Should receive DNS response"

            logger.info(f"DNS UDP port accessible - received {len(response)} bytes")

        except Exception as e:
            pytest.fail(f"DNS UDP port not accessible - error: {str(e)}")
        finally:
            sock.close()

    def test_dns_tcp_port_accessible(self, dns_config):
        """Test that DNS TCP port is accessible."""
        host = dns_config["dns_host"]
        port = dns_config["dns_tcp_port"]

        logger.info(f"Testing DNS TCP port accessibility - host: {host}, port: {port}")

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((host, port))

            # Send a basic DNS query with length prefix for TCP
            query = self._create_dns_query(".", "NS")
            length_prefix = struct.pack("!H", len(query))
            sock.send(length_prefix + query)

            # Receive response length
            length_data = sock.recv(2)
            assert len(length_data) == 2, "Should receive length prefix"

            response_length = struct.unpack("!H", length_data)[0]
            assert response_length > 0, "Response should have content"

            logger.info(f"DNS TCP port accessible - response length: {response_length}")

        except Exception as e:
            pytest.fail(f"DNS TCP port not accessible - error: {str(e)}")
        finally:
            sock.close()

    def test_dns_server_responds_to_queries(self, dns_config):
        """Test that DNS server responds to basic queries."""
        host = dns_config["dns_host"]
        port = dns_config["dns_port"]
        test_domain = dns_config["test_domain"]

        logger.info(f"Testing DNS query response - domain: {test_domain}")

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(5)

            # Send A record query for test domain
            query = self._create_dns_query(test_domain, "A")
            sock.sendto(query, (host, port))

            # Receive response
            response, _ = sock.recvfrom(512)
            assert len(response) >= 12, "DNS response should be at least 12 bytes (header)"

            # Parse basic response header
            header = struct.unpack("!HHHHHH", response[:12])
            query_id, flags, questions, answers, authority, additional = header

            # Check that it's a response (QR bit set)
            assert flags & 0x8000, "Response should have QR bit set"

            logger.info(f"DNS query successful - questions: {questions}, answers: {answers}")

        except Exception as e:
            pytest.fail(f"DNS query failed - error: {str(e)}")
        finally:
            sock.close()

    def _create_dns_query(self, domain, record_type):
        """Create a simple DNS query packet."""
        # DNS header
        query_id = 0x1234
        flags = 0x0100  # Standard query, recursion desired
        questions = 1
        answers = 0
        authority = 0
        additional = 0

        header = struct.pack("!HHHHHH", query_id, flags, questions, answers, authority, additional)

        # DNS question
        question = b""
        for part in domain.split("."):
            if part:
                question += struct.pack("!B", len(part)) + part.encode()
        question += b"\x00"  # End of domain name

        # Query type and class
        if record_type == "A":
            qtype = 1
        elif record_type == "NS":
            qtype = 2
        elif record_type == "CNAME":
            qtype = 5
        else:
            qtype = 1  # Default to A record

        qclass = 1  # IN (Internet)
        question += struct.pack("!HH", qtype, qclass)

        return header + question


class TestDNSService:
    """Test DNS service functionality."""

    def test_dns_service_health(self, dns_config):
        """Test DNS service health using dig command."""
        host = dns_config["dns_host"]
        port = dns_config["dns_port"]

        logger.info(f"Testing DNS service health - host: {host}, port: {port}")

        try:
            # Use dig to test DNS service
            result = subprocess.run(
                ["dig", f"@{host}", "-p", str(port), ".", "NS"], capture_output=True, text=True, timeout=10
            )

            assert result.returncode == 0, f"dig command failed with return code {result.returncode}"
            assert (
                "ANSWER:" in result.stdout or "AUTHORITY:" in result.stdout
            ), "DNS response should contain answer or authority section"

            logger.info("DNS service health check passed")

        except subprocess.TimeoutExpired:
            pytest.fail("DNS service health check timed out")
        except Exception as e:
            pytest.fail(f"DNS service health check failed - error: {str(e)}")

    def test_dns_forwarding_works(self, dns_config):
        """Test that DNS forwarding to upstream servers works."""
        host = dns_config["dns_host"]
        port = dns_config["dns_port"]
        test_domain = dns_config["test_domain"]

        logger.info(f"Testing DNS forwarding - domain: {test_domain}")

        try:
            # Query a well-known domain that should be forwarded
            result = subprocess.run(
                ["dig", f"@{host}", "-p", str(port), test_domain, "A"], capture_output=True, text=True, timeout=10
            )

            assert result.returncode == 0, f"dig command failed with return code {result.returncode}"

            # Check that we got some kind of response (even if NXDOMAIN)
            assert "Query time:" in result.stdout, "DNS query should complete"

            logger.info("DNS forwarding test passed")

        except subprocess.TimeoutExpired:
            pytest.fail("DNS forwarding test timed out")
        except Exception as e:
            pytest.fail(f"DNS forwarding test failed - error: {str(e)}")


class TestDNSPerformance:
    """Test DNS performance characteristics."""

    def test_dns_query_response_time(self, dns_config):
        """Test that DNS queries respond within reasonable time."""
        host = dns_config["dns_host"]
        port = dns_config["dns_port"]

        logger.info("Testing DNS query response time")

        try:
            start_time = time.time()

            result = subprocess.run(
                ["dig", f"@{host}", "-p", str(port), ".", "NS"], capture_output=True, text=True, timeout=5
            )

            end_time = time.time()
            response_time = end_time - start_time

            assert result.returncode == 0, "DNS query should succeed"
            assert response_time < 2.0, f"DNS query should respond within 2 seconds, took {response_time:.2f}s"

            logger.info(f"DNS query response time: {response_time:.2f}s")

        except subprocess.TimeoutExpired:
            pytest.fail("DNS query response time test timed out")
        except Exception as e:
            pytest.fail(f"DNS query response time test failed - error: {str(e)}")

    def test_concurrent_dns_queries(self, dns_config):
        """Test that DNS server can handle multiple concurrent queries."""
        host = dns_config["dns_host"]
        port = dns_config["dns_port"]

        logger.info("Testing concurrent DNS queries")

        import threading

        results = []

        def make_query():
            try:
                result = subprocess.run(
                    ["dig", f"@{host}", "-p", str(port), ".", "NS"], capture_output=True, text=True, timeout=5
                )
                results.append(result.returncode == 0)
            except:
                results.append(False)

        # Start multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=make_query)
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Check results
        successful_queries = sum(results)
        assert (
            successful_queries >= 4
        ), f"At least 4 out of 5 concurrent queries should succeed, got {successful_queries}"

        logger.info(f"Concurrent DNS queries: {successful_queries}/5 successful")
