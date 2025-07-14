"""Configuration and fixtures for mail container tests."""

import logging
import os
import uuid
from typing import Generator, Tuple

import psycopg2
import pytest

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
)
logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def mail_config():
    """Configuration for mail server connection."""
    return {
        "smtp_host": os.getenv("MAIL_SMTP_HOST", "localhost"),
        "smtp_port": int(os.getenv("MAIL_SMTP_PORT", "2525")),
        "imap_host": os.getenv("MAIL_IMAP_HOST", "localhost"),
        "imap_port": int(os.getenv("MAIL_IMAP_PORT", "1143")),
        "mail_domain": os.getenv("MAIL_DOMAIN", "localhost"),
    }


@pytest.fixture(scope="session")
def db_config():
    """Configuration for PostgreSQL database connection."""
    return {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", "5432")),
        "database": os.getenv("DB_NAME", "unified"),
        "user": os.getenv("DB_USER", "unified_user"),
        "password": os.getenv("DB_PASSWORD", ""),
        "sslmode": os.getenv("DB_SSLMODE", "prefer"),
    }


@pytest.fixture
def db_connection(db_config):
    """Provide a database connection for tests."""
    logger.info(
        f"Connecting to database - host: {db_config['host']}, port: {db_config['port']}, database: {db_config['database']}"
    )
    conn = psycopg2.connect(**db_config)
    try:
        yield conn
    finally:
        conn.close()
        logger.debug("Database connection closed")


@pytest.fixture
def test_user(db_connection, mail_config) -> Generator[Tuple[str, str], None, None]:
    """Create a test user for mail testing with cleanup."""
    test_id = str(uuid.uuid4())[:8]
    username = f"testuser_{test_id}"
    email = f"{username}@{mail_config['mail_domain']}"
    password = f"testpass_{test_id}"

    logger.info(f"Creating test user - username: {username}, email: {email}")

    with db_connection.cursor() as cursor:
        # Insert test user
        cursor.execute(
            """
            INSERT INTO unified.users (username, email, domain, is_active, email_verified)
            VALUES (%s, %s, %s, true, true)
            RETURNING id
        """,
            (username, email, mail_config["mail_domain"]),
        )

        user_id = cursor.fetchone()[0]

        # Insert dovecot password entry
        cursor.execute(
            """
            INSERT INTO unified.user_passwords (user_id, service, password_hash, hash_scheme)
            VALUES (%s, 'dovecot', %s, 'PLAIN')
        """,
            (user_id, password),
        )

        db_connection.commit()
        logger.debug(f"Test user created - user_id: {user_id}")

    try:
        yield (email, password)
    finally:
        # Cleanup test user
        logger.info(f"Cleaning up test user - username: {username}")
        with db_connection.cursor() as cursor:
            cursor.execute("DELETE FROM unified.user_passwords WHERE user_id = %s", (user_id,))
            cursor.execute("DELETE FROM unified.users WHERE id = %s", (user_id,))
            db_connection.commit()
            logger.debug("Test user cleanup completed")


@pytest.fixture
def test_user_pair(db_connection, mail_config) -> Generator[Tuple[Tuple[str, str], Tuple[str, str]], None, None]:
    """Create two test users for cross-user mail testing."""
    test_id = str(uuid.uuid4())[:8]

    users = []
    user_ids = []

    for i in range(2):
        username = f"testuser_{test_id}_{i}"
        email = f"{username}@{mail_config['mail_domain']}"
        password = f"testpass_{test_id}_{i}"

        logger.info(f"Creating test user {i+1} - username: {username}, email: {email}")

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
            user_ids.append(user_id)

            cursor.execute(
                """
                INSERT INTO unified.user_passwords (user_id, service, password_hash, hash_scheme)
                VALUES (%s, 'dovecot', %s, 'PLAIN')
            """,
                (user_id, password),
            )

            users.append((email, password))

        db_connection.commit()
        logger.debug(f"Test user {i+1} created - user_id: {user_id}")

    try:
        yield (users[0], users[1])
    finally:
        # Cleanup both test users
        logger.info(f"Cleaning up test user pair - test_id: {test_id}")
        with db_connection.cursor() as cursor:
            for user_id in user_ids:
                cursor.execute("DELETE FROM unified.user_passwords WHERE user_id = %s", (user_id,))
                cursor.execute("DELETE FROM unified.users WHERE id = %s", (user_id,))
            db_connection.commit()
            logger.debug("Test user pair cleanup completed")


@pytest.fixture
def unique_subject():
    """Generate a unique email subject for testing."""
    test_id = str(uuid.uuid4())[:8]
    subject = f"Test Email {test_id}"
    logger.debug(f"Generated unique subject - subject: {subject}")
    return subject
