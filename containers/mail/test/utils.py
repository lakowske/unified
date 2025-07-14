"""Utility functions for mail container testing."""

import email
import imaplib
import logging
import smtplib
import socket
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


def check_port_connectivity(host: str, port: int, timeout: int = 5) -> bool:
    """Check if a port is accessible on the given host."""
    logger.debug(f"Checking port connectivity - host: {host}, port: {port}, timeout: {timeout}")
    try:
        with socket.create_connection((host, port), timeout=timeout):
            logger.debug(f"Port connectivity successful - host: {host}, port: {port}")
            return True
    except (OSError, socket.timeout) as e:
        logger.warning(f"Port connectivity failed - host: {host}, port: {port}, error: {str(e)}")
        return False


def wait_for_service(host: str, port: int, max_attempts: int = 30, delay: int = 1) -> bool:
    """Wait for a service to become available with retry logic."""
    logger.info(f"Waiting for service - host: {host}, port: {port}, max_attempts: {max_attempts}")

    for attempt in range(1, max_attempts + 1):
        if check_port_connectivity(host, port):
            logger.info(f"Service available after {attempt} attempts - host: {host}, port: {port}")
            return True

        if attempt < max_attempts:
            logger.debug(f"Service not ready, attempt {attempt}/{max_attempts}, waiting {delay}s...")
            time.sleep(delay)

    logger.error(f"Service not available after {max_attempts} attempts - host: {host}, port: {port}")
    return False


def send_test_email(
    smtp_host: str,
    smtp_port: int,
    from_email: str,
    to_email: str,
    subject: str,
    body: str,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> bool:
    """Send a test email via SMTP."""
    logger.info(f"Sending test email - from: {from_email}, to: {to_email}, subject: {subject}")

    try:
        # Create message
        msg = MIMEMultipart()
        msg["From"] = from_email
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        # Connect to SMTP server
        logger.debug(f"Connecting to SMTP server - host: {smtp_host}, port: {smtp_port}")
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.set_debuglevel(0)  # Set to 1 for detailed SMTP debugging

            # Authenticate if credentials provided
            if username and password:
                logger.debug(f"Authenticating SMTP - username: {username}")
                server.login(username, password)

            # Send email
            text = msg.as_string()
            server.sendmail(from_email, [to_email], text)
            logger.info(f"Email sent successfully - from: {from_email}, to: {to_email}")
            return True

    except Exception as e:
        logger.error(f"Failed to send email - from: {from_email}, to: {to_email}, error: {str(e)}")
        return False


def connect_imap(host: str, port: int, username: str, password: str) -> Optional[imaplib.IMAP4]:
    """Connect to IMAP server and authenticate."""
    logger.debug(f"Connecting to IMAP server - host: {host}, port: {port}, username: {username}")

    try:
        imap = imaplib.IMAP4(host, port)
        result, data = imap.login(username, password)

        if result == "OK":
            logger.info(f"IMAP login successful - username: {username}")
            return imap
        logger.error(f"IMAP login failed - username: {username}, result: {result}, data: {data}")
        return None

    except Exception as e:
        logger.error(f"IMAP connection failed - host: {host}, port: {port}, username: {username}, error: {str(e)}")
        return None


def list_imap_folders(imap: imaplib.IMAP4) -> List[str]:
    """List all folders in IMAP mailbox."""
    logger.debug("Listing IMAP folders")

    try:
        result, folders = imap.list()
        if result == "OK":
            folder_names = []
            for folder in folders:
                if folder:
                    # Parse folder name from IMAP LIST response
                    parts = folder.decode().split('"')
                    if len(parts) >= 3:
                        folder_name = parts[-2]
                        folder_names.append(folder_name)

            logger.debug(f"IMAP folders found - count: {len(folder_names)}, folders: {folder_names}")
            return folder_names
        logger.error(f"Failed to list IMAP folders - result: {result}")
        return []

    except Exception as e:
        logger.error(f"Error listing IMAP folders - error: {str(e)}")
        return []


def search_emails_by_subject(imap: imaplib.IMAP4, folder: str, subject: str) -> List[int]:
    """Search for emails by subject in the specified folder."""
    logger.debug(f"Searching emails by subject - folder: {folder}, subject: {subject}")

    try:
        # Select folder
        result, data = imap.select(folder)
        if result != "OK":
            logger.error(f"Failed to select IMAP folder - folder: {folder}, result: {result}")
            return []

        # Search for emails with the subject
        search_criteria = f'SUBJECT "{subject}"'
        result, message_ids = imap.search(None, search_criteria)

        if result == "OK":
            if message_ids[0]:
                ids = [int(id_) for id_ in message_ids[0].split()]
                logger.debug(f"Found emails by subject - folder: {folder}, subject: {subject}, count: {len(ids)}")
                return ids
            logger.debug(f"No emails found by subject - folder: {folder}, subject: {subject}")
            return []
        logger.error(f"Failed to search emails - folder: {folder}, subject: {subject}, result: {result}")
        return []

    except Exception as e:
        logger.error(f"Error searching emails by subject - folder: {folder}, subject: {subject}, error: {str(e)}")
        return []


def fetch_email_content(imap: imaplib.IMAP4, message_id: int) -> Optional[Tuple[str, str, str]]:
    """Fetch email content and return (subject, from, body)."""
    logger.debug(f"Fetching email content - message_id: {message_id}")

    try:
        result, message_data = imap.fetch(str(message_id), "(RFC822)")
        if result != "OK":
            logger.error(f"Failed to fetch email - message_id: {message_id}, result: {result}")
            return None

        # Parse email message
        email_body = message_data[0][1]
        email_message = email.message_from_bytes(email_body)

        subject = email_message["Subject"] or ""
        from_addr = email_message["From"] or ""

        # Extract plain text body
        body = ""
        if email_message.is_multipart():
            for part in email_message.walk():
                if part.get_content_type() == "text/plain":
                    body = part.get_payload(decode=True).decode()
                    break
        else:
            body = email_message.get_payload(decode=True).decode()

        logger.debug(f"Email content fetched - message_id: {message_id}, subject: {subject}, from: {from_addr}")
        return subject, from_addr, body

    except Exception as e:
        logger.error(f"Error fetching email content - message_id: {message_id}, error: {str(e)}")
        return None


def delete_emails_by_subject(imap: imaplib.IMAP4, folder: str, subject: str) -> int:
    """Delete emails by subject and return count of deleted emails."""
    logger.info(f"Deleting emails by subject - folder: {folder}, subject: {subject}")

    try:
        # Select folder
        result, data = imap.select(folder)
        if result != "OK":
            logger.error(f"Failed to select IMAP folder for deletion - folder: {folder}, result: {result}")
            return 0

        # Find emails to delete
        message_ids = search_emails_by_subject(imap, folder, subject)
        if not message_ids:
            logger.debug(f"No emails found to delete - folder: {folder}, subject: {subject}")
            return 0

        # Mark emails for deletion
        for message_id in message_ids:
            imap.store(str(message_id), "+FLAGS", "\\Deleted")

        # Expunge to permanently delete
        imap.expunge()

        deleted_count = len(message_ids)
        logger.info(f"Emails deleted successfully - folder: {folder}, subject: {subject}, count: {deleted_count}")
        return deleted_count

    except Exception as e:
        logger.error(f"Error deleting emails by subject - folder: {folder}, subject: {subject}, error: {str(e)}")
        return 0


def cleanup_test_emails(imap: imaplib.IMAP4, test_subjects: List[str]) -> None:
    """Clean up test emails from all common folders."""
    logger.info(f"Cleaning up test emails - subjects: {test_subjects}")

    common_folders = ["INBOX", "Sent", "Drafts", "Trash"]
    total_deleted = 0

    for folder in common_folders:
        for subject in test_subjects:
            deleted = delete_emails_by_subject(imap, folder, subject)
            total_deleted += deleted

    logger.info(f"Test email cleanup completed - total_deleted: {total_deleted}")
