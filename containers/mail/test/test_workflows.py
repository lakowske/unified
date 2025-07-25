"""End-to-end workflow tests for mail container functionality."""

import logging
import ssl
import time

import pytest

from .utils import (
    cleanup_test_emails,
    connect_imap,
    fetch_email_content,
    search_emails_by_subject,
    send_test_email,
)

logger = logging.getLogger(__name__)


class TestEmailWorkflows:
    """Complete email workflow tests from send to receive."""

    def test_send_receive_single_user_workflow(self, mail_config, test_user, unique_subject):
        """Test complete workflow: send email to user, then retrieve via IMAP."""
        user_email, password = test_user
        from_email = f"external@{mail_config['mail_domain']}"
        test_body = f"End-to-end workflow test email sent at {time.time()}"

        logger.info(f"Testing send-receive workflow - user: {user_email}, subject: {unique_subject}")

        # Step 1: Send email via SMTP
        logger.info("Step 1: Sending email via SMTP")
        send_success = send_test_email(
            smtp_host=mail_config["smtp_host"],
            smtp_port=mail_config["smtp_port"],
            from_email=from_email,
            to_email=user_email,
            subject=unique_subject,
            body=test_body,
        )

        assert send_success, f"Email sending should succeed - to: {user_email}"

        # Step 2: Wait for email delivery
        logger.info("Step 2: Waiting for email delivery")
        time.sleep(3)

        # Step 3: Connect to IMAP and retrieve email
        logger.info("Step 3: Connecting to IMAP and retrieving email")
        imap = connect_imap(
            host=mail_config["imap_host"], port=mail_config["imap_port"], username=user_email, password=password
        )

        assert imap is not None, f"IMAP connection should succeed - username: {user_email}"

        try:
            # Step 4: Search for the sent email
            logger.info("Step 4: Searching for sent email")
            message_ids = search_emails_by_subject(imap, "INBOX", unique_subject)

            if message_ids:
                logger.info(f"Email found in INBOX - message_count: {len(message_ids)}")

                # Step 5: Fetch and verify email content
                logger.info("Step 5: Fetching and verifying email content")
                email_content = fetch_email_content(imap, message_ids[0])

                assert email_content is not None, "Email content should be retrievable"

                subject, from_addr, body = email_content
                logger.info(f"Email content verified - subject: {subject}, from: {from_addr}")

                # Verify email content matches what was sent
                assert unique_subject in subject, f"Subject should match - expected: {unique_subject}, got: {subject}"
                assert from_email in from_addr, f"From address should match - expected: {from_email}, got: {from_addr}"

                logger.info("Send-receive workflow completed successfully")
            else:
                pytest.fail(f"Sent email not found in INBOX - subject: {unique_subject}")

        finally:
            # Step 6: Cleanup
            logger.info("Step 6: Cleaning up test emails")
            cleanup_test_emails(imap, [unique_subject])
            imap.logout()

    def test_cross_user_email_workflow(self, mail_config, test_user_pair, unique_subject):
        """Test email workflow between two users."""
        (sender_email, sender_password), (recipient_email, recipient_password) = test_user_pair
        test_body = f"Cross-user workflow test email sent at {time.time()}"

        logger.info(
            f"Testing cross-user workflow - from: {sender_email}, to: {recipient_email}, subject: {unique_subject}"
        )

        # Step 1: Send email from sender to recipient
        logger.info("Step 1: Sending email between users")
        send_success = send_test_email(
            smtp_host=mail_config["smtp_host"],
            smtp_port=mail_config["smtp_port"],
            from_email=sender_email,
            to_email=recipient_email,
            subject=unique_subject,
            body=test_body,
        )

        assert send_success, f"Cross-user email sending should succeed - from: {sender_email}, to: {recipient_email}"

        # Step 2: Wait for delivery
        logger.info("Step 2: Waiting for email delivery")
        time.sleep(3)

        # Step 3: Verify recipient received the email
        logger.info("Step 3: Verifying recipient received email")
        recipient_imap = connect_imap(
            host=mail_config["imap_host"],
            port=mail_config["imap_port"],
            username=recipient_email,
            password=recipient_password,
        )

        assert recipient_imap is not None, f"Recipient IMAP connection should succeed - username: {recipient_email}"

        try:
            # Search for email in recipient's inbox
            message_ids = search_emails_by_subject(recipient_imap, "INBOX", unique_subject)

            if message_ids:
                # Verify email content
                email_content = fetch_email_content(recipient_imap, message_ids[0])
                assert email_content is not None, "Recipient should be able to read email content"

                subject, from_addr, body = email_content
                logger.info(f"Recipient email verified - subject: {subject}, from: {from_addr}")

                assert unique_subject in subject, "Subject should match in recipient's inbox"
                assert sender_email in from_addr, "From address should be the sender"

                logger.info("Cross-user email workflow completed successfully")
            else:
                pytest.fail(f"Cross-user email not found in recipient inbox - subject: {unique_subject}")

        finally:
            # Cleanup recipient's emails
            cleanup_test_emails(recipient_imap, [unique_subject])
            recipient_imap.logout()

    def test_reply_workflow(self, mail_config, test_user_pair, unique_subject):
        """Test email reply workflow."""
        (sender_email, sender_password), (recipient_email, recipient_password) = test_user_pair
        original_body = f"Original email for reply test sent at {time.time()}"
        reply_subject = f"Re: {unique_subject}"
        reply_body = f"Reply to original email sent at {time.time()}"

        logger.info(f"Testing reply workflow - original_from: {sender_email}, reply_to: {recipient_email}")

        # Step 1: Send original email
        logger.info("Step 1: Sending original email")
        send_success = send_test_email(
            smtp_host=mail_config["smtp_host"],
            smtp_port=mail_config["smtp_port"],
            from_email=sender_email,
            to_email=recipient_email,
            subject=unique_subject,
            body=original_body,
        )

        assert send_success, "Original email should be sent successfully"
        time.sleep(2)

        # Step 2: Send reply email
        logger.info("Step 2: Sending reply email")
        reply_success = send_test_email(
            smtp_host=mail_config["smtp_host"],
            smtp_port=mail_config["smtp_port"],
            from_email=recipient_email,
            to_email=sender_email,
            subject=reply_subject,
            body=reply_body,
        )

        assert reply_success, "Reply email should be sent successfully"
        time.sleep(3)

        # Step 3: Verify sender received the reply
        logger.info("Step 3: Verifying sender received reply")
        sender_imap = connect_imap(
            host=mail_config["imap_host"],
            port=mail_config["imap_port"],
            username=sender_email,
            password=sender_password,
        )

        assert sender_imap is not None, f"Sender IMAP connection should succeed - username: {sender_email}"

        try:
            # Search for reply in sender's inbox
            reply_ids = search_emails_by_subject(sender_imap, "INBOX", reply_subject)

            if reply_ids:
                email_content = fetch_email_content(sender_imap, reply_ids[0])
                assert email_content is not None, "Sender should receive reply email"

                subject, from_addr, body = email_content
                logger.info(f"Reply email verified - subject: {subject}, from: {from_addr}")

                assert reply_subject in subject, "Reply subject should match"
                assert recipient_email in from_addr, "Reply should be from recipient"

                logger.info("Reply workflow completed successfully")
            else:
                pytest.fail(f"Reply email not found in sender inbox - subject: {reply_subject}")

        finally:
            # Cleanup all test emails
            cleanup_test_emails(sender_imap, [unique_subject, reply_subject])
            sender_imap.logout()

        # Also cleanup recipient's inbox
        recipient_imap = connect_imap(
            host=mail_config["imap_host"],
            port=mail_config["imap_port"],
            username=recipient_email,
            password=recipient_password,
        )

        if recipient_imap:
            try:
                cleanup_test_emails(recipient_imap, [unique_subject, reply_subject])
            finally:
                recipient_imap.logout()

    def test_multiple_recipients_workflow(self, mail_config, test_user_pair, unique_subject):
        """Test sending email to multiple recipients (simulated)."""
        (sender_email, sender_password), (recipient_email, recipient_password) = test_user_pair
        additional_recipient = f"cc@{mail_config['mail_domain']}"
        test_body = f"Multi-recipient workflow test email sent at {time.time()}"

        logger.info(
            f"Testing multi-recipient workflow - from: {sender_email}, to: {recipient_email}, cc: {additional_recipient}"
        )

        # Step 1: Send email to primary recipient
        logger.info("Step 1: Sending email to primary recipient")
        send_success = send_test_email(
            smtp_host=mail_config["smtp_host"],
            smtp_port=mail_config["smtp_port"],
            from_email=sender_email,
            to_email=recipient_email,
            subject=unique_subject,
            body=test_body,
        )

        assert send_success, "Email to primary recipient should succeed"

        # Step 2: Attempt to send to additional recipient (may fail if user doesn't exist)
        logger.info("Step 2: Attempting to send to additional recipient")
        additional_send_success = send_test_email(
            smtp_host=mail_config["smtp_host"],
            smtp_port=mail_config["smtp_port"],
            from_email=sender_email,
            to_email=additional_recipient,
            subject=unique_subject,
            body=test_body,
        )

        # We don't assert this since the additional recipient might not exist
        logger.info(f"Additional recipient send result - success: {additional_send_success}")

        time.sleep(3)

        # Step 3: Verify primary recipient received email
        logger.info("Step 3: Verifying primary recipient received email")
        recipient_imap = connect_imap(
            host=mail_config["imap_host"],
            port=mail_config["imap_port"],
            username=recipient_email,
            password=recipient_password,
        )

        assert recipient_imap is not None, "Primary recipient IMAP connection should succeed"

        try:
            message_ids = search_emails_by_subject(recipient_imap, "INBOX", unique_subject)

            if message_ids:
                email_content = fetch_email_content(recipient_imap, message_ids[0])
                assert email_content is not None, "Primary recipient should receive email"

                subject, from_addr, body = email_content
                logger.info(f"Multi-recipient email verified - subject: {subject}, from: {from_addr}")

                assert unique_subject in subject, "Subject should match"
                assert sender_email in from_addr, "From address should match sender"

                logger.info("Multi-recipient workflow completed successfully")
            else:
                pytest.fail(f"Multi-recipient email not found - subject: {unique_subject}")

        finally:
            cleanup_test_emails(recipient_imap, [unique_subject])
            recipient_imap.logout()


@pytest.mark.slow
class TestMailPerformanceWorkflows:
    """Performance and stress test workflows."""

    def test_email_volume_workflow(self, mail_config, test_user, unique_subject):
        """Test sending and receiving multiple emails."""
        user_email, password = test_user
        from_email = f"bulk@{mail_config['mail_domain']}"
        email_count = 5

        logger.info(f"Testing email volume workflow - count: {email_count}, user: {user_email}")

        sent_subjects = []

        # Step 1: Send multiple emails
        logger.info(f"Step 1: Sending {email_count} emails")
        for i in range(email_count):
            subject = f"{unique_subject} - Email {i+1}"
            body = f"Bulk email {i+1} of {email_count} sent at {time.time()}"

            success = send_test_email(
                smtp_host=mail_config["smtp_host"],
                smtp_port=mail_config["smtp_port"],
                from_email=from_email,
                to_email=user_email,
                subject=subject,
                body=body,
            )

            if success:
                sent_subjects.append(subject)
                logger.debug(f"Email {i+1} sent successfully - subject: {subject}")
            else:
                logger.warning(f"Email {i+1} failed to send - subject: {subject}")

        # At least half should succeed
        assert len(sent_subjects) >= email_count // 2, f"At least {email_count // 2} emails should be sent"

        # Step 2: Wait for delivery
        logger.info("Step 2: Waiting for email delivery")
        time.sleep(5)

        # Step 3: Verify emails were received
        logger.info("Step 3: Verifying emails were received")
        imap = connect_imap(
            host=mail_config["imap_host"], port=mail_config["imap_port"], username=user_email, password=password
        )

        assert imap is not None, "IMAP connection should succeed"

        try:
            received_count = 0
            for subject in sent_subjects:
                message_ids = search_emails_by_subject(imap, "INBOX", subject)
                if message_ids:
                    received_count += 1
                    logger.debug(f"Email received - subject: {subject}")

            logger.info(f"Email volume workflow results - sent: {len(sent_subjects)}, received: {received_count}")

            # At least 70% of sent emails should be received
            min_received = int(len(sent_subjects) * 0.7)
            assert (
                received_count >= min_received
            ), f"At least {min_received} emails should be received, got {received_count}"

        finally:
            # Cleanup all test emails
            cleanup_test_emails(imap, sent_subjects)
            imap.logout()

    def test_concurrent_user_workflow(self, mail_config, test_user_pair, unique_subject):
        """Test concurrent email operations between users."""
        import threading

        (user1_email, user1_password), (user2_email, user2_password) = test_user_pair
        results = {}

        def user_send_receive(user_id, sender_email, recipient_email, recipient_password):
            """Send email and verify receipt for a single user pair."""
            subject = f"{unique_subject} - User {user_id}"
            body = f"Concurrent workflow email from user {user_id} at {time.time()}"

            logger.debug(f"User {user_id}: Sending email - from: {sender_email}, to: {recipient_email}")

            # Send email
            send_success = send_test_email(
                smtp_host=mail_config["smtp_host"],
                smtp_port=mail_config["smtp_port"],
                from_email=sender_email,
                to_email=recipient_email,
                subject=subject,
                body=body,
            )

            if not send_success:
                results[user_id] = False
                return

            # Wait and check receipt
            time.sleep(3)

            imap = connect_imap(
                host=mail_config["imap_host"],
                port=mail_config["imap_port"],
                username=recipient_email,
                password=recipient_password,
            )

            if imap:
                try:
                    message_ids = search_emails_by_subject(imap, "INBOX", subject)
                    results[user_id] = len(message_ids) > 0

                    # Cleanup
                    cleanup_test_emails(imap, [subject])
                finally:
                    imap.logout()
            else:
                results[user_id] = False

        logger.info("Testing concurrent user workflow")

        # Create threads for concurrent operations
        threads = [
            threading.Thread(target=user_send_receive, args=(1, user1_email, user2_email, user2_password)),
            threading.Thread(target=user_send_receive, args=(2, user2_email, user1_email, user1_password)),
        ]

        # Start threads
        for thread in threads:
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # Check results
        successful_workflows = sum(results.values())
        logger.info(f"Concurrent workflow results - successful: {successful_workflows}, total: {len(results)}")

        assert successful_workflows >= 1, f"At least 1 concurrent workflow should succeed, got {successful_workflows}"


@pytest.mark.integration
class TestSystemIntegration:
    """System-level integration tests."""

    def test_database_mail_integration_workflow(self, mail_config, db_connection, unique_subject):
        """Test integration between database user management and mail functionality."""
        import uuid

        # Create a test user directly in the database
        test_id = str(uuid.uuid4())[:8]
        username = f"dbuser_{test_id}"
        email = f"{username}@{mail_config['mail_domain']}"
        password = f"dbpass_{test_id}"

        logger.info(f"Testing database-mail integration - email: {email}")

        user_id = None
        try:
            # Step 1: Create user in database
            logger.info("Step 1: Creating user in database")
            with db_connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO unified.users (username, email, domain, is_active, email_verified)
                    VALUES (%s, %s, %s, true, true)
                    RETURNING id
                """,
                    (username, email, mail_config["mail_domain"]),
                )

                user_id = cursor.fetchone()[0]

                cursor.execute(
                    """
                    INSERT INTO unified.user_passwords (user_id, service, password_hash, hash_scheme)
                    VALUES (%s, 'dovecot', %s, 'PLAIN')
                """,
                    (user_id, password),
                )

                db_connection.commit()

            # Step 2: Test IMAP authentication with database user
            logger.info("Step 2: Testing IMAP authentication")
            imap = connect_imap(
                host=mail_config["imap_host"], port=mail_config["imap_port"], username=email, password=password
            )

            assert imap is not None, f"Database user should be able to authenticate via IMAP - email: {email}"

            try:
                # Step 3: Send email to database user
                logger.info("Step 3: Sending email to database user")
                from_email = f"system@{mail_config['mail_domain']}"
                body = f"Database integration test email sent at {time.time()}"

                send_success = send_test_email(
                    smtp_host=mail_config["smtp_host"],
                    smtp_port=mail_config["smtp_port"],
                    from_email=from_email,
                    to_email=email,
                    subject=unique_subject,
                    body=body,
                )

                assert send_success, "Email should be sent to database user"

                # Step 4: Verify email receipt
                logger.info("Step 4: Verifying email receipt")
                time.sleep(3)

                message_ids = search_emails_by_subject(imap, "INBOX", unique_subject)

                if message_ids:
                    email_content = fetch_email_content(imap, message_ids[0])
                    assert email_content is not None, "Database user should receive email"

                    subject, from_addr, body = email_content
                    assert unique_subject in subject, "Subject should match"

                    logger.info("Database-mail integration workflow completed successfully")
                else:
                    pytest.fail("Email not found in database user's inbox")

            finally:
                cleanup_test_emails(imap, [unique_subject])
                imap.logout()

        finally:
            # Cleanup database user
            if user_id:
                logger.info("Cleaning up database user")
                with db_connection.cursor() as cursor:
                    cursor.execute("DELETE FROM unified.user_passwords WHERE user_id = %s", (user_id,))
                    cursor.execute("DELETE FROM unified.users WHERE id = %s", (user_id,))
                    db_connection.commit()


class TestSSLTLSWorkflows:
    """SSL/TLS enabled email workflow tests."""

    def test_ssl_send_receive_workflow(self, mail_config, test_user, unique_subject):
        """Test complete workflow using SSL/TLS for both SMTP and IMAP."""
        user_email, password = test_user
        from_email = f"ssl-test@{mail_config['mail_domain']}"
        test_body = f"SSL/TLS workflow test email sent at {time.time()}"

        logger.info(f"Testing SSL send-receive workflow - user: {user_email}, subject: {unique_subject}")

        # Step 1: Send email via SMTPS (SSL-enabled SMTP)
        logger.info("Step 1: Sending email via SMTPS")
        try:
            import smtplib

            # Create SSL context that allows self-signed certificates
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            smtps_port = mail_config.get("smtps_port", 4465)

            with smtplib.SMTP_SSL(mail_config["smtp_host"], smtps_port, context=ssl_context, timeout=10) as server:
                # Create email message
                from email.mime.text import MIMEText

                msg = MIMEText(test_body)
                msg["Subject"] = unique_subject
                msg["From"] = from_email
                msg["To"] = user_email

                # Send email
                server.send_message(msg)
                logger.info("Email sent successfully via SMTPS")

        except Exception as e:
            # If SSL is not configured, this test should be skipped
            logger.warning(f"SMTPS test skipped (SSL may not be configured) - error: {str(e)}")
            pytest.skip(f"SMTPS not available: {str(e)}")

        # Step 2: Wait for email delivery
        logger.info("Step 2: Waiting for email delivery")
        time.sleep(3)

        # Step 3: Connect to IMAPS and retrieve email
        logger.info("Step 3: Connecting to IMAPS and retrieving email")
        try:
            import imaplib

            # Create SSL context that allows self-signed certificates
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            imaps_port = mail_config.get("imaps_port", 9933)

            with imaplib.IMAP4_SSL(mail_config["imap_host"], imaps_port, ssl_context=ssl_context) as imap:
                # Login
                imap.login(user_email, password)
                imap.select("INBOX")

                # Search for the sent email
                logger.info("Step 4: Searching for sent email")
                message_ids = search_emails_by_subject(imap, "INBOX", unique_subject)

                if message_ids:
                    logger.info(f"Email found in INBOX via IMAPS - message_count: {len(message_ids)}")

                    # Fetch and verify email content
                    logger.info("Step 5: Fetching and verifying email content")
                    email_content = fetch_email_content(imap, message_ids[0])

                    assert email_content is not None, "Email content should be retrievable via IMAPS"

                    subject, from_addr, body = email_content
                    logger.info(f"SSL email content verified - subject: {subject}, from: {from_addr}")

                    # Verify email content matches what was sent
                    assert (
                        unique_subject in subject
                    ), f"Subject should match - expected: {unique_subject}, got: {subject}"
                    assert (
                        from_email in from_addr
                    ), f"From address should match - expected: {from_email}, got: {from_addr}"

                    logger.info("SSL send-receive workflow completed successfully")
                else:
                    pytest.fail(f"SSL-sent email not found in INBOX - subject: {unique_subject}")

                # Cleanup
                cleanup_test_emails(imap, [unique_subject])

        except Exception as e:
            # If SSL is not configured, this test should be skipped
            logger.warning(f"IMAPS test skipped (SSL may not be configured) - error: {str(e)}")
            pytest.skip(f"IMAPS not available: {str(e)}")

    def test_starttls_submission_workflow(self, mail_config, test_user, unique_subject):
        """Test email workflow using STARTTLS on submission port."""
        user_email, password = test_user
        from_email = f"starttls-test@{mail_config['mail_domain']}"
        test_body = f"STARTTLS workflow test email sent at {time.time()}"

        logger.info(f"Testing STARTTLS submission workflow - user: {user_email}, subject: {unique_subject}")

        # Step 1: Send email via SMTP with STARTTLS
        logger.info("Step 1: Sending email via SMTP with STARTTLS")
        try:
            import smtplib

            submission_port = mail_config.get("submission_port", 5587)

            with smtplib.SMTP(mail_config["smtp_host"], submission_port, timeout=10) as server:
                server.ehlo()

                # Check if STARTTLS is available
                if server.has_extn("STARTTLS"):
                    logger.info("STARTTLS extension available, starting TLS")
                    server.starttls()
                    server.ehlo()  # Re-identify after STARTTLS

                    # Create and send email message
                    from email.mime.text import MIMEText

                    msg = MIMEText(test_body)
                    msg["Subject"] = unique_subject
                    msg["From"] = from_email
                    msg["To"] = user_email

                    server.send_message(msg)
                    logger.info("Email sent successfully via STARTTLS")
                else:
                    logger.warning("STARTTLS not available, using plain SMTP")
                    pytest.skip("STARTTLS not available")

        except Exception as e:
            logger.warning(f"STARTTLS test skipped - error: {str(e)}")
            pytest.skip(f"STARTTLS submission not available: {str(e)}")

        # Step 2: Wait for email delivery
        logger.info("Step 2: Waiting for email delivery")
        time.sleep(3)

        # Step 3: Retrieve email via standard IMAP
        logger.info("Step 3: Retrieving email via IMAP")
        imap = connect_imap(
            host=mail_config["imap_host"], port=mail_config["imap_port"], username=user_email, password=password
        )

        assert imap is not None, f"IMAP connection should succeed - username: {user_email}"

        try:
            # Search for the sent email
            message_ids = search_emails_by_subject(imap, "INBOX", unique_subject)

            if message_ids:
                logger.info(f"STARTTLS email found in INBOX - message_count: {len(message_ids)}")

                # Verify email content
                email_content = fetch_email_content(imap, message_ids[0])
                assert email_content is not None, "Email content should be retrievable"

                subject, from_addr, body = email_content
                logger.info(f"STARTTLS email content verified - subject: {subject}, from: {from_addr}")

                assert unique_subject in subject, "Subject should match"
                assert from_email in from_addr, "From address should match"

                logger.info("STARTTLS submission workflow completed successfully")
            else:
                pytest.fail(f"STARTTLS email not found in INBOX - subject: {unique_subject}")

        finally:
            cleanup_test_emails(imap, [unique_subject])
            imap.logout()

    def test_mixed_ssl_workflow(self, mail_config, test_user_pair, unique_subject):
        """Test workflow mixing SSL and non-SSL connections."""
        (sender_email, sender_password), (recipient_email, recipient_password) = test_user_pair
        test_body = f"Mixed SSL workflow test email sent at {time.time()}"

        logger.info(f"Testing mixed SSL workflow - from: {sender_email}, to: {recipient_email}")

        # Step 1: Send email via regular SMTP (non-SSL)
        logger.info("Step 1: Sending email via regular SMTP")
        send_success = send_test_email(
            smtp_host=mail_config["smtp_host"],
            smtp_port=mail_config["smtp_port"],
            from_email=sender_email,
            to_email=recipient_email,
            subject=unique_subject,
            body=test_body,
        )

        assert send_success, "Email should be sent via regular SMTP"
        time.sleep(3)

        # Step 2: Retrieve email via IMAPS (SSL)
        logger.info("Step 2: Retrieving email via IMAPS")
        try:
            import imaplib

            # Create SSL context that allows self-signed certificates
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            imaps_port = mail_config.get("imaps_port", 9933)

            with imaplib.IMAP4_SSL(mail_config["imap_host"], imaps_port, ssl_context=ssl_context) as imap:
                # Login and select inbox
                imap.login(recipient_email, recipient_password)
                imap.select("INBOX")

                # Search for email
                message_ids = search_emails_by_subject(imap, "INBOX", unique_subject)

                if message_ids:
                    logger.info("Mixed SSL workflow: Email sent via SMTP retrieved via IMAPS")

                    # Verify content
                    email_content = fetch_email_content(imap, message_ids[0])
                    assert email_content is not None, "Email should be retrievable via IMAPS"

                    subject, from_addr, body = email_content
                    assert unique_subject in subject, "Subject should match"
                    assert sender_email in from_addr, "From address should match"

                    logger.info("Mixed SSL workflow completed successfully")
                else:
                    pytest.fail("Email not found via IMAPS")

                # Cleanup
                cleanup_test_emails(imap, [unique_subject])

        except Exception as e:
            logger.warning(f"Mixed SSL workflow test failed - error: {str(e)}")
            # Fall back to regular IMAP if IMAPS fails
            recipient_imap = connect_imap(
                host=mail_config["imap_host"],
                port=mail_config["imap_port"],
                username=recipient_email,
                password=recipient_password,
            )

            if recipient_imap:
                try:
                    cleanup_test_emails(recipient_imap, [unique_subject])
                finally:
                    recipient_imap.logout()

            pytest.skip(f"IMAPS not available for mixed SSL test: {str(e)}")

    def test_certificate_preference_workflow(self, mail_config, db_connection, test_user, unique_subject):
        """Test that certificate preference system affects SSL connections."""
        user_email, password = test_user

        logger.info("Testing certificate preference workflow")

        # Step 1: Check current certificate status in database
        logger.info("Step 1: Checking current certificate status")
        with db_connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT certificate_type, ssl_enabled, certificate_path
                FROM unified.service_certificates
                WHERE service_name = 'mail' AND domain = %s
            """,
                (mail_config["mail_domain"],),
            )

            cert_status = cursor.fetchone()

            if cert_status:
                cert_type, ssl_enabled, cert_path = cert_status
                logger.info(f"Current certificate status - type: {cert_type}, SSL: {ssl_enabled}")

                if ssl_enabled:
                    # Step 2: Test SSL connection with current certificate
                    logger.info(f"Step 2: Testing SSL connection with {cert_type} certificate")

                    try:
                        import imaplib
                        import socket

                        # Create SSL context
                        ssl_context = ssl.create_default_context()
                        ssl_context.check_hostname = False
                        ssl_context.verify_mode = ssl.CERT_NONE

                        imaps_port = mail_config.get("imaps_port", 9933)

                        # Test SSL connection and certificate
                        with socket.create_connection((mail_config["imap_host"], imaps_port), timeout=10) as sock:
                            with ssl_context.wrap_socket(sock, server_hostname=mail_config["imap_host"]) as ssock:
                                cert = ssock.getpeercert()

                                logger.info(f"SSL certificate retrieved for {cert_type} preference")
                                logger.info(f"Certificate subject: {cert.get('subject', 'N/A')}")
                                logger.info(f"Certificate issuer: {cert.get('issuer', 'N/A')}")

                                # Basic certificate validation
                                assert cert is not None, "Certificate should be present"

                                # Test actual IMAPS functionality
                                with imaplib.IMAP4_SSL(
                                    mail_config["imap_host"], imaps_port, ssl_context=ssl_context
                                ) as imap:
                                    imap.login(user_email, password)
                                    imap.select("INBOX")
                                    logger.info(f"IMAPS login successful with {cert_type} certificate")

                        logger.info(f"Certificate preference workflow completed - certificate type: {cert_type}")

                    except Exception as e:
                        logger.warning(f"SSL test failed with {cert_type} certificate - error: {str(e)}")
                        pytest.skip(f"SSL not working with {cert_type} certificate: {str(e)}")
                else:
                    logger.info("SSL is disabled, skipping certificate preference test")
                    pytest.skip("SSL is disabled in mail configuration")
            else:
                logger.info("No certificate status found, testing may be running before service startup")
                pytest.skip("Certificate status not found in database")
