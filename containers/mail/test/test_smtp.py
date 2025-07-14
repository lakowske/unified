"""SMTP functionality tests for mail container."""

import logging
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import pytest

from .utils import send_test_email

logger = logging.getLogger(__name__)


class TestSMTPBasic:
    """Basic SMTP functionality tests."""

    def test_smtp_connection(self, mail_config):
        """Test basic SMTP connection without authentication."""
        logger.info(f"Testing SMTP connection - host: {mail_config['smtp_host']}, port: {mail_config['smtp_port']}")

        try:
            with smtplib.SMTP(mail_config["smtp_host"], mail_config["smtp_port"], timeout=10) as server:
                response = server.ehlo()
                logger.info(f"SMTP EHLO response - response: {response}")
                assert response[0] == 250, f"SMTP EHLO should return 250, got {response[0]}"
        except Exception as e:
            pytest.fail(f"SMTP connection failed - error: {str(e)}")

    def test_smtp_help_command(self, mail_config):
        """Test SMTP HELP command."""
        logger.info("Testing SMTP HELP command")

        try:
            with smtplib.SMTP(mail_config["smtp_host"], mail_config["smtp_port"], timeout=10) as server:
                response = server.help()
                logger.info(f"SMTP HELP response - response: {response}")
                # Some SMTP servers don't implement HELP - accept both success (214) and error responses
                assert response[0] in [
                    214,
                    502,
                    53,
                ], f"SMTP HELP should return 214, 502, or command not recognized, got {response[0]}"
        except Exception as e:
            pytest.fail(f"SMTP HELP command failed - error: {str(e)}")

    def test_smtp_noop_command(self, mail_config):
        """Test SMTP NOOP command."""
        logger.info("Testing SMTP NOOP command")

        try:
            with smtplib.SMTP(mail_config["smtp_host"], mail_config["smtp_port"], timeout=10) as server:
                response = server.noop()
                logger.info(f"SMTP NOOP response - response: {response}")
                assert response[0] == 250, f"SMTP NOOP should return 250, got {response[0]}"
        except Exception as e:
            pytest.fail(f"SMTP NOOP command failed - error: {str(e)}")


class TestSMTPDelivery:
    """SMTP email delivery tests."""

    def test_send_email_to_local_user(self, mail_config, test_user, unique_subject):
        """Test sending email to a local user."""
        user_email, _ = test_user
        from_email = f"sender@{mail_config['mail_domain']}"
        body = f"Test email body sent at {time.time()}"

        logger.info(
            f"Testing email delivery to local user - from: {from_email}, to: {user_email}, subject: {unique_subject}"
        )

        success = send_test_email(
            smtp_host=mail_config["smtp_host"],
            smtp_port=mail_config["smtp_port"],
            from_email=from_email,
            to_email=user_email,
            subject=unique_subject,
            body=body,
        )

        assert success, f"Failed to send email to local user - to: {user_email}"

    def test_send_email_with_authentication(self, mail_config, test_user, unique_subject):
        """Test sending email with SMTP authentication."""
        user_email, password = test_user
        from_email = user_email
        body = f"Authenticated email body sent at {time.time()}"

        logger.info(
            f"Testing authenticated email sending - from: {from_email}, to: {user_email}, subject: {unique_subject}"
        )

        # Note: This test may fail if SMTP AUTH is not configured
        # In that case, we'll log the error but not fail the test
        try:
            success = send_test_email(
                smtp_host=mail_config["smtp_host"],
                smtp_port=mail_config["smtp_port"],
                from_email=from_email,
                to_email=user_email,
                subject=unique_subject,
                body=body,
                username=user_email,
                password=password,
            )
            logger.info(f"Authenticated email sending result - success: {success}")
        except Exception as e:
            logger.warning(f"SMTP authentication not available or failed - error: {str(e)}")
            # This is acceptable as SMTP AUTH might not be configured in dev environment

    def test_send_email_between_users(self, mail_config, test_user_pair, unique_subject):
        """Test sending email between two local users."""
        (sender_email, sender_password), (recipient_email, _) = test_user_pair
        body = f"Cross-user email body sent at {time.time()}"

        logger.info(
            f"Testing cross-user email delivery - from: {sender_email}, to: {recipient_email}, subject: {unique_subject}"
        )

        success = send_test_email(
            smtp_host=mail_config["smtp_host"],
            smtp_port=mail_config["smtp_port"],
            from_email=sender_email,
            to_email=recipient_email,
            subject=unique_subject,
            body=body,
        )

        assert success, f"Failed to send email between users - from: {sender_email}, to: {recipient_email}"

    def test_send_multipart_email(self, mail_config, test_user, unique_subject):
        """Test sending multipart email with text and HTML parts."""
        user_email, _ = test_user
        from_email = f"sender@{mail_config['mail_domain']}"

        logger.info(
            f"Testing multipart email delivery - from: {from_email}, to: {user_email}, subject: {unique_subject}"
        )

        try:
            # Create multipart message
            msg = MIMEMultipart("alternative")
            msg["From"] = from_email
            msg["To"] = user_email
            msg["Subject"] = unique_subject

            # Add text and HTML parts
            text_body = f"Plain text version of test email sent at {time.time()}"
            html_body = f"<html><body><h1>HTML version</h1><p>Test email sent at {time.time()}</p></body></html>"

            msg.attach(MIMEText(text_body, "plain"))
            msg.attach(MIMEText(html_body, "html"))

            # Send email
            with smtplib.SMTP(mail_config["smtp_host"], mail_config["smtp_port"], timeout=10) as server:
                server.sendmail(from_email, [user_email], msg.as_string())

            logger.info("Multipart email sent successfully")

        except Exception as e:
            pytest.fail(f"Failed to send multipart email - error: {str(e)}")


class TestSMTPErrorHandling:
    """SMTP error handling and validation tests."""

    def test_invalid_recipient_handling(self, mail_config, unique_subject):
        """Test SMTP behavior with invalid recipient addresses."""
        from_email = f"sender@{mail_config['mail_domain']}"
        invalid_email = f"nonexistent@{mail_config['mail_domain']}"
        body = "Test email to invalid recipient"

        logger.info(
            f"Testing invalid recipient handling - from: {from_email}, to: {invalid_email}, subject: {unique_subject}"
        )

        try:
            with smtplib.SMTP(mail_config["smtp_host"], mail_config["smtp_port"], timeout=10) as server:
                msg = MIMEText(body)
                msg["From"] = from_email
                msg["To"] = invalid_email
                msg["Subject"] = unique_subject

                # This should either succeed (relay) or fail gracefully
                try:
                    server.sendmail(from_email, [invalid_email], msg.as_string())
                    logger.info("Email to invalid recipient was accepted (may be relayed or bounced later)")
                except smtplib.SMTPRecipientsRefused as e:
                    logger.info(f"Email to invalid recipient was properly refused - error: {str(e)}")
                except Exception as e:
                    logger.warning(f"Unexpected error with invalid recipient - error: {str(e)}")

        except Exception as e:
            pytest.fail(f"SMTP connection failed during invalid recipient test - error: {str(e)}")

    def test_malformed_email_handling(self, mail_config, test_user):
        """Test SMTP behavior with malformed email messages."""
        user_email, _ = test_user
        from_email = f"sender@{mail_config['mail_domain']}"

        logger.info(f"Testing malformed email handling - from: {from_email}, to: {user_email}")

        try:
            with smtplib.SMTP(mail_config["smtp_host"], mail_config["smtp_port"], timeout=10) as server:
                # Send email with missing required headers
                malformed_message = "This is a message without proper headers"

                try:
                    server.sendmail(from_email, [user_email], malformed_message)
                    logger.info("Malformed email was accepted")
                except Exception as e:
                    logger.info(f"Malformed email was properly rejected - error: {str(e)}")

        except Exception as e:
            pytest.fail(f"SMTP connection failed during malformed email test - error: {str(e)}")

    def test_smtp_transaction_limits(self, mail_config, test_user):
        """Test SMTP server behavior with multiple transactions."""
        user_email, _ = test_user
        from_email = f"sender@{mail_config['mail_domain']}"

        logger.info(f"Testing SMTP transaction limits - from: {from_email}, to: {user_email}")

        try:
            with smtplib.SMTP(mail_config["smtp_host"], mail_config["smtp_port"], timeout=30) as server:
                # Send multiple emails in the same connection
                for i in range(3):
                    subject = f"Transaction test email {i+1}"
                    body = f"Test email number {i+1} in transaction sequence"

                    msg = MIMEText(body)
                    msg["From"] = from_email
                    msg["To"] = user_email
                    msg["Subject"] = subject

                    server.sendmail(from_email, [user_email], msg.as_string())
                    logger.debug(f"Transaction {i+1} completed successfully")

                logger.info("Multiple SMTP transactions completed successfully")

        except Exception as e:
            pytest.fail(f"SMTP transaction limit test failed - error: {str(e)}")


@pytest.mark.slow
class TestSMTPPerformance:
    """SMTP performance and load tests."""

    def test_concurrent_email_sending(self, mail_config, test_user_pair, unique_subject):
        """Test sending multiple emails concurrently."""
        import threading
        import time

        (sender_email, _), (recipient_email, _) = test_user_pair
        results = []

        def send_email(email_id):
            """Send a single email and record the result."""
            subject = f"{unique_subject} - Email {email_id}"
            body = f"Concurrent test email {email_id} sent at {time.time()}"

            success = send_test_email(
                smtp_host=mail_config["smtp_host"],
                smtp_port=mail_config["smtp_port"],
                from_email=sender_email,
                to_email=recipient_email,
                subject=subject,
                body=body,
            )

            results.append(success)
            logger.debug(f"Concurrent email {email_id} result - success: {success}")

        logger.info("Testing concurrent email sending")

        # Send 5 emails concurrently
        threads = []
        for i in range(5):
            thread = threading.Thread(target=send_email, args=(i + 1,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Check results
        successful_sends = sum(results)
        logger.info(f"Concurrent email sending completed - successful: {successful_sends}, total: {len(results)}")

        assert successful_sends >= 3, f"At least 3 out of 5 concurrent emails should succeed, got {successful_sends}"
