import logging
import re
import subprocess
import time

import pytest

logger = logging.getLogger(__name__)


class TestDKIMFunctionality:
    """Test DKIM signing functionality."""

    def test_dkim_keys_generated(self, mail_config):
        """Test that DKIM keys are generated for the mail domain."""
        domain = mail_config["mail_domain"]

        logger.info(f"Testing DKIM key generation for domain: {domain}")

        # Test with a simple container run to check key generation
        try:
            result = subprocess.run(
                [
                    "podman",
                    "run",
                    "--rm",
                    "-e",
                    f"MAIL_DOMAIN={domain}",
                    "unified/mail:latest",
                    "/usr/local/bin/generate-dkim-keys.sh",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            assert result.returncode == 0, f"DKIM key generation failed: {result.stderr}"
            assert "DKIM key generation completed" in result.stdout, "DKIM key generation not completed"
            assert "DNS RECORD FOR DKIM" in result.stdout, "DNS record not displayed"

            logger.info("DKIM keys generated successfully")

        except subprocess.TimeoutExpired:
            pytest.fail("DKIM key generation timed out")
        except Exception as e:
            pytest.fail(f"DKIM key generation test failed: {str(e)}")

    def test_dkim_configuration_valid(self, mail_config):
        """Test that DKIM configuration is valid."""
        domain = mail_config["mail_domain"]

        logger.info(f"Testing DKIM configuration validation for domain: {domain}")

        try:
            # Test configuration validation
            result = subprocess.run(
                [
                    "podman",
                    "run",
                    "--rm",
                    "-e",
                    f"MAIL_DOMAIN={domain}",
                    "unified/mail:latest",
                    "bash",
                    "-c",
                    """
                /usr/local/bin/generate-dkim-keys.sh > /dev/null 2>&1
                mkdir -p /etc/opendkim
                envsubst < /usr/local/bin/opendkim/opendkim.conf.template > /etc/opendkim/opendkim.conf
                envsubst < /usr/local/bin/opendkim/key.table.template > /etc/opendkim/key.table
                envsubst < /usr/local/bin/opendkim/signing.table.template > /etc/opendkim/signing.table
                envsubst < /usr/local/bin/opendkim/trusted.hosts.template > /etc/opendkim/trusted.hosts
                opendkim -t /etc/opendkim/opendkim.conf
                """,
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            # OpenDKIM -t returns 0 for valid config, non-zero for invalid
            if result.returncode != 0:
                # Check if it's just a warning or actual error
                if "warning" in result.stderr.lower() and "error" not in result.stderr.lower():
                    logger.warning(f"DKIM configuration has warnings: {result.stderr}")
                else:
                    pytest.fail(f"DKIM configuration validation failed: {result.stderr}")
            else:
                logger.info("DKIM configuration is valid")

        except subprocess.TimeoutExpired:
            pytest.fail("DKIM configuration validation timed out")
        except Exception as e:
            pytest.fail(f"DKIM configuration validation test failed: {str(e)}")

    def test_opendkim_service_starts(self, mail_config):
        """Test that OpenDKIM service starts successfully."""
        domain = mail_config["mail_domain"]

        logger.info("Testing OpenDKIM service startup")

        try:
            # Start a container with OpenDKIM and check if it starts
            result = subprocess.run(
                [
                    "podman",
                    "run",
                    "--rm",
                    "-d",
                    "--name",
                    "test-opendkim",
                    "-e",
                    f"MAIL_DOMAIN={domain}",
                    "unified/mail:latest",
                    "bash",
                    "-c",
                    """
                /usr/local/bin/generate-dkim-keys.sh > /dev/null 2>&1
                mkdir -p /etc/opendkim /var/run/opendkim
                envsubst < /usr/local/bin/opendkim/opendkim.conf.template > /etc/opendkim/opendkim.conf
                envsubst < /usr/local/bin/opendkim/key.table.template > /etc/opendkim/key.table
                envsubst < /usr/local/bin/opendkim/signing.table.template > /etc/opendkim/signing.table
                envsubst < /usr/local/bin/opendkim/trusted.hosts.template > /etc/opendkim/trusted.hosts
                chown -R opendkim:opendkim /etc/opendkim /var/run/opendkim
                opendkim -f -x /etc/opendkim/opendkim.conf
                """,
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                container_id = result.stdout.strip()

                # Wait a moment for startup
                time.sleep(2)

                # Check if container is still running
                check_result = subprocess.run(
                    ["podman", "ps", "-f", f"id={container_id}", "--format", "{{.Status}}"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )

                # Stop the container
                subprocess.run(["podman", "stop", container_id], capture_output=True, timeout=10)

                if check_result.returncode == 0 and check_result.stdout.strip():
                    logger.info("OpenDKIM service started successfully")
                else:
                    # Get container logs for debugging
                    logs = subprocess.run(["podman", "logs", container_id], capture_output=True, text=True, timeout=5)

                    pytest.fail(f"OpenDKIM service failed to start. Logs: {logs.stdout} {logs.stderr}")
            else:
                pytest.fail(f"Failed to start OpenDKIM test container: {result.stderr}")

        except subprocess.TimeoutExpired:
            pytest.fail("OpenDKIM service startup test timed out")
        except Exception as e:
            pytest.fail(f"OpenDKIM service startup test failed: {str(e)}")

    def test_dkim_dns_record_format(self, mail_config):
        """Test that DKIM DNS record is in correct format."""
        domain = mail_config["mail_domain"]

        logger.info(f"Testing DKIM DNS record format for domain: {domain}")

        try:
            result = subprocess.run(
                [
                    "podman",
                    "run",
                    "--rm",
                    "-e",
                    f"MAIL_DOMAIN={domain}",
                    "unified/mail:latest",
                    "bash",
                    "-c",
                    """
                /usr/local/bin/generate-dkim-keys.sh > /dev/null 2>&1
                cat /etc/opendkim/keys/*/mail.txt
                """,
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            assert result.returncode == 0, f"Failed to get DKIM DNS record: {result.stderr}"

            dns_record = result.stdout.strip()

            # Check DNS record format
            assert f"mail._domainkey.{domain}" in dns_record, "DNS record should contain selector and domain"
            assert "v=DKIM1" in dns_record, "DNS record should contain DKIM version"
            assert "k=rsa" in dns_record, "DNS record should specify RSA key type"
            assert "p=" in dns_record, "DNS record should contain public key"

            # Check that public key is base64 encoded
            p_match = re.search(r"p=([A-Za-z0-9+/=]+)", dns_record)
            assert p_match, "Public key should be base64 encoded"

            public_key = p_match.group(1)
            assert len(public_key) > 100, "Public key should be substantial length"

            logger.info(f"DKIM DNS record format is valid: {dns_record[:100]}...")

        except subprocess.TimeoutExpired:
            pytest.fail("DKIM DNS record format test timed out")
        except Exception as e:
            pytest.fail(f"DKIM DNS record format test failed: {str(e)}")

    @pytest.mark.integration
    def test_dkim_postfix_integration(self, mail_config):
        """Test that Postfix is configured to use OpenDKIM milter."""
        logger.info("Testing Postfix-OpenDKIM integration")

        try:
            # Check Postfix configuration contains milter settings
            result = subprocess.run(
                [
                    "podman",
                    "run",
                    "--rm",
                    "-e",
                    f'MAIL_DOMAIN={mail_config["mail_domain"]}',
                    "unified/mail:latest",
                    "bash",
                    "-c",
                    """
                envsubst < /usr/local/bin/postfix/main.cf.template > /tmp/main.cf
                grep -E "(milter_protocol|smtpd_milters|non_smtpd_milters)" /tmp/main.cf
                """,
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            assert result.returncode == 0, f"Failed to check Postfix milter configuration: {result.stderr}"

            config_output = result.stdout

            assert "milter_protocol = 6" in config_output, "Postfix should have milter protocol set"
            assert "smtpd_milters = inet:localhost:8891" in config_output, "Postfix should connect to OpenDKIM"
            assert (
                "non_smtpd_milters = inet:localhost:8891" in config_output
            ), "Postfix should use OpenDKIM for non-SMTP"

            logger.info("Postfix-OpenDKIM integration configuration is correct")

        except subprocess.TimeoutExpired:
            pytest.fail("Postfix-OpenDKIM integration test timed out")
        except Exception as e:
            pytest.fail(f"Postfix-OpenDKIM integration test failed: {str(e)}")


class TestDKIMIntegration:
    """Integration tests for DKIM functionality."""

    @pytest.mark.integration
    @pytest.mark.slow
    def test_mail_container_with_dkim(self, mail_config):
        """Test that mail container starts successfully with DKIM enabled."""
        domain = mail_config["mail_domain"]

        logger.info(f"Testing mail container startup with DKIM for domain: {domain}")

        try:
            # Start mail container with DKIM
            result = subprocess.run(
                [
                    "podman",
                    "run",
                    "--rm",
                    "-d",
                    "--name",
                    "test-mail-dkim",
                    "-e",
                    f"MAIL_DOMAIN={domain}",
                    "-e",
                    "DB_HOST=localhost",
                    "-e",
                    "DB_PORT=5432",
                    "-e",
                    "DB_NAME=test",
                    "-e",
                    "DB_USER=test",
                    "-e",
                    "DB_PASSWORD=test",
                    "unified/mail:latest",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                container_id = result.stdout.strip()

                # Wait for startup
                time.sleep(10)

                # Check container status
                status_result = subprocess.run(
                    ["podman", "ps", "-f", f"id={container_id}", "--format", "{{.Status}}"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )

                # Get container logs
                logs_result = subprocess.run(
                    ["podman", "logs", container_id], capture_output=True, text=True, timeout=5
                )

                # Stop the container
                subprocess.run(["podman", "stop", container_id], capture_output=True, timeout=15)

                # Check if container was running
                if status_result.returncode == 0 and status_result.stdout.strip():
                    # Check logs for DKIM configuration
                    logs = logs_result.stdout
                    assert "Configuring OpenDKIM" in logs, "OpenDKIM configuration should be logged"
                    assert "DKIM key generation completed" in logs, "DKIM key generation should complete"

                    logger.info("Mail container with DKIM started successfully")
                else:
                    pytest.fail(f"Mail container failed to start. Logs: {logs_result.stdout} {logs_result.stderr}")
            else:
                pytest.fail(f"Failed to start mail container with DKIM: {result.stderr}")

        except subprocess.TimeoutExpired:
            pytest.fail("Mail container with DKIM startup test timed out")
        except Exception as e:
            pytest.fail(f"Mail container with DKIM startup test failed: {str(e)}")
        finally:
            # Cleanup
            subprocess.run(["podman", "stop", "test-mail-dkim"], capture_output=True, timeout=10)
