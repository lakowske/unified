#!/usr/bin/env python3
"""PostgreSQL LISTEN/NOTIFY service for automatic mailbox creation.

This service listens for database notifications when users are created, updated, or deleted
and automatically manages the corresponding mailbox directories.
"""

import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Optional

import psycopg2
import psycopg2.extensions

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
)
logger = logging.getLogger(__name__)


class MailboxManager:
    """Manages mailbox directory creation, updates, and deletion."""

    def __init__(self, mail_base_dir: str = "/var/mail", vmail_uid: int = 5000, vmail_gid: int = 5000) -> None:
        """Initialize the MailboxManager with mail directory and ownership settings."""
        self.mail_base_dir = Path(mail_base_dir)
        self.vmail_uid = vmail_uid
        self.vmail_gid = vmail_gid
        logger.info(f"MailboxManager initialized - base_dir: {self.mail_base_dir}, uid: {vmail_uid}, gid: {vmail_gid}")

    def create_mailbox(self, domain: str, username: str) -> bool:
        """Create a new mailbox directory structure for a user."""
        try:
            # Create domain directory if it doesn't exist
            domain_dir = self.mail_base_dir / domain
            domain_dir.mkdir(mode=0o755, exist_ok=True)

            # Create user mailbox directory
            user_dir = domain_dir / username
            if user_dir.exists():
                logger.warning(f"Mailbox already exists - user: {username}, domain: {domain}")
                return True

            # Create Maildir structure
            user_dir.mkdir(mode=0o700)
            (user_dir / "cur").mkdir(mode=0o700)
            (user_dir / "new").mkdir(mode=0o700)
            (user_dir / "tmp").mkdir(mode=0o700)

            # Create standard IMAP folders
            for folder in [".Drafts", ".Sent", ".Trash", ".Junk"]:
                folder_dir = user_dir / folder
                folder_dir.mkdir(mode=0o700)
                (folder_dir / "cur").mkdir(mode=0o700)
                (folder_dir / "new").mkdir(mode=0o700)
                (folder_dir / "tmp").mkdir(mode=0o700)

            # Create maildirfolder file for Dovecot
            (user_dir / "maildirfolder").touch(mode=0o644)

            # Set ownership to vmail user
            self._set_ownership_recursive(user_dir)

            logger.info(f"Mailbox created successfully - user: {username}, domain: {domain}, path: {user_dir}")
            return True

        except Exception as e:
            logger.error(f"Failed to create mailbox - user: {username}, domain: {domain}, error: {str(e)}")
            return False

    def update_mailbox(self, old_domain: str, old_username: str, new_domain: str, new_username: str) -> bool:
        """Move/rename a mailbox when user details change."""
        try:
            old_path = self.mail_base_dir / old_domain / old_username
            new_domain_dir = self.mail_base_dir / new_domain
            new_path = new_domain_dir / new_username

            if not old_path.exists():
                logger.warning(f"Old mailbox does not exist - old_path: {old_path}")
                # Create new mailbox instead
                return self.create_mailbox(new_domain, new_username)

            if old_path == new_path:
                logger.info(f"Mailbox path unchanged - path: {old_path}")
                return True

            # Create new domain directory if needed
            new_domain_dir.mkdir(mode=0o755, exist_ok=True)

            # Move the mailbox
            shutil.move(str(old_path), str(new_path))
            self._set_ownership_recursive(new_path)

            logger.info(f"Mailbox moved successfully - from: {old_path}, to: {new_path}")
            return True

        except Exception as e:
            logger.error(
                f"Failed to update mailbox - from: {old_domain}/{old_username}, to: {new_domain}/{new_username}, error: {str(e)}"
            )
            return False

    def delete_mailbox(self, domain: str, username: str) -> bool:
        """Delete a mailbox directory."""
        try:
            user_dir = self.mail_base_dir / domain / username

            if not user_dir.exists():
                logger.warning(f"Mailbox does not exist for deletion - user: {username}, domain: {domain}")
                return True

            # Remove the entire mailbox directory
            shutil.rmtree(user_dir)

            logger.info(f"Mailbox deleted successfully - user: {username}, domain: {domain}, path: {user_dir}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete mailbox - user: {username}, domain: {domain}, error: {str(e)}")
            return False

    def _set_ownership_recursive(self, path: Path) -> None:
        """Set ownership of directory and all contents to vmail user."""
        try:
            # Use subprocess to call chown since it's more reliable than os.chown for recursive operations
            subprocess.run(
                ["/bin/chown", "-R", f"{self.vmail_uid}:{self.vmail_gid}", str(path)], check=True, capture_output=True
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to set ownership - path: {path}, error: {e.stderr.decode()}")


class DatabaseListener:
    """Listens for PostgreSQL NOTIFY events and processes them."""

    def __init__(self, db_config: Dict[str, str], mailbox_manager: MailboxManager) -> None:
        """Initialize the DatabaseListener with database configuration and mailbox manager."""
        self.db_config = db_config
        self.mailbox_manager = mailbox_manager
        self.connection: Optional[psycopg2.extensions.connection] = None
        logger.info(f"DatabaseListener initialized - host: {db_config['host']}, database: {db_config['dbname']}")

    def connect(self) -> bool:
        """Establish connection to PostgreSQL database."""
        try:
            self.connection = psycopg2.connect(**self.db_config)
            self.connection.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)

            # Set up LISTEN channels
            cursor = self.connection.cursor()
            cursor.execute("LISTEN user_created;")
            cursor.execute("LISTEN user_updated;")
            cursor.execute("LISTEN user_deleted;")
            cursor.close()

            logger.info("Database connection established and LISTEN channels configured")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to database - error: {str(e)}")
            return False

    def listen(self) -> None:
        """Main listening loop for database notifications."""
        if not self.connection and not self.connect():
            return

        logger.info("Starting database notification listener...")

        try:
            import select

            while True:
                # Wait for notifications with a timeout (10 seconds)
                if select.select([self.connection], [], [], 10) == ([self.connection], [], []):
                    self.connection.poll()

                    # Process any notifications
                    while self.connection.notifies:
                        notify = self.connection.notifies.pop(0)
                        self._process_notification(notify.channel, notify.payload)

        except KeyboardInterrupt:
            logger.info("Received interrupt signal, shutting down...")
        except Exception as e:
            logger.error(f"Error in listening loop - error: {str(e)}")
        finally:
            if self.connection:
                self.connection.close()

    def _process_notification(self, channel: str, payload: str):
        """Process a single notification from the database."""
        try:
            data = json.loads(payload)
            logger.info(f"Received notification - channel: {channel}, user: {data.get('username', 'unknown')}")

            if channel == "user_created":
                self._handle_user_created(data)
            elif channel == "user_updated":
                self._handle_user_updated(data)
            elif channel == "user_deleted":
                self._handle_user_deleted(data)
            else:
                logger.warning(f"Unknown notification channel - channel: {channel}")

        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse notification payload - channel: {channel}, payload: {payload}, error: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Error processing notification - channel: {channel}, error: {str(e)}")

    def _handle_user_created(self, data: Dict):
        """Handle user creation notification."""
        username = data.get("username")
        domain = data.get("domain")

        if not username or not domain:
            logger.error(f"Missing required fields for user creation - data: {data}")
            return

        success = self.mailbox_manager.create_mailbox(domain, username)
        if success:
            logger.info(f"User creation processed successfully - username: {username}, domain: {domain}")
        else:
            logger.error(f"Failed to process user creation - username: {username}, domain: {domain}")

    def _handle_user_updated(self, data: Dict):
        """Handle user update notification."""
        old_domain = data.get("old_domain")
        old_username = data.get("username")  # Username typically doesn't change
        new_domain = data.get("new_domain")
        new_username = data.get("username")

        if not all([old_domain, old_username, new_domain, new_username]):
            logger.error(f"Missing required fields for user update - data: {data}")
            return

        success = self.mailbox_manager.update_mailbox(old_domain, old_username, new_domain, new_username)
        if success:
            logger.info(
                f"User update processed successfully - from: {old_domain}/{old_username}, to: {new_domain}/{new_username}"
            )
        else:
            logger.error(
                f"Failed to process user update - from: {old_domain}/{old_username}, to: {new_domain}/{new_username}"
            )

    def _handle_user_deleted(self, data: Dict):
        """Handle user deletion notification."""
        username = data.get("username")
        domain = data.get("domain")

        if not username or not domain:
            logger.error(f"Missing required fields for user deletion - data: {data}")
            return

        success = self.mailbox_manager.delete_mailbox(domain, username)
        if success:
            logger.info(f"User deletion processed successfully - username: {username}, domain: {domain}")
        else:
            logger.error(f"Failed to process user deletion - username: {username}, domain: {domain}")


def main():
    """Main entry point for the mailbox listener service."""
    logger.info("Starting PostgreSQL LISTEN/NOTIFY mailbox service...")

    # Get database configuration from environment
    db_config = {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", "5432")),
        "dbname": os.getenv("DB_NAME", "unified"),
        "user": os.getenv("DB_USER", "unified_user"),
        "password": os.getenv("DB_PASSWORD", ""),
    }

    # Get mailbox configuration from environment
    mail_base_dir = os.getenv("MAIL_BASE_DIR", "/var/mail")
    vmail_uid = int(os.getenv("VMAIL_UID", "5000"))
    vmail_gid = int(os.getenv("VMAIL_GID", "5000"))

    logger.info(
        f"Configuration - db_host: {db_config['host']}, db_port: {db_config['port']}, db_name: {db_config['dbname']}"
    )
    logger.info(f"Configuration - mail_base_dir: {mail_base_dir}, vmail_uid: {vmail_uid}, vmail_gid: {vmail_gid}")

    # Initialize components
    mailbox_manager = MailboxManager(mail_base_dir, vmail_uid, vmail_gid)
    listener = DatabaseListener(db_config, mailbox_manager)

    # Start listening for notifications
    listener.listen()


if __name__ == "__main__":
    main()
