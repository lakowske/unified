#!/usr/bin/env python3
"""DNS DKIM Record Management Script
This script manages DKIM records in the DNS database and zone files.
"""

import logging
import os
import re
import subprocess
import sys
from datetime import datetime

import psycopg2

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class DKIMRecordManager:
    """Manages DKIM records in DNS database and zone files."""

    def __init__(self):
        self.db_config = {
            "host": os.getenv("DB_HOST", "localhost"),
            "port": int(os.getenv("DB_PORT", "5432")),
            "database": os.getenv("DB_NAME", "unified"),
            "user": os.getenv("DB_USER", "unified_user"),
            "password": os.getenv("DB_PASSWORD", ""),
        }
        self.mail_domain = os.getenv("MAIL_DOMAIN", "localhost")
        self.mail_server_ip = os.getenv("MAIL_SERVER_IP", "127.0.0.1")

    def connect_db(self):
        """Connect to the database."""
        try:
            conn = psycopg2.connect(**self.db_config)
            logger.info(f"Connected to database: {self.db_config['host']}:{self.db_config['port']}")
            return conn
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise

    def get_dkim_public_key(self):
        """Extract DKIM public key from OpenDKIM key file."""
        key_file = f"/etc/opendkim/keys/{self.mail_domain}/mail.txt"

        try:
            with open(key_file) as f:
                content = f.read()

            # Extract public key from DKIM record
            p_match = re.search(r"p=([A-Za-z0-9+/=\s]+)", content)
            if p_match:
                # Clean up the public key (remove whitespace)
                public_key = re.sub(r"\s+", "", p_match.group(1))
                logger.info(f"Extracted DKIM public key (length: {len(public_key)})")
                return public_key
            logger.error("Could not extract public key from DKIM record")
            return None

        except FileNotFoundError:
            logger.error(f"DKIM key file not found: {key_file}")
            return None
        except Exception as e:
            logger.error(f"Error reading DKIM key file: {e}")
            return None

    def update_dkim_record_in_db(self, public_key):
        """Update DKIM record in the database."""
        conn = self.connect_db()
        try:
            with conn.cursor() as cursor:
                # Prepare DKIM record value
                dkim_value = f"v=DKIM1; h=sha256; k=rsa; p={public_key}"

                # Insert or update DKIM record
                cursor.execute(
                    """
                    INSERT INTO unified.dns_records (domain, name, type, value, ttl)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (domain, name, type)
                    DO UPDATE SET
                        value = EXCLUDED.value,
                        updated_at = CURRENT_TIMESTAMP
                """,
                    (self.mail_domain, "mail._domainkey", "TXT", dkim_value, 3600),
                )

                conn.commit()
                logger.info(f"DKIM record updated in database for domain: {self.mail_domain}")

        except Exception as e:
            logger.error(f"Error updating DKIM record in database: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    def update_zone_file(self, public_key):
        """Update the zone file with DKIM record."""
        zone_file = f"/data/dns/zones/{self.mail_domain}.zone"

        try:
            # Read current zone file
            if os.path.exists(zone_file):
                with open(zone_file) as f:
                    content = f.read()
            else:
                # Create new zone file from template
                template_file = "/usr/local/bin/dns/zones/mail-domain.zone.template"
                if os.path.exists(template_file):
                    with open(template_file) as f:
                        content = f.read()

                    # Replace placeholders
                    content = content.replace("${MAIL_DOMAIN}", self.mail_domain)
                    content = content.replace("${MAIL_SERVER_IP}", self.mail_server_ip)
                else:
                    logger.error(f"Zone template not found: {template_file}")
                    return False

            # Prepare DKIM record
            dkim_record = f'mail._domainkey    IN    TXT    "v=DKIM1; h=sha256; k=rsa; p={public_key}"'

            # Replace or add DKIM record
            dkim_pattern = r"mail\._domainkey\s+IN\s+TXT\s+.*"
            if re.search(dkim_pattern, content):
                # Replace existing DKIM record
                content = re.sub(dkim_pattern, dkim_record, content)
                logger.info("Replaced existing DKIM record in zone file")
            else:
                # Add DKIM record after DMARC record or at the end
                dmarc_pattern = r"(_dmarc\s+IN\s+TXT\s+.*)"
                if re.search(dmarc_pattern, content):
                    content = re.sub(dmarc_pattern, r"\1\n\n; DKIM record\n" + dkim_record, content)
                else:
                    content += f"\n\n; DKIM record\n{dkim_record}\n"
                logger.info("Added DKIM record to zone file")

            # Update serial number
            today = datetime.now().strftime("%Y%m%d")
            serial_pattern = r"(\d{10})\s*;\s*serial"

            def increment_serial(match):
                current_serial = match.group(1)
                if current_serial.startswith(today):
                    # Increment the sequence number
                    seq = int(current_serial[-2:]) + 1
                    return f"{today}{seq:02d}    ; serial"
                # New day, start with 01
                return f"{today}01    ; serial"

            content = re.sub(serial_pattern, increment_serial, content)

            # Write updated zone file
            with open(zone_file, "w") as f:
                f.write(content)

            logger.info(f"Zone file updated: {zone_file}")
            return True

        except Exception as e:
            logger.error(f"Error updating zone file: {e}")
            return False

    def reload_dns_server(self):
        """Reload the DNS server configuration."""
        try:
            # Send SIGHUP to named to reload configuration
            result = subprocess.run(["rndc", "reload"], capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                logger.info("DNS server reloaded successfully")
                return True
            logger.error(f"DNS server reload failed: {result.stderr}")
            return False

        except subprocess.TimeoutExpired:
            logger.error("DNS server reload timed out")
            return False
        except Exception as e:
            logger.error(f"Error reloading DNS server: {e}")
            return False

    def update_all_mail_records(self):
        """Update all mail-related DNS records with current configuration."""
        conn = self.connect_db()
        try:
            with conn.cursor() as cursor:
                # Update all placeholder records with actual values
                cursor.execute(
                    """
                    UPDATE unified.dns_records
                    SET value = REPLACE(REPLACE(value, 'PLACEHOLDER_MAIL_DOMAIN', %s),
                                       'PLACEHOLDER_MAIL_SERVER_IP', %s),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE domain = %s OR value LIKE '%%PLACEHOLDER_MAIL_DOMAIN%%'
                """,
                    (self.mail_domain, self.mail_server_ip, self.mail_domain),
                )

                # Update zone record
                cursor.execute(
                    """
                    UPDATE unified.dns_zones
                    SET domain = %s,
                        primary_ns = %s,
                        admin_email = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE domain = 'PLACEHOLDER_MAIL_DOMAIN' OR domain = %s
                """,
                    (self.mail_domain, f"ns1.{self.mail_domain}", f"admin@{self.mail_domain}", self.mail_domain),
                )

                conn.commit()
                logger.info("All mail DNS records updated with current configuration")

        except Exception as e:
            logger.error(f"Error updating mail records: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    def run(self):
        """Main execution method."""
        logger.info(f"Starting DKIM record management for domain: {self.mail_domain}")

        # Update all mail records first
        self.update_all_mail_records()

        # Get DKIM public key
        public_key = self.get_dkim_public_key()
        if not public_key:
            logger.error("Could not retrieve DKIM public key")
            return False

        # Update database
        self.update_dkim_record_in_db(public_key)

        # Update zone file
        if not self.update_zone_file(public_key):
            logger.error("Failed to update zone file")
            return False

        # Reload DNS server
        if not self.reload_dns_server():
            logger.warning("DNS server reload failed, but records were updated")

        logger.info("DKIM record management completed successfully")
        return True


if __name__ == "__main__":
    manager = DKIMRecordManager()
    success = manager.run()
    sys.exit(0 if success else 1)
