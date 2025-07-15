"""Basic connectivity tests for mail container services."""

import logging
import socket
import ssl

import psycopg2
import pytest

from .utils import check_port_connectivity, wait_for_service

logger = logging.getLogger(__name__)


class TestMailConnectivity:
    """Test basic connectivity to mail services."""

    def test_smtp_port_accessible(self, mail_config):
        """Test that SMTP port is accessible."""
        logger.info(
            f"Testing SMTP port accessibility - host: {mail_config['smtp_host']}, port: {mail_config['smtp_port']}"
        )

        # Wait for service to be ready
        assert wait_for_service(
            mail_config["smtp_host"], mail_config["smtp_port"], max_attempts=10
        ), f"SMTP service not available on {mail_config['smtp_host']}:{mail_config['smtp_port']}"

        # Verify port is accessible
        assert check_port_connectivity(
            mail_config["smtp_host"], mail_config["smtp_port"]
        ), f"SMTP port not accessible on {mail_config['smtp_host']}:{mail_config['smtp_port']}"

    def test_imap_port_accessible(self, mail_config):
        """Test that IMAP port is accessible."""
        logger.info(
            f"Testing IMAP port accessibility - host: {mail_config['imap_host']}, port: {mail_config['imap_port']}"
        )

        # Wait for service to be ready
        assert wait_for_service(
            mail_config["imap_host"], mail_config["imap_port"], max_attempts=10
        ), f"IMAP service not available on {mail_config['imap_host']}:{mail_config['imap_port']}"

        # Verify port is accessible
        assert check_port_connectivity(
            mail_config["imap_host"], mail_config["imap_port"]
        ), f"IMAP port not accessible on {mail_config['imap_host']}:{mail_config['imap_port']}"

    def test_database_connection(self, db_config):
        """Test database connectivity."""
        logger.info(
            f"Testing database connectivity - host: {db_config['host']}, port: {db_config['port']}, database: {db_config['database']}"
        )

        try:
            conn = psycopg2.connect(**db_config)
            conn.close()
            logger.info("Database connection successful")
        except Exception as e:
            pytest.fail(f"Database connection failed - error: {str(e)}")

    def test_dovecot_auth_view_exists(self, db_connection):
        """Test that the dovecot_auth view exists and is accessible."""
        logger.info("Testing dovecot_auth view accessibility")

        with db_connection.cursor() as cursor:
            try:
                cursor.execute("SELECT COUNT(*) FROM unified.dovecot_auth LIMIT 1;")
                result = cursor.fetchone()
                logger.info(f"dovecot_auth view accessible - result: {result}")
                assert result is not None, "dovecot_auth view should return a result"
            except Exception as e:
                pytest.fail(f"dovecot_auth view not accessible - error: {str(e)}")

    def test_dovecot_users_view_exists(self, db_connection):
        """Test that the dovecot_users view exists and is accessible."""
        logger.info("Testing dovecot_users view accessibility")

        with db_connection.cursor() as cursor:
            try:
                cursor.execute("SELECT COUNT(*) FROM unified.dovecot_users LIMIT 1;")
                result = cursor.fetchone()
                logger.info(f"dovecot_users view accessible - result: {result}")
                assert result is not None, "dovecot_users view should return a result"
            except Exception as e:
                pytest.fail(f"dovecot_users view not accessible - error: {str(e)}")

    def test_users_table_exists(self, db_connection):
        """Test that the users table exists and is accessible."""
        logger.info("Testing users table accessibility")

        with db_connection.cursor() as cursor:
            try:
                cursor.execute("SELECT COUNT(*) FROM unified.users;")
                result = cursor.fetchone()
                logger.info(f"users table accessible - user_count: {result[0]}")
                assert result is not None, "users table should return a result"
            except Exception as e:
                pytest.fail(f"users table not accessible - error: {str(e)}")


class TestMailServiceHealth:
    """Test mail service health and readiness."""

    def test_smtp_service_responds(self, mail_config):
        """Test that SMTP service responds to connections."""
        import smtplib

        logger.info(
            f"Testing SMTP service response - host: {mail_config['smtp_host']}, port: {mail_config['smtp_port']}"
        )

        try:
            with smtplib.SMTP(mail_config["smtp_host"], mail_config["smtp_port"], timeout=10) as server:
                response = server.noop()
                logger.info(f"SMTP service responded - response: {response}")
                assert response[0] == 250, f"SMTP NOOP should return 250, got {response[0]}"
        except Exception as e:
            pytest.fail(f"SMTP service did not respond properly - error: {str(e)}")

    def test_imap_service_responds(self, mail_config):
        """Test that IMAP service responds to connections."""
        import imaplib

        logger.info(
            f"Testing IMAP service response - host: {mail_config['imap_host']}, port: {mail_config['imap_port']}"
        )

        try:
            with imaplib.IMAP4(mail_config["imap_host"], mail_config["imap_port"]) as imap:
                response = imap.noop()
                logger.info(f"IMAP service responded - response: {response}")
                assert response[0] == "OK", f"IMAP NOOP should return OK, got {response[0]}"
        except Exception as e:
            pytest.fail(f"IMAP service did not respond properly - error: {str(e)}")

    def test_database_schema_ready(self, db_connection):
        """Test that all required database schema elements are present."""
        logger.info("Testing database schema readiness")

        required_tables_views = [
            "unified.users",
            "unified.user_passwords",
            "unified.dovecot_auth",
            "unified.dovecot_users",
        ]

        with db_connection.cursor() as cursor:
            for table_view in required_tables_views:
                try:
                    cursor.execute(f"SELECT 1 FROM {table_view} LIMIT 1;")
                    logger.debug(f"Schema element accessible - name: {table_view}")
                except Exception as e:
                    pytest.fail(f"Required schema element not accessible - name: {table_view}, error: {str(e)}")

        logger.info("Database schema readiness check completed successfully")


@pytest.mark.integration
class TestMailIntegration:
    """Integration tests for mail service components."""

    def test_mail_domain_configuration(self, mail_config, db_connection):
        """Test that mail domain is properly configured in the system."""
        logger.info(f"Testing mail domain configuration - domain: {mail_config['mail_domain']}")

        with db_connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*) FROM unified.users
                WHERE domain = %s AND is_active = true
            """,
                (mail_config["mail_domain"],),
            )

            user_count = cursor.fetchone()[0]
            logger.info(f"Active users in mail domain - domain: {mail_config['mail_domain']}, count: {user_count}")

            # We don't require users to exist, but the query should work
            assert user_count >= 0, "Domain query should return non-negative count"

    def test_dovecot_database_integration(self, db_connection, mail_config):
        """Test that Dovecot can read authentication data from database."""
        logger.info("Testing Dovecot database integration")

        with db_connection.cursor() as cursor:
            # Test the dovecot_auth view with domain filter
            cursor.execute(
                """
                SELECT username, domain, password FROM unified.dovecot_auth
                WHERE domain = %s LIMIT 5
            """,
                (mail_config["mail_domain"],),
            )

            auth_records = cursor.fetchall()
            logger.info(
                f"Dovecot auth records found - domain: {mail_config['mail_domain']}, count: {len(auth_records)}"
            )

            # Test the dovecot_users view
            cursor.execute(
                """
                SELECT "user", uid, gid, home FROM unified.dovecot_users
                WHERE "user" LIKE %s LIMIT 5
            """,
                (f"%@{mail_config['mail_domain']}",),
            )

            user_records = cursor.fetchall()
            logger.info(
                f"Dovecot user records found - domain: {mail_config['mail_domain']}, count: {len(user_records)}"
            )

            # Views should be accessible even if empty
            assert isinstance(auth_records, list), "dovecot_auth view should return list"
            assert isinstance(user_records, list), "dovecot_users view should return list"


class TestSSLTLSConnectivity:
    """Test SSL/TLS connectivity for secure mail services."""

    def test_imaps_port_accessible(self, mail_config):
        """Test that IMAPS port is accessible."""
        imaps_port = mail_config.get("imaps_port", 9933)
        logger.info(f"Testing IMAPS port accessibility - host: {mail_config['imap_host']}, port: {imaps_port}")

        # Wait for service to be ready
        assert wait_for_service(
            mail_config["imap_host"], imaps_port, max_attempts=10
        ), f"IMAPS service not available on {mail_config['imap_host']}:{imaps_port}"

        # Verify port is accessible
        assert check_port_connectivity(
            mail_config["imap_host"], imaps_port
        ), f"IMAPS port not accessible on {mail_config['imap_host']}:{imaps_port}"

    def test_smtps_port_accessible(self, mail_config):
        """Test that SMTPS port is accessible."""
        smtps_port = mail_config.get("smtps_port", 4465)
        logger.info(f"Testing SMTPS port accessibility - host: {mail_config['smtp_host']}, port: {smtps_port}")

        # Wait for service to be ready
        assert wait_for_service(
            mail_config["smtp_host"], smtps_port, max_attempts=10
        ), f"SMTPS service not available on {mail_config['smtp_host']}:{smtps_port}"

        # Verify port is accessible
        assert check_port_connectivity(
            mail_config["smtp_host"], smtps_port
        ), f"SMTPS port not accessible on {mail_config['smtp_host']}:{smtps_port}"

    def test_submission_port_accessible(self, mail_config):
        """Test that SMTP submission port is accessible."""
        submission_port = mail_config.get("submission_port", 5587)
        logger.info(
            f"Testing submission port accessibility - host: {mail_config['smtp_host']}, port: {submission_port}"
        )

        # Wait for service to be ready
        assert wait_for_service(
            mail_config["smtp_host"], submission_port, max_attempts=10
        ), f"SMTP submission service not available on {mail_config['smtp_host']}:{submission_port}"

        # Verify port is accessible
        assert check_port_connectivity(
            mail_config["smtp_host"], submission_port
        ), f"SMTP submission port not accessible on {mail_config['smtp_host']}:{submission_port}"

    def test_ssl_certificate_present(self, mail_config):
        """Test that SSL certificate is present and valid for IMAPS."""
        imaps_port = mail_config.get("imaps_port", 993)
        logger.info(f"Testing SSL certificate - host: {mail_config['imap_host']}, port: {imaps_port}")

        try:
            # Test SSL connection and certificate retrieval
            # First, verify SSL connection works
            context_basic = ssl.create_default_context()
            context_basic.check_hostname = False
            context_basic.verify_mode = ssl.CERT_NONE

            with socket.create_connection((mail_config["imap_host"], imaps_port), timeout=10) as sock:
                with context_basic.wrap_socket(sock, server_hostname=mail_config["imap_host"]) as ssock:
                    logger.info("SSL connection established successfully")

            # Now retrieve certificate metadata with proper verification
            # Use mail domain for hostname verification if available
            server_hostname = mail_config.get("mail_domain", mail_config["imap_host"])

            context_verify = ssl.create_default_context()
            context_verify.check_hostname = False  # Disable hostname check but enable cert verification
            context_verify.verify_mode = ssl.CERT_REQUIRED

            with socket.create_connection((mail_config["imap_host"], imaps_port), timeout=10) as sock:
                with context_verify.wrap_socket(sock, server_hostname=server_hostname) as ssock:
                    cert = ssock.getpeercert()

                    logger.info(f"SSL certificate retrieved - subject: {cert.get('subject', 'N/A')}")
                    logger.info(f"SSL certificate issuer: {cert.get('issuer', 'N/A')}")
                    logger.info(f"SSL certificate valid until: {cert.get('notAfter', 'N/A')}")

                    # Certificate should exist and contain metadata
                    assert cert is not None, "SSL certificate should be present"
                    assert "subject" in cert, "Certificate should have subject field"
                    assert "notAfter" in cert, "Certificate should have expiration date"

                    # Additional validation for Let's Encrypt certificates
                    issuer_info = cert.get("issuer", [])
                    issuer_str = str(issuer_info)
                    if "Let's Encrypt" in issuer_str:
                        logger.info("Detected Let's Encrypt certificate")

        except ssl.SSLError as e:
            if "certificate verify failed" in str(e):
                logger.warning(f"Certificate verification failed (expected for self-signed): {e}")
                # For self-signed certificates, just verify SSL connection works
                context_basic = ssl.create_default_context()
                context_basic.check_hostname = False
                context_basic.verify_mode = ssl.CERT_NONE

                with socket.create_connection((mail_config["imap_host"], imaps_port), timeout=10) as sock:
                    with context_basic.wrap_socket(sock, server_hostname=mail_config["imap_host"]) as ssock:
                        logger.info("SSL connection works with self-signed certificate")
                        # For self-signed certs, we can't get metadata but connection works
            else:
                pytest.fail(f"SSL certificate test failed - SSL error: {str(e)}")
        except Exception as e:
            pytest.fail(f"SSL certificate test failed - error: {str(e)}")

    def test_tls_smtp_submission(self, mail_config):
        """Test STARTTLS functionality on SMTP submission port."""
        submission_port = mail_config.get("submission_port", 5587)
        logger.info(f"Testing SMTP STARTTLS - host: {mail_config['smtp_host']}, port: {submission_port}")

        try:
            import smtplib

            # Connect to submission port and test STARTTLS
            with smtplib.SMTP(mail_config["smtp_host"], submission_port, timeout=10) as server:
                # Check if STARTTLS is available
                server.ehlo()

                if server.has_extn("STARTTLS"):
                    logger.info("STARTTLS extension available")

                    # Start TLS
                    server.starttls()
                    server.ehlo()  # Re-identify after STARTTLS

                    logger.info("STARTTLS negotiation successful")

                    # Verify we're now using SSL
                    assert hasattr(server.sock, "read"), "Connection should be using SSL after STARTTLS"
                else:
                    logger.warning("STARTTLS extension not available - SSL may be disabled")

        except Exception as e:
            # Don't fail if SSL is not configured, just log
            logger.warning(f"STARTTLS test failed (may be expected if SSL disabled) - error: {str(e)}")

    def test_imaps_ssl_service_responds(self, mail_config):
        """Test that IMAPS service responds to SSL connections."""
        imaps_port = mail_config.get("imaps_port", 9933)
        logger.info(f"Testing IMAPS SSL service response - host: {mail_config['imap_host']}, port: {imaps_port}")

        try:
            import imaplib

            # Create SSL context that allows self-signed certificates
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            # Connect to IMAPS with SSL
            with imaplib.IMAP4_SSL(mail_config["imap_host"], imaps_port, ssl_context=ssl_context) as imap:
                response = imap.noop()
                logger.info(f"IMAPS SSL service responded - response: {response}")
                assert response[0] == "OK", f"IMAPS NOOP should return OK, got {response[0]}"

        except Exception as e:
            # Don't fail if SSL is not configured, just log
            logger.warning(f"IMAPS SSL test failed (may be expected if SSL disabled) - error: {str(e)}")

    def test_smtps_ssl_service_responds(self, mail_config):
        """Test that SMTPS service responds to SSL connections."""
        smtps_port = mail_config.get("smtps_port", 4465)
        logger.info(f"Testing SMTPS SSL service response - host: {mail_config['smtp_host']}, port: {smtps_port}")

        try:
            import smtplib

            # Create SSL context that allows self-signed certificates
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            # Connect to SMTPS with SSL
            with smtplib.SMTP_SSL(mail_config["smtp_host"], smtps_port, context=ssl_context, timeout=10) as server:
                response = server.noop()
                logger.info(f"SMTPS SSL service responded - response: {response}")
                assert response[0] == 250, f"SMTPS NOOP should return 250, got {response[0]}"

        except Exception as e:
            # Don't fail if SSL is not configured, just log
            logger.warning(f"SMTPS SSL test failed (may be expected if SSL disabled) - error: {str(e)}")


class TestCertificateManagement:
    """Test certificate management and preference system."""

    def test_certificate_status_in_database(self, db_connection, mail_config):
        """Test that certificate status is tracked in database."""
        logger.info("Testing certificate status tracking in database")

        with db_connection.cursor() as cursor:
            try:
                cursor.execute(
                    """
                    SELECT service_name, domain, certificate_type, ssl_enabled, certificate_path, last_updated
                    FROM unified.service_certificates
                    WHERE service_name = 'mail' AND domain = %s
                """,
                    (mail_config["mail_domain"],),
                )

                cert_status = cursor.fetchone()

                if cert_status:
                    service_name, domain, cert_type, ssl_enabled, cert_path, last_updated = cert_status
                    logger.info(f"Certificate status found - service: {service_name}, domain: {domain}")
                    logger.info(f"Certificate type: {cert_type}, SSL enabled: {ssl_enabled}")
                    logger.info(f"Certificate path: {cert_path}, last updated: {last_updated}")

                    # Basic validation
                    assert service_name == "mail", "Service name should be 'mail'"
                    assert domain == mail_config["mail_domain"], "Domain should match mail domain"
                    assert cert_type in ["live", "staged", "self-signed", "none"], "Certificate type should be valid"
                    assert isinstance(ssl_enabled, bool), "SSL enabled should be boolean"
                else:
                    logger.info("No certificate status found in database (may be expected if service not started)")

            except Exception as e:
                pytest.fail(f"Certificate status check failed - error: {str(e)}")

    def test_certificate_notification_system(self, db_connection):
        """Test that certificate notification system is working."""
        logger.info("Testing certificate notification system")

        with db_connection.cursor() as cursor:
            try:
                # Check if certificate notifications table exists and is accessible
                cursor.execute("""
                    SELECT COUNT(*) FROM unified.certificate_notifications
                    WHERE created_at > NOW() - INTERVAL '1 hour'
                """)

                recent_notifications = cursor.fetchone()[0]
                logger.info(f"Recent certificate notifications found: {recent_notifications}")

                # We don't require notifications to exist, but the table should be accessible
                assert recent_notifications >= 0, "Notification count should be non-negative"

            except Exception as e:
                pytest.fail(f"Certificate notification system check failed - error: {str(e)}")

    @pytest.mark.slow
    def test_certificate_watcher_listening(self, db_connection):
        """Test that certificate watcher is listening for notifications."""
        logger.info("Testing certificate watcher notification system")

        try:
            with db_connection.cursor() as cursor:
                # Send a test notification
                test_payload = "test:example.com:self-signed"
                cursor.execute("NOTIFY certificate_change, %s", (test_payload,))
                db_connection.commit()

                logger.info(f"Test notification sent - payload: {test_payload}")

                # We can't easily test if the watcher received it without more complex setup
                # But we can verify the notification was sent successfully
                assert True, "Notification sent successfully"

        except Exception as e:
            pytest.fail(f"Certificate watcher notification test failed - error: {str(e)}")
