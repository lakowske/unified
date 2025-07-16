"""DNS and Mail Integration Tests

This module contains comprehensive tests for DNS resolution of mail-related records
including SPF, DKIM, DMARC, MX, and A records. These tests validate that the DNS
server is properly configured and serving the correct records for email authentication.
"""

import logging
import re
import socket
import subprocess
import time
from typing import Dict, List, Tuple

import pytest

logger = logging.getLogger(__name__)


class DNSResolver:
    """Helper class for DNS resolution operations."""

    def __init__(self, dns_server: str = "localhost", dns_port: int = 53):
        self.dns_server = dns_server
        self.dns_port = dns_port

    def query_dns(self, domain: str, record_type: str, timeout: int = 5) -> Tuple[bool, List[str]]:
        """Query DNS server for specific record type.

        Returns:
            Tuple of (success, list_of_records)
        """
        try:
            cmd = ["dig", f"@{self.dns_server}", "-p", str(self.dns_port), domain, record_type, "+short", "+time=1"]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

            if result.returncode == 0:
                records = [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
                return True, records
            logger.error(f"DNS query failed for {domain} {record_type}: {result.stderr}")
            return False, []

        except subprocess.TimeoutExpired:
            logger.error(f"DNS query timeout for {domain} {record_type}")
            return False, []
        except Exception as e:
            logger.error(f"DNS query error for {domain} {record_type}: {e}")
            return False, []

    def verify_dns_server_running(self) -> bool:
        """Verify DNS server is running and responding."""
        try:
            # Test basic connectivity
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(2)
            result = sock.connect_ex((self.dns_server, self.dns_port))
            sock.close()

            if result == 0:
                # Test basic DNS query
                success, records = self.query_dns(".", "NS")
                return success
            return False

        except Exception as e:
            logger.error(f"DNS server connectivity check failed: {e}")
            return False


class SPFValidator:
    """Validates SPF (Sender Policy Framework) records."""

    @staticmethod
    def validate_spf_record(spf_record: str, expected_ip: str) -> Dict[str, bool]:
        """Validate SPF record format and content.

        Returns:
            Dict with validation results
        """
        results = {
            "valid_version": False,
            "has_a_mechanism": False,
            "has_mx_mechanism": False,
            "has_ip4_mechanism": False,
            "has_include_mechanism": False,
            "has_all_mechanism": False,
            "correct_ip": False,
        }

        # Remove quotes if present
        spf_record = spf_record.strip('"')

        # Check version
        if spf_record.startswith("v=spf1"):
            results["valid_version"] = True

        # Check mechanisms
        if " a " in spf_record or spf_record.endswith(" a"):
            results["has_a_mechanism"] = True

        if " mx " in spf_record or spf_record.endswith(" mx"):
            results["has_mx_mechanism"] = True

        if f"ip4:{expected_ip}" in spf_record:
            results["has_ip4_mechanism"] = True
            results["correct_ip"] = True

        if "include:" in spf_record:
            results["has_include_mechanism"] = True

        if spf_record.endswith(" ~all") or spf_record.endswith(" -all"):
            results["has_all_mechanism"] = True

        return results


class DMARCValidator:
    """Validates DMARC (Domain-based Message Authentication) records."""

    @staticmethod
    def validate_dmarc_record(dmarc_record: str, domain: str) -> Dict[str, bool]:
        """Validate DMARC record format and content.

        Returns:
            Dict with validation results
        """
        results = {
            "valid_version": False,
            "has_policy": False,
            "has_rua": False,
            "has_ruf": False,
            "has_subdomain_policy": False,
            "has_alignment_settings": False,
            "valid_rua_email": False,
            "valid_ruf_email": False,
        }

        # Remove quotes if present
        dmarc_record = dmarc_record.strip('"')

        # Check version
        if dmarc_record.startswith("v=DMARC1"):
            results["valid_version"] = True

        # Check policy
        if re.search(r"p=(none|quarantine|reject)", dmarc_record):
            results["has_policy"] = True

        # Check aggregate reports (rua)
        rua_match = re.search(r"rua=mailto:([^;]+)", dmarc_record)
        if rua_match:
            results["has_rua"] = True
            email = rua_match.group(1)
            if domain in email:
                results["valid_rua_email"] = True

        # Check failure reports (ruf)
        ruf_match = re.search(r"ruf=mailto:([^;]+)", dmarc_record)
        if ruf_match:
            results["has_ruf"] = True
            email = ruf_match.group(1)
            if domain in email:
                results["valid_ruf_email"] = True

        # Check subdomain policy
        if "sp=" in dmarc_record:
            results["has_subdomain_policy"] = True

        # Check alignment settings
        if "aspf=" in dmarc_record and "adkim=" in dmarc_record:
            results["has_alignment_settings"] = True

        return results


class DKIMValidator:
    """Validates DKIM (DomainKeys Identified Mail) records."""

    @staticmethod
    def validate_dkim_record(dkim_record: str) -> Dict[str, bool]:
        """Validate DKIM record format and content.

        Returns:
            Dict with validation results
        """
        results = {
            "valid_version": False,
            "has_key_type": False,
            "has_public_key": False,
            "has_hash_algorithm": False,
            "valid_key_length": False,
            "valid_base64": False,
        }

        # Remove quotes if present
        dkim_record = dkim_record.strip('"')

        # Check version
        if "v=DKIM1" in dkim_record:
            results["valid_version"] = True

        # Check key type
        if "k=rsa" in dkim_record:
            results["has_key_type"] = True

        # Check hash algorithm
        if "h=sha256" in dkim_record:
            results["has_hash_algorithm"] = True

        # Check public key
        p_match = re.search(r"p=([A-Za-z0-9+/=]+)", dkim_record)
        if p_match:
            results["has_public_key"] = True
            public_key = p_match.group(1)

            # Check key length (should be substantial for RSA)
            if len(public_key) > 200:
                results["valid_key_length"] = True

            # Check base64 format
            try:
                import base64

                base64.b64decode(public_key)
                results["valid_base64"] = True
            except Exception:
                results["valid_base64"] = False

        return results


@pytest.fixture
def dns_resolver():
    """Create DNS resolver instance."""
    return DNSResolver()


@pytest.fixture
def mail_config():
    """Mail configuration for testing."""
    return {
        "mail_domain": "lab.sethlakowske.com",
        "mail_server_ip": "192.168.0.156",
        "dns_server": "localhost",
        "dns_port": 53,
    }


class TestDNSMailIntegration:
    """Test DNS integration for mail services."""

    def test_dns_server_running(self, dns_resolver):
        """Test that DNS server is running and responding."""
        logger.info("Testing DNS server connectivity")

        assert dns_resolver.verify_dns_server_running(), "DNS server should be running and responding"

        logger.info("DNS server is running and responding")

    def test_mail_domain_a_record(self, dns_resolver, mail_config):
        """Test A record resolution for mail domain."""
        domain = mail_config["mail_domain"]
        expected_ip = mail_config["mail_server_ip"]

        logger.info(f"Testing A record for domain: {domain}")

        success, records = dns_resolver.query_dns(domain, "A")

        assert success, f"DNS query should succeed for {domain} A record"
        assert len(records) > 0, f"Should have at least one A record for {domain}"
        assert expected_ip in records, f"A record should contain expected IP {expected_ip}"

        logger.info(f"A record validated - domain: {domain}, IP: {expected_ip}")

    def test_mail_domain_mx_record(self, dns_resolver, mail_config):
        """Test MX record resolution for mail domain."""
        domain = mail_config["mail_domain"]

        logger.info(f"Testing MX record for domain: {domain}")

        success, records = dns_resolver.query_dns(domain, "MX")

        assert success, f"DNS query should succeed for {domain} MX record"
        assert len(records) > 0, f"Should have at least one MX record for {domain}"

        # Check MX record format (priority hostname)
        mx_record = records[0]
        assert "mail." in mx_record, f"MX record should point to mail subdomain: {mx_record}"

        # Extract priority and hostname
        parts = mx_record.split()
        assert len(parts) >= 2, f"MX record should have priority and hostname: {mx_record}"

        priority = int(parts[0])
        hostname = parts[1].rstrip(".")

        assert priority >= 0, f"MX priority should be non-negative: {priority}"
        assert hostname.endswith(domain), f"MX hostname should be under mail domain: {hostname}"

        logger.info(f"MX record validated - domain: {domain}, priority: {priority}, hostname: {hostname}")

    def test_mail_subdomain_a_record(self, dns_resolver, mail_config):
        """Test A record resolution for mail subdomain."""
        domain = mail_config["mail_domain"]
        mail_subdomain = f"mail.{domain}"
        expected_ip = mail_config["mail_server_ip"]

        logger.info(f"Testing A record for mail subdomain: {mail_subdomain}")

        success, records = dns_resolver.query_dns(mail_subdomain, "A")

        assert success, f"DNS query should succeed for {mail_subdomain} A record"
        assert len(records) > 0, f"Should have at least one A record for {mail_subdomain}"
        assert expected_ip in records, f"A record should contain expected IP {expected_ip}"

        logger.info(f"Mail subdomain A record validated - domain: {mail_subdomain}, IP: {expected_ip}")

    def test_spf_record_resolution(self, dns_resolver, mail_config):
        """Test SPF record DNS resolution and validation."""
        domain = mail_config["mail_domain"]
        expected_ip = mail_config["mail_server_ip"]

        logger.info(f"Testing SPF record for domain: {domain}")

        success, records = dns_resolver.query_dns(domain, "TXT")

        assert success, f"DNS query should succeed for {domain} TXT record"
        assert len(records) > 0, f"Should have at least one TXT record for {domain}"

        # Find SPF record
        spf_record = None
        for record in records:
            if record.startswith('"v=spf1') or record.startswith("v=spf1"):
                spf_record = record
                break

        assert spf_record is not None, f"Should have SPF record in TXT records: {records}"

        # Validate SPF record
        spf_validator = SPFValidator()
        validation_results = spf_validator.validate_spf_record(spf_record, expected_ip)

        assert validation_results["valid_version"], f"SPF record should have valid version: {spf_record}"
        assert validation_results["has_a_mechanism"], f"SPF record should have 'a' mechanism: {spf_record}"
        assert validation_results["has_mx_mechanism"], f"SPF record should have 'mx' mechanism: {spf_record}"
        assert validation_results["has_ip4_mechanism"], f"SPF record should have 'ip4' mechanism: {spf_record}"
        assert validation_results["correct_ip"], f"SPF record should have correct IP {expected_ip}: {spf_record}"
        assert validation_results["has_all_mechanism"], f"SPF record should have 'all' mechanism: {spf_record}"

        logger.info(f"SPF record validated - domain: {domain}, record: {spf_record}")

    def test_dmarc_record_resolution(self, dns_resolver, mail_config):
        """Test DMARC record DNS resolution and validation."""
        domain = mail_config["mail_domain"]
        dmarc_domain = f"_dmarc.{domain}"

        logger.info(f"Testing DMARC record for domain: {dmarc_domain}")

        success, records = dns_resolver.query_dns(dmarc_domain, "TXT")

        assert success, f"DNS query should succeed for {dmarc_domain} TXT record"
        assert len(records) > 0, f"Should have at least one TXT record for {dmarc_domain}"

        # Find DMARC record
        dmarc_record = None
        for record in records:
            if record.startswith('"v=DMARC1') or record.startswith("v=DMARC1"):
                dmarc_record = record
                break

        assert dmarc_record is not None, f"Should have DMARC record in TXT records: {records}"

        # Validate DMARC record
        dmarc_validator = DMARCValidator()
        validation_results = dmarc_validator.validate_dmarc_record(dmarc_record, domain)

        assert validation_results["valid_version"], f"DMARC record should have valid version: {dmarc_record}"
        assert validation_results["has_policy"], f"DMARC record should have policy: {dmarc_record}"
        assert validation_results["has_rua"], f"DMARC record should have RUA (aggregate reports): {dmarc_record}"
        assert validation_results["has_ruf"], f"DMARC record should have RUF (failure reports): {dmarc_record}"
        assert validation_results["valid_rua_email"], f"DMARC RUA should have valid email: {dmarc_record}"
        assert validation_results["valid_ruf_email"], f"DMARC RUF should have valid email: {dmarc_record}"

        logger.info(f"DMARC record validated - domain: {dmarc_domain}, record: {dmarc_record}")

    def test_dkim_record_resolution(self, dns_resolver, mail_config):
        """Test DKIM record DNS resolution and validation."""
        domain = mail_config["mail_domain"]
        dkim_domain = f"mail._domainkey.{domain}"

        logger.info(f"Testing DKIM record for domain: {dkim_domain}")

        success, records = dns_resolver.query_dns(dkim_domain, "TXT")

        # DKIM record might not be populated yet if mail server hasn't started
        if not success or len(records) == 0:
            logger.warning(f"DKIM record not found for {dkim_domain} - may not be populated yet")
            pytest.skip(f"DKIM record not found for {dkim_domain}")

        # Find DKIM record
        dkim_record = None
        for record in records:
            if record.startswith('"v=DKIM1') or record.startswith("v=DKIM1"):
                dkim_record = record
                break

        if dkim_record is None:
            logger.warning(f"DKIM record not properly formatted in TXT records: {records}")
            pytest.skip(f"DKIM record not properly formatted for {dkim_domain}")

        # Validate DKIM record
        dkim_validator = DKIMValidator()
        validation_results = dkim_validator.validate_dkim_record(dkim_record)

        assert validation_results["valid_version"], f"DKIM record should have valid version: {dkim_record}"
        assert validation_results["has_key_type"], f"DKIM record should have key type: {dkim_record}"
        assert validation_results["has_public_key"], f"DKIM record should have public key: {dkim_record}"
        assert validation_results["valid_key_length"], f"DKIM record should have valid key length: {dkim_record}"
        assert validation_results["valid_base64"], f"DKIM record should have valid base64 encoding: {dkim_record}"

        logger.info(f"DKIM record validated - domain: {dkim_domain}, record: {dkim_record[:100]}...")

    def test_mail_authentication_record_consistency(self, dns_resolver, mail_config):
        """Test consistency across all mail authentication records."""
        domain = mail_config["mail_domain"]
        expected_ip = mail_config["mail_server_ip"]

        logger.info(f"Testing mail authentication record consistency for domain: {domain}")

        # Get all records
        a_success, a_records = dns_resolver.query_dns(domain, "A")
        mx_success, mx_records = dns_resolver.query_dns(domain, "MX")
        txt_success, txt_records = dns_resolver.query_dns(domain, "TXT")
        dmarc_success, dmarc_records = dns_resolver.query_dns(f"_dmarc.{domain}", "TXT")

        # Basic success checks
        assert a_success and len(a_records) > 0, "Should have A records"
        assert mx_success and len(mx_records) > 0, "Should have MX records"
        assert txt_success and len(txt_records) > 0, "Should have TXT records"
        assert dmarc_success and len(dmarc_records) > 0, "Should have DMARC records"

        # Check IP consistency
        assert expected_ip in a_records, "A record should contain expected IP"

        # Check MX points to correct subdomain
        mx_record = mx_records[0]
        mx_hostname = mx_record.split()[1].rstrip(".")
        assert mx_hostname == f"mail.{domain}", f"MX should point to mail.{domain}"

        # Check SPF record references correct IP
        spf_record = None
        for record in txt_records:
            if "v=spf1" in record:
                spf_record = record
                break

        assert spf_record is not None, "Should have SPF record"
        assert expected_ip in spf_record, "SPF record should reference expected IP"

        # Check DMARC record references correct domain
        dmarc_record = dmarc_records[0] if dmarc_records else ""
        assert "v=DMARC1" in dmarc_record, "Should have valid DMARC record"
        assert domain in dmarc_record, f"DMARC record should reference domain {domain}"

        logger.info(f"Mail authentication record consistency validated for domain: {domain}")

    def test_dns_performance(self, dns_resolver, mail_config):
        """Test DNS query performance for mail records."""
        domain = mail_config["mail_domain"]
        record_types = ["A", "MX", "TXT"]

        logger.info(f"Testing DNS performance for domain: {domain}")

        performance_results = {}

        for record_type in record_types:
            start_time = time.time()
            success, records = dns_resolver.query_dns(domain, record_type)
            end_time = time.time()

            query_time = end_time - start_time
            performance_results[record_type] = query_time

            assert success, f"DNS query should succeed for {domain} {record_type}"
            assert query_time < 1.0, f"DNS query should complete within 1 second for {record_type}"

            logger.info(f"DNS query performance - {record_type}: {query_time:.3f}s")

        # Check DMARC performance
        start_time = time.time()
        success, records = dns_resolver.query_dns(f"_dmarc.{domain}", "TXT")
        end_time = time.time()

        query_time = end_time - start_time
        performance_results["DMARC"] = query_time

        assert success, f"DNS query should succeed for _dmarc.{domain} TXT"
        assert query_time < 1.0, "DNS query should complete within 1 second for DMARC"

        logger.info(f"DNS query performance - DMARC: {query_time:.3f}s")

        # Overall performance check
        avg_time = sum(performance_results.values()) / len(performance_results)
        assert avg_time < 0.5, f"Average DNS query time should be under 0.5s, got {avg_time:.3f}s"

        logger.info(f"DNS performance test completed - average time: {avg_time:.3f}s")


class TestDNSMailIntegrationAdvanced:
    """Advanced DNS integration tests."""

    def test_mail_subdomain_records(self, dns_resolver, mail_config):
        """Test all mail-related subdomain records."""
        domain = mail_config["mail_domain"]
        expected_ip = mail_config["mail_server_ip"]

        mail_subdomains = ["mail", "imap", "smtp", "webmail", "autodiscover", "autoconfig"]

        logger.info(f"Testing mail subdomain records for domain: {domain}")

        for subdomain in mail_subdomains:
            full_domain = f"{subdomain}.{domain}"

            success, records = dns_resolver.query_dns(full_domain, "A")

            assert success, f"DNS query should succeed for {full_domain} A record"
            assert len(records) > 0, f"Should have A record for {full_domain}"
            assert expected_ip in records, f"A record should contain expected IP for {full_domain}"

            logger.info(f"Mail subdomain validated - {full_domain}: {expected_ip}")

    def test_mail_security_records(self, dns_resolver, mail_config):
        """Test additional mail security records."""
        domain = mail_config["mail_domain"]

        security_records = [("_smtp._tls", "TXT"), ("_mta-sts", "TXT"), ("mta-sts", "A")]

        logger.info(f"Testing mail security records for domain: {domain}")

        for record_name, record_type in security_records:
            full_domain = f"{record_name}.{domain}"

            success, records = dns_resolver.query_dns(full_domain, record_type)

            if success and len(records) > 0:
                logger.info(f"Mail security record found - {full_domain} {record_type}: {records[0]}")

                # Basic validation for TLS policy
                if record_name == "_smtp._tls":
                    assert "v=TLSRPTv1" in records[0], f"TLS policy should be valid: {records[0]}"

                # Basic validation for MTA-STS
                elif record_name == "_mta-sts":
                    assert "v=STSv1" in records[0], f"MTA-STS should be valid: {records[0]}"
            else:
                logger.warning(f"Mail security record not found: {full_domain} {record_type}")

    def test_reverse_dns_consistency(self, dns_resolver, mail_config):
        """Test reverse DNS consistency for mail server IP."""
        expected_ip = mail_config["mail_server_ip"]
        domain = mail_config["mail_domain"]

        logger.info(f"Testing reverse DNS for IP: {expected_ip}")

        # Create reverse DNS query
        ip_parts = expected_ip.split(".")
        reverse_domain = f"{ip_parts[3]}.{ip_parts[2]}.{ip_parts[1]}.{ip_parts[0]}.in-addr.arpa"

        success, records = dns_resolver.query_dns(reverse_domain, "PTR")

        if success and len(records) > 0:
            ptr_record = records[0].rstrip(".")

            # Check if PTR record matches mail domain or subdomain
            assert domain in ptr_record, f"PTR record should reference mail domain: {ptr_record}"

            logger.info(f"Reverse DNS validated - IP: {expected_ip}, PTR: {ptr_record}")
        else:
            logger.warning(f"Reverse DNS not configured for IP: {expected_ip}")
            pytest.skip(f"Reverse DNS not configured for {expected_ip}")


@pytest.mark.integration
class TestDNSMailIntegrationLive:
    """Live integration tests requiring running services."""

    def test_mail_server_dns_integration(self, dns_resolver, mail_config):
        """Test integration between DNS and mail server."""
        domain = mail_config["mail_domain"]

        logger.info(f"Testing DNS-Mail server integration for domain: {domain}")

        # Test that DNS resolves correctly
        success, a_records = dns_resolver.query_dns(domain, "A")
        assert success and len(a_records) > 0, "DNS should resolve A record"

        # Test that mail server IP is reachable
        mail_ip = a_records[0]
        mail_ports = [25, 143, 587, 993, 465]  # SMTP, IMAP, submission, IMAPS, SMTPS

        reachable_ports = []
        for port in mail_ports:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                result = sock.connect_ex((mail_ip, port))
                sock.close()

                if result == 0:
                    reachable_ports.append(port)
            except Exception as e:
                logger.debug(f"Port {port} check failed: {e}")

        assert len(reachable_ports) > 0, f"At least one mail port should be reachable on {mail_ip}"

        logger.info(f"Mail server ports reachable on {mail_ip}: {reachable_ports}")

    def test_dkim_key_dns_propagation(self, dns_resolver, mail_config):
        """Test that DKIM keys are properly propagated to DNS."""
        domain = mail_config["mail_domain"]
        dkim_domain = f"mail._domainkey.{domain}"

        logger.info(f"Testing DKIM key propagation for domain: {dkim_domain}")

        # Check if DKIM record exists
        success, records = dns_resolver.query_dns(dkim_domain, "TXT")

        if not success or len(records) == 0:
            logger.warning("DKIM record not found - may not be propagated yet")
            pytest.skip(f"DKIM record not found for {dkim_domain}")

        dkim_record = records[0]

        # Validate DKIM record format
        assert "v=DKIM1" in dkim_record, "DKIM record should have valid version"
        assert "k=rsa" in dkim_record, "DKIM record should specify RSA key"
        assert "p=" in dkim_record, "DKIM record should have public key"

        # Extract public key
        p_match = re.search(r"p=([A-Za-z0-9+/=]+)", dkim_record)
        assert p_match, "DKIM record should have valid public key format"

        public_key = p_match.group(1)
        assert len(public_key) > 200, "DKIM public key should be substantial length"

        logger.info(f"DKIM key propagation validated - domain: {dkim_domain}")
