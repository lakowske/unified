"""Basic connectivity tests for mail container services."""

import logging

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
