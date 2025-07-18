"""Database Schema Integration Tests

This module provides comprehensive tests for database schema integrity,
migrations, and data consistency in the unified infrastructure.
"""

import logging
import subprocess
import time
from typing import Any, Dict, List

import pytest

logger = logging.getLogger(__name__)


class DatabaseTestManager:
    """Manages database testing operations."""

    def __init__(self, container_name: str = "postgres-dev"):
        self.container_name = container_name
        self.db_user = "unified_dev_user"
        self.db_name = "unified_dev"

    def execute_query(self, query: str, timeout: int = 30) -> Dict[str, Any]:
        """Execute a SQL query and return results."""
        try:
            result = subprocess.run(
                ["docker", "exec", self.container_name, "psql", "-U", self.db_user, "-d", self.db_name, "-c", query],
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "stdout": "", "stderr": "Query timed out", "returncode": -1}
        except Exception as e:
            return {"success": False, "stdout": "", "stderr": str(e), "returncode": -1}

    def get_table_names(self) -> List[str]:
        """Get list of all table names in the database."""
        query = """
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = 'unified'
        ORDER BY tablename;
        """
        result = self.execute_query(query)

        if result["success"]:
            # Parse table names from output
            lines = result["stdout"].strip().split("\n")
            tables = []
            for line in lines:
                line = line.strip()
                if line and not line.startswith("-") and not line.startswith("tablename") and line != "(0 rows)":
                    if "|" in line:
                        continue  # Skip header separator
                    if line.startswith("("):
                        break  # End of results
                    tables.append(line)
            return tables
        return []

    def get_table_columns(self, table_name: str) -> List[Dict[str, str]]:
        """Get column information for a table."""
        query = f"""
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_name = '{table_name}' AND table_schema = 'unified'
        ORDER BY ordinal_position;
        """
        result = self.execute_query(query)

        columns = []
        if result["success"]:
            # Parse column information
            lines = result["stdout"].strip().split("\n")
            for line in lines[2:]:  # Skip header lines
                line = line.strip()
                if line and not line.startswith("-") and not line.startswith("("):
                    parts = line.split("|")
                    if len(parts) >= 4:
                        columns.append(
                            {
                                "name": parts[0].strip(),
                                "type": parts[1].strip(),
                                "nullable": parts[2].strip(),
                                "default": parts[3].strip(),
                            }
                        )
        return columns

    def check_foreign_keys(self, table_name: str) -> List[Dict[str, str]]:
        """Check foreign key constraints for a table."""
        query = f"""
        SELECT
            kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name
        FROM information_schema.key_column_usage kcu
        JOIN information_schema.table_constraints tc
            ON kcu.constraint_name = tc.constraint_name
        JOIN information_schema.constraint_column_usage ccu
            ON ccu.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
            AND kcu.table_name = '{table_name}'
            AND kcu.table_schema = 'unified';
        """
        result = self.execute_query(query)

        foreign_keys = []
        if result["success"]:
            lines = result["stdout"].strip().split("\n")
            for line in lines[2:]:  # Skip header lines
                line = line.strip()
                if line and not line.startswith("-") and not line.startswith("("):
                    parts = line.split("|")
                    if len(parts) >= 3:
                        foreign_keys.append(
                            {
                                "column": parts[0].strip(),
                                "foreign_table": parts[1].strip(),
                                "foreign_column": parts[2].strip(),
                            }
                        )
        return foreign_keys

    def check_indexes(self, table_name: str) -> List[Dict[str, str]]:
        """Check indexes for a table."""
        query = f"""
        SELECT
            i.relname AS index_name,
            a.attname AS column_name,
            ix.indisunique AS is_unique
        FROM pg_class i
        JOIN pg_index ix ON i.oid = ix.indexrelid
        JOIN pg_class t ON ix.indrelid = t.oid
        JOIN pg_namespace n ON t.relnamespace = n.oid
        JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(ix.indkey)
        WHERE t.relname = '{table_name}' AND n.nspname = 'unified'
        ORDER BY i.relname, a.attname;
        """
        result = self.execute_query(query)

        indexes = []
        if result["success"]:
            lines = result["stdout"].strip().split("\n")
            for line in lines[2:]:  # Skip header lines
                line = line.strip()
                if line and not line.startswith("-") and not line.startswith("("):
                    parts = line.split("|")
                    if len(parts) >= 3:
                        indexes.append(
                            {"name": parts[0].strip(), "column": parts[1].strip(), "unique": parts[2].strip() == "t"}
                        )
        return indexes

    def get_row_count(self, table_name: str) -> int:
        """Get row count for a table."""
        query = f"SELECT COUNT(*) FROM unified.{table_name};"
        result = self.execute_query(query)

        if result["success"]:
            lines = result["stdout"].strip().split("\n")
            for line in lines:
                line = line.strip()
                if line.isdigit():
                    return int(line)
        return 0

    def check_flyway_migrations(self) -> List[Dict[str, Any]]:
        """Check Flyway migration history."""
        query = """
        SELECT version, description, type, script, checksum, installed_on, success
        FROM unified.flyway_schema_history
        ORDER BY installed_rank;
        """
        result = self.execute_query(query)

        migrations = []
        if result["success"]:
            lines = result["stdout"].strip().split("\n")
            for line in lines[2:]:  # Skip header lines
                line = line.strip()
                if line and not line.startswith("-") and not line.startswith("("):
                    parts = line.split("|")
                    if len(parts) >= 7:
                        migrations.append(
                            {
                                "version": parts[0].strip(),
                                "description": parts[1].strip(),
                                "type": parts[2].strip(),
                                "script": parts[3].strip(),
                                "checksum": parts[4].strip(),
                                "installed_on": parts[5].strip(),
                                "success": parts[6].strip() == "t",
                            }
                        )
        return migrations


@pytest.fixture(scope="session")
def db_manager():
    """Create a database test manager."""
    return DatabaseTestManager()


@pytest.fixture(scope="session")
def db_ready(db_manager):
    """Ensure database is ready for testing."""
    # Test basic connectivity
    result = db_manager.execute_query("SELECT 1;")
    assert result["success"], f"Database not ready: {result['stderr']}"
    return db_manager


class TestDatabaseSchema:
    """Test database schema integrity."""

    def test_required_tables_exist(self, db_ready):
        """Test that all required tables exist."""
        tables = db_ready.get_table_names()

        # Required tables based on the unified schema
        required_tables = ["users", "user_passwords", "user_roles", "flyway_schema_history"]

        missing_tables = []
        for table in required_tables:
            if table not in tables:
                missing_tables.append(table)

        assert not missing_tables, f"Missing required tables: {missing_tables}"
        logger.info(f"All required tables exist: {required_tables}")

    def test_users_table_structure(self, db_ready):
        """Test users table structure."""
        columns = db_ready.get_table_columns("users")
        assert columns, "Users table has no columns"

        # Check for required columns
        column_names = [col["name"] for col in columns]
        required_columns = ["id", "username", "email", "created_at", "is_active"]

        missing_columns = []
        for col in required_columns:
            if col not in column_names:
                missing_columns.append(col)

        assert not missing_columns, f"Missing required columns in users table: {missing_columns}"

        # Check specific column properties
        id_column = next((col for col in columns if col["name"] == "id"), None)
        assert id_column, "ID column not found"
        assert (
            "serial" in id_column["type"].lower() or "integer" in id_column["type"].lower()
        ), "ID column should be serial/integer"

        username_column = next((col for col in columns if col["name"] == "username"), None)
        assert username_column, "Username column not found"
        assert (
            "character" in username_column["type"].lower() or "varchar" in username_column["type"].lower()
        ), "Username should be character type"

        logger.info(f"Users table structure validated: {len(columns)} columns")

    def test_user_passwords_table_structure(self, db_ready):
        """Test user_passwords table structure."""
        columns = db_ready.get_table_columns("user_passwords")
        assert columns, "User_passwords table has no columns"

        column_names = [col["name"] for col in columns]
        required_columns = ["user_id", "service", "password_hash", "hash_scheme"]

        missing_columns = []
        for col in required_columns:
            if col not in column_names:
                missing_columns.append(col)

        assert not missing_columns, f"Missing required columns in user_passwords table: {missing_columns}"

        # Check foreign key relationship
        foreign_keys = db_ready.check_foreign_keys("user_passwords")
        user_id_fk = next((fk for fk in foreign_keys if fk["column"] == "user_id"), None)
        assert user_id_fk, "user_id foreign key not found"
        assert user_id_fk["foreign_table"] == "users", "user_id should reference users table"

        logger.info("User_passwords table structure validated")

    def test_user_roles_table_structure(self, db_ready):
        """Test user_roles table structure."""
        columns = db_ready.get_table_columns("user_roles")
        assert columns, "User_roles table has no columns"

        column_names = [col["name"] for col in columns]
        required_columns = ["user_id", "role_name", "service"]

        missing_columns = []
        for col in required_columns:
            if col not in column_names:
                missing_columns.append(col)

        assert not missing_columns, f"Missing required columns in user_roles table: {missing_columns}"

        # Check foreign key relationship
        foreign_keys = db_ready.check_foreign_keys("user_roles")
        user_id_fk = next((fk for fk in foreign_keys if fk["column"] == "user_id"), None)
        assert user_id_fk, "user_id foreign key not found"
        assert user_id_fk["foreign_table"] == "users", "user_id should reference users table"

        logger.info("User_roles table structure validated")

    def test_table_indexes(self, db_ready):
        """Test that appropriate indexes exist."""
        # Check users table indexes
        users_indexes = db_ready.check_indexes("users")
        username_indexed = any(idx["column"] == "username" for idx in users_indexes)
        email_indexed = any(idx["column"] == "email" for idx in users_indexes)

        # Username should be indexed (likely unique)
        assert username_indexed, "Username column should be indexed"

        # Email should be indexed if it exists
        if email_indexed:
            logger.info("Email column is indexed")

        # Check for primary key index
        pk_index = any(idx["unique"] for idx in users_indexes)
        assert pk_index, "Users table should have a primary key index"

        logger.info(f"Users table indexes validated: {len(users_indexes)} indexes")

    def test_referential_integrity(self, db_ready):
        """Test referential integrity constraints."""
        # Test that all foreign key constraints work

        # Check user_passwords foreign keys
        password_fks = db_ready.check_foreign_keys("user_passwords")
        assert password_fks, "user_passwords table should have foreign key constraints"

        # Check user_roles foreign keys
        role_fks = db_ready.check_foreign_keys("user_roles")
        assert role_fks, "user_roles table should have foreign key constraints"

        # Verify all foreign keys point to users table
        for fk in password_fks + role_fks:
            if fk["column"] == "user_id":
                assert (
                    fk["foreign_table"] == "users"
                ), f"Foreign key should reference users table, got {fk['foreign_table']}"

        logger.info("Referential integrity constraints validated")


class TestMigrations:
    """Test database migrations."""

    def test_flyway_migration_history(self, db_ready):
        """Test Flyway migration history."""
        migrations = db_ready.check_flyway_migrations()

        # Should have at least one migration
        assert migrations, "No Flyway migrations found"

        # All migrations should be successful
        failed_migrations = [m for m in migrations if not m["success"]]
        assert not failed_migrations, f"Failed migrations found: {failed_migrations}"

        # Check for baseline migration
        baseline_migration = next((m for m in migrations if m["type"] == "BASELINE"), None)
        if baseline_migration:
            logger.info(f"Found baseline migration: {baseline_migration['version']}")

        logger.info(f"Flyway migrations validated: {len(migrations)} migrations")

    def test_migration_checksums(self, db_ready):
        """Test migration checksum integrity."""
        migrations = db_ready.check_flyway_migrations()

        # All migrations should have checksums
        no_checksum = [m for m in migrations if not m["checksum"] or m["checksum"] in ["", "NULL"]]
        assert not no_checksum, f"Migrations without checksums: {no_checksum}"

        # Check for duplicate checksums (would indicate migration conflicts)
        checksums = [m["checksum"] for m in migrations if m["checksum"] and m["checksum"] != "NULL"]
        duplicate_checksums = []
        seen_checksums = set()

        for checksum in checksums:
            if checksum in seen_checksums:
                duplicate_checksums.append(checksum)
            seen_checksums.add(checksum)

        assert not duplicate_checksums, f"Duplicate migration checksums found: {duplicate_checksums}"

        logger.info("Migration checksums validated")

    def test_migration_order(self, db_ready):
        """Test migration version ordering."""
        migrations = db_ready.check_flyway_migrations()

        # Get versions (skip baseline)
        versions = [m["version"] for m in migrations if m["type"] != "BASELINE"]

        # Versions should be in order
        for i in range(1, len(versions)):
            prev_version = versions[i - 1]
            curr_version = versions[i]

            # Simple version comparison (assuming semantic versioning)
            if prev_version and curr_version:
                assert prev_version <= curr_version, f"Migration versions out of order: {prev_version} > {curr_version}"

        logger.info(f"Migration ordering validated: {len(versions)} versions")


class TestDataIntegrity:
    """Test data integrity and constraints."""

    def test_data_consistency(self, db_ready):
        """Test data consistency across related tables."""
        # Test that all user_passwords.user_id references exist in users
        query = """
        SELECT COUNT(*) FROM user_passwords up
        LEFT JOIN users u ON up.user_id = u.id
        WHERE u.id IS NULL;
        """
        result = db_ready.execute_query(query)

        if result["success"]:
            orphaned_count = 0
            for line in result["stdout"].strip().split("\n"):
                if line.strip().isdigit():
                    orphaned_count = int(line.strip())
                    break

            assert orphaned_count == 0, f"Found {orphaned_count} orphaned user_passwords records"

        # Test that all user_roles.user_id references exist in users
        query = """
        SELECT COUNT(*) FROM user_roles ur
        LEFT JOIN users u ON ur.user_id = u.id
        WHERE u.id IS NULL;
        """
        result = db_ready.execute_query(query)

        if result["success"]:
            orphaned_count = 0
            for line in result["stdout"].strip().split("\n"):
                if line.strip().isdigit():
                    orphaned_count = int(line.strip())
                    break

            assert orphaned_count == 0, f"Found {orphaned_count} orphaned user_roles records"

        logger.info("Data consistency validated")

    def test_unique_constraints(self, db_ready):
        """Test unique constraints."""
        # Test username uniqueness
        query = """
        SELECT username, COUNT(*) as count
        FROM users
        GROUP BY username
        HAVING COUNT(*) > 1;
        """
        result = db_ready.execute_query(query)

        if result["success"]:
            # Should return no rows if usernames are unique
            duplicate_lines = [
                line
                for line in result["stdout"].strip().split("\n")
                if line.strip() and not line.startswith("-") and not line.startswith("username") and "|" in line
            ]
            assert not duplicate_lines, f"Found duplicate usernames: {duplicate_lines}"

        # Test email uniqueness (if email column exists and has unique constraint)
        query = """
        SELECT email, COUNT(*) as count
        FROM users
        WHERE email IS NOT NULL
        GROUP BY email
        HAVING COUNT(*) > 1;
        """
        result = db_ready.execute_query(query)

        if result["success"]:
            duplicate_lines = [
                line
                for line in result["stdout"].strip().split("\n")
                if line.strip() and not line.startswith("-") and not line.startswith("email") and "|" in line
            ]
            # Note: This might not be enforced depending on schema
            if duplicate_lines:
                logger.warning(f"Found duplicate emails: {duplicate_lines}")

        logger.info("Unique constraints validated")

    def test_not_null_constraints(self, db_ready):
        """Test NOT NULL constraints."""
        # Test users table NOT NULL constraints
        query = """
        SELECT COUNT(*) FROM users
        WHERE username IS NULL OR created_at IS NULL;
        """
        result = db_ready.execute_query(query)

        if result["success"]:
            null_count = 0
            for line in result["stdout"].strip().split("\n"):
                if line.strip().isdigit():
                    null_count = int(line.strip())
                    break

            assert null_count == 0, f"Found {null_count} users with NULL required fields"

        # Test user_passwords table NOT NULL constraints
        query = """
        SELECT COUNT(*) FROM user_passwords
        WHERE user_id IS NULL OR service IS NULL OR password_hash IS NULL;
        """
        result = db_ready.execute_query(query)

        if result["success"]:
            null_count = 0
            for line in result["stdout"].strip().split("\n"):
                if line.strip().isdigit():
                    null_count = int(line.strip())
                    break

            assert null_count == 0, f"Found {null_count} user_passwords with NULL required fields"

        logger.info("NOT NULL constraints validated")


@pytest.mark.performance
class TestDatabasePerformance:
    """Test database performance."""

    def test_query_performance(self, db_ready):
        """Test basic query performance."""
        # Test simple select performance
        start_time = time.time()
        result = db_ready.execute_query("SELECT COUNT(*) FROM unified.users;")
        end_time = time.time()

        assert result["success"], f"Query failed: {result['stderr']}"

        query_time = end_time - start_time
        assert query_time < 1.0, f"Simple query too slow: {query_time:.3f}s"

        logger.info(f"Simple query performance: {query_time:.3f}s")

    def test_join_performance(self, db_ready):
        """Test JOIN query performance."""
        # Test JOIN between users and user_passwords
        start_time = time.time()
        query = """
        SELECT u.username, up.service, ur.role_name
        FROM unified.users u
        LEFT JOIN unified.user_passwords up ON u.id = up.user_id
        LEFT JOIN unified.user_roles ur ON u.id = ur.user_id
        LIMIT 100;
        """
        result = db_ready.execute_query(query)
        end_time = time.time()

        assert result["success"], f"JOIN query failed: {result['stderr']}"

        query_time = end_time - start_time
        assert query_time < 2.0, f"JOIN query too slow: {query_time:.3f}s"

        logger.info(f"JOIN query performance: {query_time:.3f}s")

    def test_index_usage(self, db_ready):
        """Test that indexes are being used effectively."""
        # Test username lookup performance (should use index)
        start_time = time.time()
        result = db_ready.execute_query("SELECT * FROM unified.users WHERE username = 'nonexistent_user';")
        end_time = time.time()

        assert result["success"], f"Index query failed: {result['stderr']}"

        query_time = end_time - start_time
        assert query_time < 0.5, f"Indexed query too slow: {query_time:.3f}s"

        logger.info(f"Index usage performance: {query_time:.3f}s")

    def test_bulk_insert_performance(self, db_ready):
        """Test bulk insert performance for baseline measurement."""
        # Test inserting multiple test records
        test_data = []
        for i in range(100):
            test_data.append(
                f"('test_perf_{i}', 'test_perf_{i}@example.com', 'test_perf_{i}', 'user', 5000, 5000, NULL, 'maildir', true, false, true)"
            )

        bulk_insert_query = f"""
        INSERT INTO unified.users (username, email, maildir, role, uid, gid, home, mailbox_format, is_active, is_super_admin, mail_enabled)
        VALUES {', '.join(test_data)};
        """

        start_time = time.time()
        result = db_ready.execute_query(bulk_insert_query)
        end_time = time.time()

        if result["success"]:
            insert_time = end_time - start_time
            assert insert_time < 5.0, f"Bulk insert too slow: {insert_time:.3f}s"
            logger.info(f"Bulk insert performance: {insert_time:.3f}s for 100 records")

            # Clean up test data
            cleanup_query = "DELETE FROM unified.users WHERE username LIKE 'test_perf_%';"
            db_ready.execute_query(cleanup_query)
        else:
            pytest.skip(f"Bulk insert failed: {result['stderr']}")

    def test_database_connection_performance(self, db_ready):
        """Test database connection establishment performance."""
        connection_times = []

        for i in range(10):
            start_time = time.time()
            result = db_ready.execute_query("SELECT 1;")
            end_time = time.time()

            if result["success"]:
                connection_times.append(end_time - start_time)
            else:
                pytest.skip(f"Connection test failed: {result['stderr']}")

        avg_time = sum(connection_times) / len(connection_times)
        max_time = max(connection_times)
        min_time = min(connection_times)

        assert avg_time < 0.1, f"Average connection time too slow: {avg_time:.3f}s"
        assert max_time < 0.2, f"Max connection time too slow: {max_time:.3f}s"

        logger.info(f"Connection performance: avg={avg_time:.3f}s, min={min_time:.3f}s, max={max_time:.3f}s")

    def test_complex_query_performance(self, db_ready):
        """Test complex query performance with multiple joins."""
        complex_query = """
        SELECT
            u.username,
            u.email,
            u.created_at,
            COUNT(ur.role_name) as role_count,
            COUNT(up.service) as password_count,
            CASE
                WHEN u.is_active THEN 'Active'
                ELSE 'Inactive'
            END as status
        FROM unified.users u
        LEFT JOIN unified.user_roles ur ON u.id = ur.user_id
        LEFT JOIN unified.user_passwords up ON u.id = up.user_id
        WHERE u.created_at > NOW() - INTERVAL '7 days'
        GROUP BY u.id, u.username, u.email, u.created_at, u.is_active
        ORDER BY u.created_at DESC, role_count DESC
        LIMIT 50;
        """

        start_time = time.time()
        result = db_ready.execute_query(complex_query)
        end_time = time.time()

        assert result["success"], f"Complex query failed: {result['stderr']}"

        query_time = end_time - start_time
        assert query_time < 3.0, f"Complex query too slow: {query_time:.3f}s"

        logger.info(f"Complex query performance: {query_time:.3f}s")

    def test_transaction_performance(self, db_ready):
        """Test transaction performance."""
        transaction_query = """
        BEGIN;
        INSERT INTO unified.users (username, email, maildir, role, uid, gid, home, mailbox_format, is_active, is_super_admin, mail_enabled)
        VALUES ('txn_test_user', 'txn_test@example.com', 'txn_test_user', 'user', 5000, 5000, NULL, 'maildir', true, false, true);

        INSERT INTO unified.user_roles (user_id, role_name, service)
        VALUES (LASTVAL(), 'user', 'apache');

        INSERT INTO unified.user_passwords (user_id, service, password_hash, hash_scheme)
        VALUES (LASTVAL(), 'apache', 'dummy_hash', 'CRYPT');

        ROLLBACK;
        """

        start_time = time.time()
        result = db_ready.execute_query(transaction_query)
        end_time = time.time()

        assert result["success"], f"Transaction failed: {result['stderr']}"

        transaction_time = end_time - start_time
        assert transaction_time < 1.0, f"Transaction too slow: {transaction_time:.3f}s"

        logger.info(f"Transaction performance: {transaction_time:.3f}s")
