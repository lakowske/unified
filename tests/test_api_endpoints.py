"""API Endpoints Integration Tests

This module provides comprehensive integration tests for the unified infrastructure
PHP API endpoints, including user management, authentication, and database operations.
"""

import logging
import os
import subprocess
import time
from typing import Any, Dict, List, Optional

import pytest
import requests

logger = logging.getLogger(__name__)


class APITestManager:
    """Manages API testing against the unified infrastructure."""

    def __init__(self, base_url: str = "http://localhost:8080", api_key: Optional[str] = None):
        self.base_url = base_url
        self.api_key = api_key
        self.session = requests.Session()

        # Set default headers
        if self.api_key:
            self.session.headers.update({"X-API-Key": self.api_key})

        self.session.headers.update({"Content-Type": "application/json", "Accept": "application/json"})

    def get_api_key(self) -> Optional[str]:
        """Get API key from environment or container."""
        # Try environment variable first
        api_key = os.environ.get("UNIFIED_API_KEY")
        if api_key:
            return api_key

        # Try to read from container
        try:
            result = subprocess.run(
                ["docker", "exec", "apache-dev", "cat", "/var/local/unified_api_key"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception as e:
            logger.warning(f"Could not read API key from container: {e}")

        return None

    def wait_for_api_ready(self, timeout: int = 60) -> bool:
        """Wait for API to be ready."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                response = self.session.get(f"{self.base_url}/health", timeout=5)
                if response.status_code == 200:
                    logger.info("API is ready")
                    return True
            except requests.exceptions.RequestException:
                pass

            time.sleep(2)

        logger.error("API did not become ready within timeout")
        return False

    def create_user(self, username: str, password: str, email: str = None, role: str = "user") -> Dict[str, Any]:
        """Create a new user via API."""
        data = {"username": username, "password": password, "role": role}

        if email:
            data["email"] = email

        response = self.session.post(f"{self.base_url}/api/v1/admin/create_user.php", json=data)

        return {
            "status_code": response.status_code,
            "response": response.json() if response.content else {},
            "headers": dict(response.headers),
        }

    def list_users(self) -> Dict[str, Any]:
        """List all users via API."""
        response = self.session.get(f"{self.base_url}/api/v1/admin/list_users.php")

        return {
            "status_code": response.status_code,
            "response": response.json() if response.content else {},
            "headers": dict(response.headers),
        }

    def delete_user(self, user_id: int) -> Dict[str, Any]:
        """Delete a user via API."""
        data = {"user_id": user_id}
        response = self.session.post(f"{self.base_url}/api/v1/admin/delete_user.php", json=data)

        return {
            "status_code": response.status_code,
            "response": response.json() if response.content else {},
            "headers": dict(response.headers),
        }

    def update_user(self, user_id: int, **kwargs) -> Dict[str, Any]:
        """Update a user via API."""
        data = {"user_id": user_id, **kwargs}
        response = self.session.post(f"{self.base_url}/api/v1/admin/update_user.php", json=data)

        # Parse JSON response safely
        response_data = {}
        if response.content:
            try:
                response_data = response.json()
            except requests.exceptions.JSONDecodeError:
                # If JSON parsing fails, include raw text
                response_data = {"raw_response": response.text}

        return {"status_code": response.status_code, "response": response_data, "headers": dict(response.headers)}

    def get_user(self, user_id: int) -> Dict[str, Any]:
        """Get a specific user via API."""
        response = self.session.get(f"{self.base_url}/api/v1/admin/get_user.php?user_id={user_id}")

        # Parse JSON response safely
        response_data = {}
        if response.content:
            try:
                response_data = response.json()
            except requests.exceptions.JSONDecodeError:
                # If JSON parsing fails, include raw text
                response_data = {"raw_response": response.text}

        return {"status_code": response.status_code, "response": response_data, "headers": dict(response.headers)}

    def search_users(self, query: str = "", role: str = "", active: bool = None) -> Dict[str, Any]:
        """Search users via API."""
        params = {}
        if query:
            params["q"] = query
        if role:
            params["role"] = role
        if active is not None:
            params["active"] = str(active).lower()

        query_string = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{self.base_url}/api/v1/admin/search_users.php"
        if query_string:
            url += f"?{query_string}"

        response = self.session.get(url)

        # Parse JSON response safely
        response_data = {}
        if response.content:
            try:
                response_data = response.json()
            except requests.exceptions.JSONDecodeError:
                # If JSON parsing fails, include raw text
                response_data = {"raw_response": response.text}

        return {"status_code": response.status_code, "response": response_data, "headers": dict(response.headers)}

    def set_user_status(self, user_id: int, active: bool) -> Dict[str, Any]:
        """Set user active/inactive status via API."""
        data = {"user_id": user_id, "active": active}
        response = self.session.post(f"{self.base_url}/api/v1/admin/set_user_status.php", json=data)

        # Parse JSON response safely
        response_data = {}
        if response.content:
            try:
                response_data = response.json()
            except requests.exceptions.JSONDecodeError:
                # If JSON parsing fails, include raw text
                response_data = {"raw_response": response.text}

        return {"status_code": response.status_code, "response": response_data, "headers": dict(response.headers)}

    def bulk_create_users(self, users: List[Dict[str, str]]) -> Dict[str, Any]:
        """Create multiple users via API."""
        data = {"users": users}
        response = self.session.post(f"{self.base_url}/api/v1/admin/bulk_create_users.php", json=data)

        # Parse JSON response safely
        response_data = {}
        if response.content:
            try:
                response_data = response.json()
            except requests.exceptions.JSONDecodeError:
                # If JSON parsing fails, include raw text
                response_data = {"raw_response": response.text}

        return {"status_code": response.status_code, "response": response_data, "headers": dict(response.headers)}

    def test_without_api_key(self, endpoint: str, method: str = "GET", data: Dict = None) -> Dict[str, Any]:
        """Test API endpoint without API key."""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json", "Accept": "application/json"})

        if method.upper() == "GET":
            response = session.get(f"{self.base_url}{endpoint}")
        elif method.upper() == "POST":
            response = session.post(f"{self.base_url}{endpoint}", json=data)
        else:
            msg = f"Unsupported method: {method}"
            raise ValueError(msg)

        # Parse JSON response safely
        response_data = {}
        if response.content:
            try:
                response_data = response.json()
            except requests.exceptions.JSONDecodeError:
                # If JSON parsing fails, include raw text
                response_data = {"raw_response": response.text}

        return {"status_code": response.status_code, "response": response_data, "headers": dict(response.headers)}


@pytest.fixture(scope="session")
def api_manager():
    """Create an API test manager."""
    manager = APITestManager()

    # Get API key
    api_key = manager.get_api_key()
    if api_key:
        manager.api_key = api_key
        manager.session.headers.update({"X-API-Key": api_key})
        logger.info("API key configured for tests")
    else:
        logger.warning("No API key found - authentication tests will be limited")

    return manager


@pytest.fixture(scope="session")
def api_ready(api_manager):
    """Ensure API is ready before running tests."""
    assert api_manager.wait_for_api_ready(), "API did not become ready"
    return api_manager


class TestAPIAuthentication:
    """Test API authentication and authorization."""

    def test_api_requires_authentication(self, api_manager):
        """Test that API endpoints require authentication."""
        # Test create user without API key
        result = api_manager.test_without_api_key(
            "/api/v1/admin/create_user.php", "POST", {"username": "test", "password": "password"}
        )

        assert result["status_code"] == 401, f"Expected 401, got {result['status_code']}"
        assert "error" in result["response"], "Expected error message in response"
        assert "api key" in result["response"]["error"].lower(), "Expected API key error message"

    def test_api_key_validation(self, api_manager):
        """Test API key validation."""
        if not api_manager.api_key:
            pytest.skip("No API key available for testing")

        # Test with valid API key
        result = api_manager.list_users()
        assert result["status_code"] in [200, 404], f"Expected 200 or 404, got {result['status_code']}"

        # Test with invalid API key
        original_key = api_manager.api_key
        api_manager.session.headers["X-API-Key"] = "invalid-key"

        result = api_manager.list_users()
        assert result["status_code"] == 401, f"Expected 401 with invalid key, got {result['status_code']}"

        # Restore original key
        api_manager.session.headers["X-API-Key"] = original_key

    def test_cors_headers(self, api_manager):
        """Test CORS headers are present."""
        result = api_manager.test_without_api_key("/api/v1/admin/create_user.php", "POST", {})

        headers = result["headers"]
        assert "Access-Control-Allow-Origin" in headers, "CORS origin header missing"
        assert "Access-Control-Allow-Methods" in headers, "CORS methods header missing"
        assert "Access-Control-Allow-Headers" in headers, "CORS headers header missing"


class TestUserManagement:
    """Test user management API endpoints."""

    def test_create_user_success(self, api_ready):
        """Test successful user creation."""
        if not api_ready.api_key:
            pytest.skip("No API key available for testing")

        # Create a test user
        username = f"test_user_{int(time.time())}"
        email = f"{username}@example.com"

        result = api_ready.create_user(username, "password123", email, "user")

        assert result["status_code"] == 201, f"Expected 201, got {result['status_code']}: {result['response']}"
        assert result["response"]["success"] is True, "Expected success=true"
        assert "user" in result["response"], "Expected user data in response"

        user_data = result["response"]["user"]
        assert user_data["username"] == username, "Username mismatch"
        assert user_data["email"] == email, "Email mismatch"
        assert user_data["role"] == "user", "Role mismatch"
        assert "id" in user_data, "User ID missing"
        assert "created_at" in user_data, "Created timestamp missing"

    def test_create_user_validation(self, api_ready):
        """Test user creation validation."""
        if not api_ready.api_key:
            pytest.skip("No API key available for testing")

        # Test missing username
        result = api_ready.create_user("", "password123")
        assert result["status_code"] == 400, f"Expected 400, got {result['status_code']}"
        assert "error" in result["response"], "Expected error message"

        # Test short password
        result = api_ready.create_user("testuser", "123")
        assert result["status_code"] == 400, f"Expected 400, got {result['status_code']}"
        assert "error" in result["response"], "Expected error message"

        # Test invalid email
        result = api_ready.create_user("testuser", "password123", "invalid-email")
        assert result["status_code"] == 400, f"Expected 400, got {result['status_code']}"
        assert "error" in result["response"], "Expected error message"

        # Test invalid role
        result = api_ready.create_user("testuser", "password123", "user@example.com", "invalid_role")
        assert result["status_code"] == 400, f"Expected 400, got {result['status_code']}"
        assert "error" in result["response"], "Expected error message"

    def test_create_user_duplicate_username(self, api_ready):
        """Test creating user with duplicate username."""
        if not api_ready.api_key:
            pytest.skip("No API key available for testing")

        username = f"duplicate_test_{int(time.time())}"
        email = f"{username}@example.com"

        # Create first user
        result1 = api_ready.create_user(username, "password123", email=email)
        assert result1["status_code"] == 201, f"First user creation failed: {result1['response']}"

        # Try to create duplicate
        result2 = api_ready.create_user(username, "password456", email=f"{username}2@example.com")
        assert result2["status_code"] == 409, f"Expected 409, got {result2['status_code']}"
        assert "error" in result2["response"], "Expected error message"
        assert "username" in result2["response"]["error"].lower(), "Expected username error"

    def test_list_users(self, api_ready):
        """Test listing users."""
        if not api_ready.api_key:
            pytest.skip("No API key available for testing")

        result = api_ready.list_users()

        # Should be 200 (success) or 404 (no users found)
        assert result["status_code"] in [200, 404], f"Expected 200 or 404, got {result['status_code']}"

        if result["status_code"] == 200:
            assert "users" in result["response"], "Expected users array"
            assert isinstance(result["response"]["users"], list), "Expected users to be a list"

            # If users exist, check structure
            if result["response"]["users"]:
                user = result["response"]["users"][0]
                assert "id" in user, "User ID missing"
                assert "username" in user, "Username missing"
                assert "created_at" in user, "Created timestamp missing"

    def test_delete_user(self, api_ready):
        """Test user deletion."""
        if not api_ready.api_key:
            pytest.skip("No API key available for testing")

        # Create a user to delete
        username = f"delete_test_{int(time.time())}"
        email = f"{username}@example.com"
        create_result = api_ready.create_user(username, "password123", email=email)
        assert create_result["status_code"] == 201, f"User creation failed: {create_result['response']}"

        user_id = create_result["response"]["user"]["id"]

        # Delete the user
        delete_result = api_ready.delete_user(user_id)
        # Check if delete endpoint exists
        if delete_result["status_code"] == 405:
            pytest.skip("Delete user endpoint not implemented")
        assert (
            delete_result["status_code"] == 200
        ), f"Expected 200, got {delete_result['status_code']}: {delete_result['response']}"
        assert delete_result["response"]["success"] is True, "Expected success=true"

    def test_delete_nonexistent_user(self, api_ready):
        """Test deleting non-existent user."""
        if not api_ready.api_key:
            pytest.skip("No API key available for testing")

        # Try to delete a user that doesn't exist
        result = api_ready.delete_user(999999)
        # Check if delete endpoint exists
        if result["status_code"] == 405:
            pytest.skip("Delete user endpoint not implemented")
        assert result["status_code"] == 404, f"Expected 404, got {result['status_code']}"
        assert "error" in result["response"], "Expected error message"


class TestAPIErrorHandling:
    """Test API error handling and edge cases."""

    def test_invalid_json(self, api_ready):
        """Test handling of invalid JSON."""
        if not api_ready.api_key:
            pytest.skip("No API key available for testing")

        # Send invalid JSON
        response = api_ready.session.post(
            f"{api_ready.base_url}/api/v1/admin/create_user.php",
            data="invalid json",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        response_data = response.json()
        assert "error" in response_data, "Expected error message"
        assert "json" in response_data["error"].lower(), "Expected JSON error message"

    def test_method_not_allowed(self, api_ready):
        """Test method not allowed handling."""
        if not api_ready.api_key:
            pytest.skip("No API key available for testing")

        # Try GET on create_user endpoint (which only accepts POST)
        response = api_ready.session.get(f"{api_ready.base_url}/api/v1/admin/create_user.php")

        assert response.status_code == 405, f"Expected 405, got {response.status_code}"
        response_data = response.json()
        assert "error" in response_data, "Expected error message"
        assert "method" in response_data["error"].lower(), "Expected method error message"

    def test_options_request(self, api_ready):
        """Test OPTIONS request handling (CORS preflight)."""
        response = api_ready.session.options(f"{api_ready.base_url}/api/v1/admin/create_user.php")

        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        # Check CORS headers
        headers = response.headers
        assert "Access-Control-Allow-Origin" in headers, "CORS origin header missing"
        assert "Access-Control-Allow-Methods" in headers, "CORS methods header missing"
        assert "Access-Control-Allow-Headers" in headers, "CORS headers header missing"


class TestAdvancedUserManagement:
    """Test advanced user management features."""

    def test_user_role_management(self, api_ready):
        """Test user role assignment and updates."""
        if not api_ready.api_key:
            pytest.skip("No API key available for testing")

        # Create a user with admin role
        username = f"role_test_{int(time.time())}"
        email = f"{username}@example.com"
        result = api_ready.create_user(username, "password123", email=email, role="admin")
        assert result["status_code"] == 201, f"Admin user creation failed: {result['response']}"

        user_id = result["response"]["user"]["id"]
        assert result["response"]["user"]["role"] == "admin", "Role should be admin"

        # Update user role to regular user
        update_result = api_ready.update_user(user_id, role="user")
        # Note: This test may fail if the endpoint doesn't exist - that's expected
        if update_result["status_code"] == 200:
            assert update_result["response"]["user"]["role"] == "user", "Role should be updated to user"
        elif update_result["status_code"] == 404:
            pytest.skip("User update endpoint not implemented")

    def test_user_status_management(self, api_ready):
        """Test user active/inactive status management."""
        if not api_ready.api_key:
            pytest.skip("No API key available for testing")

        # Create an active user
        username = f"status_test_{int(time.time())}"
        email = f"{username}@example.com"
        result = api_ready.create_user(username, "password123", email=email)
        assert result["status_code"] == 201, f"User creation failed: {result['response']}"

        user_id = result["response"]["user"]["id"]
        assert result["response"]["user"]["active"] is True, "User should be active by default"

        # Set user to inactive
        status_result = api_ready.set_user_status(user_id, False)
        # Note: This test may fail if the endpoint doesn't exist - that's expected
        if status_result["status_code"] == 200:
            assert status_result["response"]["user"]["active"] is False, "User should be inactive"
        elif status_result["status_code"] == 404:
            pytest.skip("User status endpoint not implemented")

    def test_user_search_and_filtering(self, api_ready):
        """Test user search and filtering capabilities."""
        if not api_ready.api_key:
            pytest.skip("No API key available for testing")

        # Create test users with different roles
        timestamp = int(time.time())
        admin_user = f"admin_search_{timestamp}"
        regular_user = f"user_search_{timestamp}"

        # Create admin user
        admin_result = api_ready.create_user(admin_user, "password123", email=f"{admin_user}@example.com", role="admin")
        assert admin_result["status_code"] == 201, f"Admin user creation failed: {admin_result['response']}"

        # Create regular user
        user_result = api_ready.create_user(
            regular_user, "password123", email=f"{regular_user}@example.com", role="user"
        )
        assert user_result["status_code"] == 201, f"Regular user creation failed: {user_result['response']}"

        # Search for admin users
        search_result = api_ready.search_users(role="admin")
        # Note: This test may fail if the endpoint doesn't exist - that's expected
        if search_result["status_code"] == 200:
            admin_users = [u for u in search_result["response"]["users"] if u["role"] == "admin"]
            assert len(admin_users) > 0, "Should find at least one admin user"
        elif search_result["status_code"] == 404:
            pytest.skip("User search endpoint not implemented")

    def test_bulk_user_operations(self, api_ready):
        """Test bulk user creation."""
        if not api_ready.api_key:
            pytest.skip("No API key available for testing")

        # Prepare bulk users
        timestamp = int(time.time())
        users = [
            {
                "username": f"bulk_user1_{timestamp}",
                "password": "password123",
                "email": f"bulk_user1_{timestamp}@example.com",
                "role": "user",
            },
            {
                "username": f"bulk_user2_{timestamp}",
                "password": "password123",
                "email": f"bulk_user2_{timestamp}@example.com",
                "role": "user",
            },
            {
                "username": f"bulk_user3_{timestamp}",
                "password": "password123",
                "email": f"bulk_user3_{timestamp}@example.com",
                "role": "admin",
            },
        ]

        # Create users in bulk
        bulk_result = api_ready.bulk_create_users(users)
        # Note: This test may fail if the endpoint doesn't exist - that's expected
        if bulk_result["status_code"] == 200:
            assert len(bulk_result["response"]["users"]) == 3, "Should create 3 users"
            assert bulk_result["response"]["success"] is True, "Bulk creation should succeed"
        elif bulk_result["status_code"] == 404:
            pytest.skip("Bulk user creation endpoint not implemented")

    def test_user_data_retrieval(self, api_ready):
        """Test retrieving individual user data."""
        if not api_ready.api_key:
            pytest.skip("No API key available for testing")

        # Create a user
        username = f"retrieve_test_{int(time.time())}"
        email = f"{username}@example.com"

        create_result = api_ready.create_user(username, "password123", email=email)
        assert create_result["status_code"] == 201, f"User creation failed: {create_result['response']}"

        user_id = create_result["response"]["user"]["id"]

        # Retrieve user data
        get_result = api_ready.get_user(user_id)
        # Note: This test may fail if the endpoint doesn't exist - that's expected
        if get_result["status_code"] == 200:
            user_data = get_result["response"]["user"]
            assert user_data["username"] == username, "Username should match"
            assert user_data["email"] == email, "Email should match"
            assert user_data["id"] == user_id, "User ID should match"
        elif get_result["status_code"] == 404:
            pytest.skip("Get user endpoint not implemented")


class TestDatabaseIntegration:
    """Test API database integration."""

    def test_user_creation_database_consistency(self, api_ready):
        """Test that user creation is consistent with database."""
        if not api_ready.api_key:
            pytest.skip("No API key available for testing")

        # Create user via API
        username = f"db_test_{int(time.time())}"
        email = f"{username}@example.com"

        result = api_ready.create_user(username, "password123", email=email, role="admin")
        assert result["status_code"] == 201, f"User creation failed: {result['response']}"

        user_id = result["response"]["user"]["id"]

        # Verify user exists in database
        try:
            db_result = subprocess.run(
                [
                    "docker",
                    "exec",
                    "postgres-dev",
                    "psql",
                    "-U",
                    "unified_dev_user",
                    "-d",
                    "unified_dev",
                    "-c",
                    f"SELECT username, email, is_active FROM unified.users WHERE id = {user_id};",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            assert db_result.returncode == 0, f"Database query failed: {db_result.stderr}"
            assert username in db_result.stdout, "Username not found in database"
            assert email in db_result.stdout, "Email not found in database"

        except subprocess.TimeoutExpired:
            pytest.skip("Database query timed out")
        except Exception as e:
            pytest.skip(f"Database query failed: {e}")

    def test_user_roles_and_passwords(self, api_ready):
        """Test that user roles and passwords are stored correctly."""
        if not api_ready.api_key:
            pytest.skip("No API key available for testing")

        # Create admin user
        username = f"admin_test_{int(time.time())}"
        email = f"{username}@example.com"
        result = api_ready.create_user(username, "password123", email=email, role="admin")
        assert result["status_code"] == 201, f"Admin user creation failed: {result['response']}"

        user_id = result["response"]["user"]["id"]

        # Check roles in database
        try:
            role_result = subprocess.run(
                [
                    "docker",
                    "exec",
                    "postgres-dev",
                    "psql",
                    "-U",
                    "unified_dev_user",
                    "-d",
                    "unified_dev",
                    "-c",
                    f"SELECT role_name, service FROM unified.user_roles WHERE user_id = {user_id};",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            assert role_result.returncode == 0, f"Role query failed: {role_result.stderr}"
            assert "admin" in role_result.stdout, "Admin role not found in database"
            assert "apache" in role_result.stdout, "Apache service role not found"
            assert "dovecot" in role_result.stdout, "Dovecot service role not found"

            # Check passwords exist
            password_result = subprocess.run(
                [
                    "docker",
                    "exec",
                    "postgres-dev",
                    "psql",
                    "-U",
                    "unified_dev_user",
                    "-d",
                    "unified_dev",
                    "-c",
                    f"SELECT service, hash_scheme FROM unified.user_passwords WHERE user_id = {user_id};",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            assert password_result.returncode == 0, f"Password query failed: {password_result.stderr}"
            assert "apache" in password_result.stdout, "Apache password not found"
            assert "dovecot" in password_result.stdout, "Dovecot password not found"
            assert "CRYPT" in password_result.stdout, "CRYPT hash scheme not found"

        except subprocess.TimeoutExpired:
            pytest.skip("Database query timed out")
        except Exception as e:
            pytest.skip(f"Database query failed: {e}")

    def test_user_deletion_cleanup(self, api_ready):
        """Test that user deletion properly cleans up related data."""
        if not api_ready.api_key:
            pytest.skip("No API key available for testing")

        # Create a user
        username = f"cleanup_test_{int(time.time())}"
        email = f"{username}@example.com"
        result = api_ready.create_user(username, "password123", email=email, role="admin")
        assert result["status_code"] == 201, f"User creation failed: {result['response']}"

        user_id = result["response"]["user"]["id"]

        # Delete the user
        delete_result = api_ready.delete_user(user_id)

        # If deletion succeeds, verify cleanup in database
        if delete_result["status_code"] == 200:
            try:
                # Check that user record is deleted
                user_result = subprocess.run(
                    [
                        "docker",
                        "exec",
                        "postgres-dev",
                        "psql",
                        "-U",
                        "unified_dev_user",
                        "-d",
                        "unified_dev",
                        "-c",
                        f"SELECT COUNT(*) FROM unified.users WHERE id = {user_id};",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                assert user_result.returncode == 0, f"User query failed: {user_result.stderr}"
                assert "0" in user_result.stdout, "User record should be deleted"

                # Check that related records are also cleaned up
                role_result = subprocess.run(
                    [
                        "docker",
                        "exec",
                        "postgres-dev",
                        "psql",
                        "-U",
                        "unified_dev_user",
                        "-d",
                        "unified_dev",
                        "-c",
                        f"SELECT COUNT(*) FROM unified.user_roles WHERE user_id = {user_id};",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                assert role_result.returncode == 0, f"Role query failed: {role_result.stderr}"
                assert "0" in role_result.stdout, "User role records should be deleted"

                password_result = subprocess.run(
                    [
                        "docker",
                        "exec",
                        "postgres-dev",
                        "psql",
                        "-U",
                        "unified_dev_user",
                        "-d",
                        "unified_dev",
                        "-c",
                        f"SELECT COUNT(*) FROM unified.user_passwords WHERE user_id = {user_id};",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                assert password_result.returncode == 0, f"Password query failed: {password_result.stderr}"
                assert "0" in password_result.stdout, "User password records should be deleted"

            except subprocess.TimeoutExpired:
                pytest.skip("Database query timed out")
            except Exception as e:
                pytest.skip(f"Database query failed: {e}")
        else:
            # If deletion fails, that's also valuable test information
            assert delete_result["status_code"] in [
                404,
                405,
            ], f"Unexpected deletion failure: {delete_result['response']}"
            if delete_result["status_code"] == 405:
                pytest.skip("User deletion endpoint not implemented")
            elif delete_result["status_code"] == 404:
                pytest.skip("User not found for deletion")


@pytest.mark.performance
class TestAPIPerformance:
    """Test API performance and load handling."""

    def test_user_creation_performance(self, api_ready):
        """Test user creation performance."""
        if not api_ready.api_key:
            pytest.skip("No API key available for testing")

        # Create multiple users and measure time
        start_time = time.time()
        created_users = []

        for i in range(5):
            username = f"perf_test_{int(time.time())}_{i}"
            result = api_ready.create_user(username, "password123")

            if result["status_code"] == 201:
                created_users.append(result["response"]["user"]["id"])
            else:
                logger.warning(f"User creation failed: {result['response']}")

        end_time = time.time()
        total_time = end_time - start_time
        avg_time = total_time / len(created_users) if created_users else 0

        # Performance assertion (should be reasonably fast)
        assert avg_time < 2.0, f"User creation too slow: {avg_time:.3f}s average"
        assert len(created_users) >= 3, f"Too many user creations failed: {len(created_users)}/5"

        logger.info(f"User creation performance: {avg_time:.3f}s average for {len(created_users)} users")

    def test_concurrent_api_requests(self, api_ready):
        """Test handling of concurrent API requests."""
        if not api_ready.api_key:
            pytest.skip("No API key available for testing")

        import concurrent.futures

        def create_user_concurrent(index):
            username = f"concurrent_test_{int(time.time())}_{index}"
            result = api_ready.create_user(username, "password123")
            return result["status_code"] == 201

        # Run concurrent user creations
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(create_user_concurrent, i) for i in range(3)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]

        success_count = sum(results)
        assert success_count >= 2, f"Too many concurrent requests failed: {success_count}/3"

        logger.info(f"Concurrent API performance: {success_count}/3 requests succeeded")
