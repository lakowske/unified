#!/usr/bin/env python3
"""Mail server certificate watcher for unified project.

Monitors PostgreSQL database for certificate changes and reloads SSL configuration.
"""

import logging
import os
import signal
import subprocess
import sys

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
)
logger = logging.getLogger(__name__)


class CertificateWatcher:
    """Watches for certificate changes and manages SSL configuration updates."""

    def __init__(self):
        """Initialize the certificate watcher."""
        self.db_connection = None
        self.current_cert_type = None
        self.current_ssl_enabled = False
        self.mail_domain = os.environ.get("MAIL_DOMAIN", "localhost")
        self.cert_type_preference = os.environ.get("CERT_TYPE_PREFERENCE", "")
        self.running = True

        # Certificate priority order
        self.cert_priority = {"live": 3, "staged": 2, "self-signed": 1, "none": 0}

        logger.info(
            f"Certificate watcher initialized - domain: {self.mail_domain}, preference: {self.cert_type_preference}"
        )

    def connect_to_database(self):
        """Connect to PostgreSQL database using environment variables."""
        try:
            # Build connection string from environment variables
            db_host = os.environ.get("DB_HOST", "localhost")
            db_port = os.environ.get("DB_PORT", "5432")
            db_name = os.environ.get("DB_NAME", "unified")
            db_user = os.environ.get("DB_USER", "unified_user")
            db_password = os.environ.get("DB_PASSWORD", "")

            conn_string = f"host={db_host} port={db_port} dbname={db_name} user={db_user} password={db_password}"

            self.db_connection = psycopg2.connect(conn_string)
            self.db_connection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)

            logger.info(f"Connected to PostgreSQL database: {db_host}:{db_port}/{db_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            return False

    def get_current_certificate_status(self):
        """Get current certificate status from database."""
        try:
            with self.db_connection.cursor() as cur:
                cur.execute(
                    """
                    SELECT certificate_type, ssl_enabled, last_updated
                    FROM unified.service_certificates
                    WHERE service_name = %s AND domain = %s AND is_active = true
                """,
                    ("mail", self.mail_domain),
                )

                result = cur.fetchone()
                if result:
                    cert_type, ssl_enabled, last_updated = result
                    logger.debug(
                        f"Current certificate status - type: {cert_type}, ssl: {ssl_enabled}, updated: {last_updated}"
                    )
                    return cert_type, ssl_enabled
                logger.debug("No certificate status found in database")
                return None, False

        except Exception as e:
            logger.error(f"Failed to get certificate status: {e}")
            return None, False

    def check_for_certificate_updates(self):
        """Check if there are newer certificates available."""
        try:
            with self.db_connection.cursor() as cur:
                # Get all available certificates for this domain
                cur.execute(
                    """
                    SELECT certificate_type, created_at, is_active
                    FROM unified.certificates
                    WHERE domain = %s AND is_active = true
                    ORDER BY created_at DESC
                """,
                    (self.mail_domain,),
                )

                available_certs = cur.fetchall()

                if not available_certs:
                    logger.debug("No certificates found in database")
                    return False, None

                # If we have a specific preference, only check for that type
                if self.cert_type_preference:
                    for cert_type, _created_at, _is_active in available_certs:
                        if cert_type == self.cert_type_preference:
                            # Check if this certificate is newer than what we're using
                            if cert_type != self.current_cert_type:
                                logger.info(f"New preferred certificate available: {cert_type}")
                                return True, cert_type
                            break
                    return False, None

                # Otherwise, use priority order
                best_cert_type = None
                best_priority = 0

                for cert_type, _created_at, _is_active in available_certs:
                    priority = self.cert_priority.get(cert_type, 0)
                    if priority > best_priority:
                        best_cert_type = cert_type
                        best_priority = priority

                # Check if we should upgrade to a better certificate
                current_priority = self.cert_priority.get(self.current_cert_type, 0)
                if best_priority > current_priority:
                    logger.info(
                        f"Better certificate available: {best_cert_type} (priority {best_priority}) > {self.current_cert_type} (priority {current_priority})"
                    )
                    return True, best_cert_type

                return False, None

        except Exception as e:
            logger.error(f"Failed to check for certificate updates: {e}")
            return False, None

    def reload_ssl_configuration(self):
        """Reload SSL configuration by running the configure-ssl.sh script."""
        try:
            logger.info("Reloading SSL configuration...")

            # Run the SSL configuration script
            result = subprocess.run(["/usr/local/bin/configure-ssl.sh"], capture_output=True, text=True, timeout=60)  # noqa: S603

            if result.returncode == 0:
                logger.info("SSL configuration updated successfully")

                # Run the SSL reload script for safe service reloads
                reload_result = subprocess.run(  # noqa: S603
                    ["/usr/local/bin/reload-ssl.sh"], capture_output=True, text=True, timeout=60
                )

                if reload_result.returncode == 0:
                    logger.info("Mail services reloaded successfully")

                    # Update our current status
                    self.current_cert_type, self.current_ssl_enabled = self.get_current_certificate_status()

                    return True
                logger.error(f"Service reload failed: {reload_result.stderr}")
                return False
            logger.error(f"SSL configuration reload failed: {result.stderr}")
            return False

        except subprocess.TimeoutExpired:
            logger.error("SSL configuration reload timed out")
            return False
        except Exception as e:
            logger.error(f"Failed to reload SSL configuration: {e}")
            return False

    def listen_for_notifications(self):
        """Listen for PostgreSQL NOTIFY messages about certificate changes."""
        try:
            with self.db_connection.cursor() as cur:
                # Listen for certificate change notifications
                cur.execute("LISTEN certificate_change")
                logger.info("Listening for certificate change notifications...")

                # Do an initial check for certificate updates at startup
                needs_update, new_cert_type = self.check_for_certificate_updates()
                if needs_update:
                    logger.info(f"Initial certificate update detected: {new_cert_type}")
                    self.reload_ssl_configuration()

                while self.running:
                    # Use select() for efficient, interruptible waiting
                    import select

                    # Wait for notifications with 1 second timeout for signal responsiveness
                    ready = select.select([self.db_connection], [], [], 1.0)

                    if ready[0]:  # Database connection has data
                        self.db_connection.poll()
                        while self.db_connection.notifies:
                            notify = self.db_connection.notifies.pop(0)
                            logger.info(f"Received notification: {notify.channel} - {notify.payload}")

                            # Check if this notification is relevant to our mail service
                            if notify.payload.startswith(f"mail:{self.mail_domain}"):
                                logger.info("Certificate change notification received for mail service")
                                self.handle_certificate_change()

                    # No polling needed - purely event-driven via LISTEN/NOTIFY

        except Exception as e:
            logger.error(f"Error listening for notifications: {e}")

    def handle_certificate_change(self):
        """Handle certificate change notification."""
        logger.info("Handling certificate change notification...")

        # Check if we need to update our certificate
        needs_update, new_cert_type = self.check_for_certificate_updates()

        if needs_update:
            logger.info(f"Certificate needs update: {self.current_cert_type} -> {new_cert_type}")
            self.reload_ssl_configuration()
        else:
            logger.debug("No certificate update needed")

    def signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False

    def run(self):
        """Main run loop."""
        logger.info("Starting mail certificate watcher...")

        # Set up signal handlers
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)

        # Connect to database
        if not self.connect_to_database():
            logger.error("Failed to connect to database, exiting")
            return 1

        # Get initial certificate status
        self.current_cert_type, self.current_ssl_enabled = self.get_current_certificate_status()
        logger.info(f"Initial certificate status - type: {self.current_cert_type}, ssl: {self.current_ssl_enabled}")

        try:
            # Start listening for notifications
            self.listen_for_notifications()

        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, shutting down...")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return 1
        finally:
            if self.db_connection:
                self.db_connection.close()
                logger.info("Database connection closed")

        logger.info("Mail certificate watcher stopped")
        return 0


if __name__ == "__main__":
    watcher = CertificateWatcher()
    sys.exit(watcher.run())
