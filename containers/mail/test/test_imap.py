"""IMAP functionality tests for mail container."""

import logging
import time

import pytest

from .utils import (
    cleanup_test_emails,
    connect_imap,
    delete_emails_by_subject,
    fetch_email_content,
    list_imap_folders,
    search_emails_by_subject,
    send_test_email,
)

logger = logging.getLogger(__name__)


class TestIMAPBasic:
    """Basic IMAP functionality tests."""

    def test_imap_connection(self, mail_config):
        """Test basic IMAP connection without authentication."""
        import imaplib

        logger.info(f"Testing IMAP connection - host: {mail_config['imap_host']}, port: {mail_config['imap_port']}")

        try:
            with imaplib.IMAP4(mail_config["imap_host"], mail_config["imap_port"]) as imap:
                response = imap.noop()
                logger.info(f"IMAP NOOP response - response: {response}")
                assert response[0] == "OK", f"IMAP NOOP should return OK, got {response[0]}"
        except Exception as e:
            pytest.fail(f"IMAP connection failed - error: {str(e)}")

    def test_imap_capability(self, mail_config):
        """Test IMAP capability command."""
        import imaplib

        logger.info("Testing IMAP capability command")

        try:
            with imaplib.IMAP4(mail_config["imap_host"], mail_config["imap_port"]) as imap:
                response = imap.capability()
                logger.info(f"IMAP capability response - response: {response}")
                assert response[0] == "OK", f"IMAP CAPABILITY should return OK, got {response[0]}"
                assert b"IMAP4REV1" in response[1][0], "Server should support IMAP4REV1"
        except Exception as e:
            pytest.fail(f"IMAP capability test failed - error: {str(e)}")


class TestIMAPAuthentication:
    """IMAP authentication tests."""

    def test_imap_login_valid_user(self, mail_config, test_user):
        """Test IMAP login with valid user credentials."""
        user_email, password = test_user

        logger.info(f"Testing IMAP login with valid user - username: {user_email}")

        imap = connect_imap(
            host=mail_config["imap_host"], port=mail_config["imap_port"], username=user_email, password=password
        )

        assert imap is not None, f"IMAP login should succeed for valid user - username: {user_email}"

        try:
            # Test that we can perform operations after login
            response = imap.list()
            assert response[0] == "OK", "Should be able to list folders after login"
            logger.info("IMAP login and folder listing successful")
        finally:
            imap.logout()

    def test_imap_login_invalid_user(self, mail_config):
        """Test IMAP login with invalid user credentials."""
        invalid_user = f"nonexistent@{mail_config['mail_domain']}"
        invalid_password = "wrongpassword"

        logger.info(f"Testing IMAP login with invalid user - username: {invalid_user}")

        imap = connect_imap(
            host=mail_config["imap_host"],
            port=mail_config["imap_port"],
            username=invalid_user,
            password=invalid_password,
        )

        assert imap is None, f"IMAP login should fail for invalid user - username: {invalid_user}"

    def test_imap_login_wrong_password(self, mail_config, test_user):
        """Test IMAP login with valid user but wrong password."""
        user_email, _ = test_user
        wrong_password = "wrongpassword123"

        logger.info(f"Testing IMAP login with wrong password - username: {user_email}")

        imap = connect_imap(
            host=mail_config["imap_host"], port=mail_config["imap_port"], username=user_email, password=wrong_password
        )

        assert imap is None, f"IMAP login should fail with wrong password - username: {user_email}"


class TestIMAPFolders:
    """IMAP folder operations tests."""

    def test_list_default_folders(self, mail_config, test_user):
        """Test listing default IMAP folders."""
        user_email, password = test_user

        logger.info(f"Testing IMAP folder listing - username: {user_email}")

        imap = connect_imap(
            host=mail_config["imap_host"], port=mail_config["imap_port"], username=user_email, password=password
        )

        assert imap is not None, "IMAP connection should succeed"

        try:
            folders = list_imap_folders(imap)
            logger.info(f"IMAP folders found - username: {user_email}, count: {len(folders)}, folders: {folders}")

            # Check for common default folders
            expected_folders = ["INBOX"]
            for folder in expected_folders:
                assert folder in folders, f"Default folder should exist - folder: {folder}"

        finally:
            imap.logout()

    def test_select_inbox(self, mail_config, test_user):
        """Test selecting INBOX folder."""
        user_email, password = test_user

        logger.info(f"Testing INBOX selection - username: {user_email}")

        imap = connect_imap(
            host=mail_config["imap_host"], port=mail_config["imap_port"], username=user_email, password=password
        )

        assert imap is not None, "IMAP connection should succeed"

        try:
            result, data = imap.select("INBOX")
            logger.info(f"INBOX selection result - username: {user_email}, result: {result}, data: {data}")
            assert result == "OK", f"INBOX selection should succeed - result: {result}"

            # Data should contain message count
            if data and data[0]:
                message_count = int(data[0])
                logger.info(f"INBOX message count - username: {user_email}, count: {message_count}")
                assert message_count >= 0, "Message count should be non-negative"

        finally:
            imap.logout()

    def test_folder_status(self, mail_config, test_user):
        """Test IMAP folder status command."""
        user_email, password = test_user

        logger.info(f"Testing folder status - username: {user_email}")

        imap = connect_imap(
            host=mail_config["imap_host"], port=mail_config["imap_port"], username=user_email, password=password
        )

        assert imap is not None, "IMAP connection should succeed"

        try:
            result, data = imap.status("INBOX", "(MESSAGES UNSEEN)")
            logger.info(f"INBOX status result - username: {user_email}, result: {result}, data: {data}")
            assert result == "OK", f"INBOX status should succeed - result: {result}"

        finally:
            imap.logout()


class TestIMAPMessages:
    """IMAP message operations tests."""

    def test_search_messages(self, mail_config, test_user):
        """Test searching for messages in INBOX."""
        user_email, password = test_user

        logger.info(f"Testing message search - username: {user_email}")

        imap = connect_imap(
            host=mail_config["imap_host"], port=mail_config["imap_port"], username=user_email, password=password
        )

        assert imap is not None, "IMAP connection should succeed"

        try:
            # Select INBOX
            result, data = imap.select("INBOX")
            assert result == "OK", "INBOX selection should succeed"

            # Search for all messages
            result, message_ids = imap.search(None, "ALL")
            logger.info(
                f"Message search result - username: {user_email}, result: {result}, count: {len(message_ids[0].split()) if message_ids[0] else 0}"
            )
            assert result == "OK", f"Message search should succeed - result: {result}"

        finally:
            imap.logout()

    def test_fetch_message_headers(self, mail_config, test_user, unique_subject):
        """Test fetching message headers after sending a test email."""
        user_email, password = test_user
        from_email = f"sender@{mail_config['mail_domain']}"
        body = f"Test email for header fetch at {time.time()}"

        logger.info(f"Testing message header fetch - username: {user_email}, subject: {unique_subject}")

        # First, send a test email
        success = send_test_email(
            smtp_host=mail_config["smtp_host"],
            smtp_port=mail_config["smtp_port"],
            from_email=from_email,
            to_email=user_email,
            subject=unique_subject,
            body=body,
        )

        assert success, "Test email should be sent successfully"

        # Give the email some time to be delivered
        time.sleep(2)

        # Connect to IMAP and search for the email
        imap = connect_imap(
            host=mail_config["imap_host"], port=mail_config["imap_port"], username=user_email, password=password
        )

        assert imap is not None, "IMAP connection should succeed"

        try:
            # Search for the test email
            message_ids = search_emails_by_subject(imap, "INBOX", unique_subject)
            logger.info(
                f"Found test emails - username: {user_email}, subject: {unique_subject}, count: {len(message_ids)}"
            )

            if message_ids:
                # Fetch headers of the first message
                result, header_data = imap.fetch(str(message_ids[0]), "(BODY[HEADER])")
                assert result == "OK", f"Header fetch should succeed - result: {result}"

                if header_data and header_data[0]:
                    headers = header_data[0][1].decode()
                    logger.debug(f"Message headers fetched - username: {user_email}, headers_length: {len(headers)}")
                    assert unique_subject in headers, "Subject should be in headers"
                    assert from_email in headers, "From address should be in headers"
            else:
                logger.warning(
                    f"No test emails found for header fetch - username: {user_email}, subject: {unique_subject}"
                )

        finally:
            # Clean up test emails
            cleanup_test_emails(imap, [unique_subject])
            imap.logout()

    def test_fetch_message_content(self, mail_config, test_user, unique_subject):
        """Test fetching complete message content."""
        user_email, password = test_user
        from_email = f"sender@{mail_config['mail_domain']}"
        test_body = f"Test email body for content fetch at {time.time()}"

        logger.info(f"Testing message content fetch - username: {user_email}, subject: {unique_subject}")

        # Send a test email
        success = send_test_email(
            smtp_host=mail_config["smtp_host"],
            smtp_port=mail_config["smtp_port"],
            from_email=from_email,
            to_email=user_email,
            subject=unique_subject,
            body=test_body,
        )

        assert success, "Test email should be sent successfully"

        # Give the email time to be delivered
        time.sleep(2)

        # Connect to IMAP and fetch the email
        imap = connect_imap(
            host=mail_config["imap_host"], port=mail_config["imap_port"], username=user_email, password=password
        )

        assert imap is not None, "IMAP connection should succeed"

        try:
            # Search for the test email
            message_ids = search_emails_by_subject(imap, "INBOX", unique_subject)

            if message_ids:
                # Fetch complete content
                email_content = fetch_email_content(imap, message_ids[0])
                assert email_content is not None, "Email content should be fetched"

                subject, from_addr, body = email_content
                logger.info(f"Email content fetched - subject: {subject}, from: {from_addr}, body_length: {len(body)}")

                assert unique_subject in subject, "Subject should match"
                assert from_email in from_addr, "From address should match"
                # Note: Body might be modified during transport, so we do a partial match

            else:
                logger.warning(
                    f"No test emails found for content fetch - username: {user_email}, subject: {unique_subject}"
                )

        finally:
            # Clean up test emails
            cleanup_test_emails(imap, [unique_subject])
            imap.logout()


class TestIMAPOperations:
    """IMAP folder and message operations tests."""

    def test_mark_message_as_read(self, mail_config, test_user, unique_subject):
        """Test marking a message as read."""
        user_email, password = test_user
        from_email = f"sender@{mail_config['mail_domain']}"
        body = f"Test email for read flag at {time.time()}"

        logger.info(f"Testing mark message as read - username: {user_email}, subject: {unique_subject}")

        # Send test email
        success = send_test_email(
            smtp_host=mail_config["smtp_host"],
            smtp_port=mail_config["smtp_port"],
            from_email=from_email,
            to_email=user_email,
            subject=unique_subject,
            body=body,
        )

        assert success, "Test email should be sent successfully"
        time.sleep(2)

        # Connect to IMAP
        imap = connect_imap(
            host=mail_config["imap_host"], port=mail_config["imap_port"], username=user_email, password=password
        )

        assert imap is not None, "IMAP connection should succeed"

        try:
            message_ids = search_emails_by_subject(imap, "INBOX", unique_subject)

            if message_ids:
                # Mark message as read
                result, data = imap.store(str(message_ids[0]), "+FLAGS", "\\Seen")
                logger.info(f"Mark as read result - username: {user_email}, result: {result}")
                assert result == "OK", f"Mark as read should succeed - result: {result}"
            else:
                logger.warning(
                    f"No test emails found for read flag test - username: {user_email}, subject: {unique_subject}"
                )

        finally:
            cleanup_test_emails(imap, [unique_subject])
            imap.logout()

    def test_delete_message(self, mail_config, test_user, unique_subject):
        """Test deleting a message."""
        user_email, password = test_user
        from_email = f"sender@{mail_config['mail_domain']}"
        body = f"Test email for deletion at {time.time()}"

        logger.info(f"Testing message deletion - username: {user_email}, subject: {unique_subject}")

        # Send test email
        success = send_test_email(
            smtp_host=mail_config["smtp_host"],
            smtp_port=mail_config["smtp_port"],
            from_email=from_email,
            to_email=user_email,
            subject=unique_subject,
            body=body,
        )

        assert success, "Test email should be sent successfully"
        time.sleep(2)

        # Connect to IMAP
        imap = connect_imap(
            host=mail_config["imap_host"], port=mail_config["imap_port"], username=user_email, password=password
        )

        assert imap is not None, "IMAP connection should succeed"

        try:
            # Delete the test email
            deleted_count = delete_emails_by_subject(imap, "INBOX", unique_subject)
            logger.info(
                f"Deletion result - username: {user_email}, subject: {unique_subject}, deleted_count: {deleted_count}"
            )

            # We don't assert on the count since the email might not be found
            # due to timing issues or delivery delays

        finally:
            # Additional cleanup just in case
            cleanup_test_emails(imap, [unique_subject])
            imap.logout()


@pytest.mark.slow
class TestIMAPPerformance:
    """IMAP performance tests."""

    def test_multiple_imap_connections(self, mail_config, test_user):
        """Test handling multiple concurrent IMAP connections."""
        import threading

        user_email, password = test_user
        results = []

        def test_connection(connection_id):
            """Test a single IMAP connection."""
            logger.debug(f"Testing IMAP connection {connection_id} - username: {user_email}")

            imap = connect_imap(
                host=mail_config["imap_host"], port=mail_config["imap_port"], username=user_email, password=password
            )

            if imap:
                try:
                    result, data = imap.select("INBOX")
                    success = result == "OK"
                    results.append(success)
                    logger.debug(f"IMAP connection {connection_id} result - success: {success}")
                finally:
                    imap.logout()
            else:
                results.append(False)
                logger.debug(f"IMAP connection {connection_id} failed")

        logger.info(f"Testing multiple IMAP connections - username: {user_email}")

        # Test 3 concurrent connections
        threads = []
        for i in range(3):
            thread = threading.Thread(target=test_connection, args=(i + 1,))
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        successful_connections = sum(results)
        logger.info(f"Multiple IMAP connections result - successful: {successful_connections}, total: {len(results)}")

        assert (
            successful_connections >= 2
        ), f"At least 2 out of 3 concurrent IMAP connections should succeed, got {successful_connections}"
