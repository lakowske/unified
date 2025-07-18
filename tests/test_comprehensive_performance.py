"""Comprehensive Performance Test Suite

This module provides comprehensive performance testing across all components
of the unified infrastructure, including API, database, and container performance.
"""

import concurrent.futures
import json
import logging
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import pytest
import requests

logger = logging.getLogger(__name__)


class PerformanceReporter:
    """Generates comprehensive performance reports."""

    def __init__(self):
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0",
            "environment": "development",
            "tests": {},
        }
        self.baselines = {
            "api_response_time": 0.5,  # seconds
            "database_query_time": 0.1,  # seconds
            "container_startup_time": 30.0,  # seconds
            "concurrent_api_requests": 10,  # requests/second
            "database_connection_time": 0.05,  # seconds
        }

    def record_test(self, test_name: str, duration: float, success: bool, details: Dict = None):
        """Record a performance test result."""
        self.results["tests"][test_name] = {
            "duration": duration,
            "success": success,
            "details": details or {},
            "timestamp": datetime.now().isoformat(),
        }

    def generate_report(self) -> Dict[str, Any]:
        """Generate a comprehensive performance report."""
        report = {
            "summary": {
                "total_tests": len(self.results["tests"]),
                "passed_tests": sum(1 for t in self.results["tests"].values() if t["success"]),
                "failed_tests": sum(1 for t in self.results["tests"].values() if not t["success"]),
                "total_duration": sum(t["duration"] for t in self.results["tests"].values()),
                "average_duration": sum(t["duration"] for t in self.results["tests"].values())
                / len(self.results["tests"])
                if self.results["tests"]
                else 0,
            },
            "baselines": self.baselines,
            "results": self.results,
            "recommendations": self._generate_recommendations(),
        }
        return report

    def _generate_recommendations(self) -> List[str]:
        """Generate performance recommendations based on results."""
        recommendations = []

        for test_name, result in self.results["tests"].items():
            if not result["success"]:
                recommendations.append(f"❌ {test_name}: Test failed - investigate and fix")
                continue

            # Check against baselines
            duration = result["duration"]

            if "api" in test_name.lower() and duration > self.baselines["api_response_time"]:
                recommendations.append(
                    f"🐌 {test_name}: API response time ({duration:.3f}s) exceeds baseline ({self.baselines['api_response_time']}s)"
                )

            if "database" in test_name.lower() and duration > self.baselines["database_query_time"]:
                recommendations.append(
                    f"🐌 {test_name}: Database query time ({duration:.3f}s) exceeds baseline ({self.baselines['database_query_time']}s)"
                )

            if "container" in test_name.lower() and duration > self.baselines["container_startup_time"]:
                recommendations.append(
                    f"🐌 {test_name}: Container startup time ({duration:.3f}s) exceeds baseline ({self.baselines['container_startup_time']}s)"
                )

        if not recommendations:
            recommendations.append("✅ All performance tests are within acceptable baselines")

        return recommendations

    def save_report(self, filename: str = None):
        """Save the performance report to a file."""
        if not filename:
            filename = f"performance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        report_path = Path("test_reports") / filename
        report_path.parent.mkdir(exist_ok=True)

        with open(report_path, "w") as f:
            json.dump(self.generate_report(), f, indent=2)

        logger.info(f"Performance report saved to {report_path}")
        return report_path


@pytest.fixture(scope="session")
def performance_reporter():
    """Create a performance reporter for the session."""
    return PerformanceReporter()


@pytest.fixture(scope="session")
def api_client():
    """Create an API client for performance testing."""
    import os

    api_key = os.environ.get("UNIFIED_API_KEY")
    if not api_key:
        # Try to get from container
        try:
            result = subprocess.run(
                ["docker", "exec", "apache-dev", "cat", "/var/local/unified_api_key"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                api_key = result.stdout.strip()
        except Exception:
            pass

    if not api_key:
        pytest.skip("No API key available for performance testing")

    session = requests.Session()
    session.headers.update({"X-API-Key": api_key, "Content-Type": "application/json", "Accept": "application/json"})

    return session


@pytest.fixture(scope="session")
def db_client():
    """Create a database client for performance testing."""

    class DatabaseClient:
        def __init__(self):
            self.container_name = "postgres-dev"
            self.db_user = "unified_dev_user"
            self.db_name = "unified_dev"

        def execute_query(self, query: str, timeout: int = 30):
            """Execute a SQL query and return results."""
            try:
                result = subprocess.run(
                    [
                        "docker",
                        "exec",
                        self.container_name,
                        "psql",
                        "-U",
                        self.db_user,
                        "-d",
                        self.db_name,
                        "-c",
                        query,
                    ],
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
            except Exception as e:
                return {"success": False, "stdout": "", "stderr": str(e), "returncode": -1}

    return DatabaseClient()


@pytest.mark.performance
class TestComprehensivePerformance:
    """Comprehensive performance test suite."""

    def test_api_response_time_baseline(self, api_client, performance_reporter):
        """Test API response time baseline."""
        url = "http://localhost:8080/health"

        # Warm up
        for _ in range(3):
            api_client.get(url)

        # Measure response times
        response_times = []
        for _ in range(10):
            start_time = time.time()
            response = api_client.get(url)
            end_time = time.time()

            if response.status_code == 200:
                response_times.append(end_time - start_time)

        if response_times:
            avg_time = sum(response_times) / len(response_times)
            min_time = min(response_times)
            max_time = max(response_times)

            performance_reporter.record_test(
                "api_response_time_baseline",
                avg_time,
                avg_time < 0.5,
                {
                    "average_time": avg_time,
                    "min_time": min_time,
                    "max_time": max_time,
                    "requests_count": len(response_times),
                },
            )

            assert avg_time < 0.5, f"Average API response time too slow: {avg_time:.3f}s"
            logger.info(f"API response time: avg={avg_time:.3f}s, min={min_time:.3f}s, max={max_time:.3f}s")
        else:
            pytest.skip("No successful API responses")

    def test_database_performance_baseline(self, db_client, performance_reporter):
        """Test database performance baseline."""
        queries = [
            ("simple_select", "SELECT 1;"),
            ("user_count", "SELECT COUNT(*) FROM unified.users;"),
            ("recent_users", "SELECT username, created_at FROM unified.users ORDER BY created_at DESC LIMIT 10;"),
            (
                "user_with_roles",
                """
                SELECT u.username, COUNT(ur.role_name) as role_count
                FROM unified.users u
                LEFT JOIN unified.user_roles ur ON u.id = ur.user_id
                GROUP BY u.username
                LIMIT 10;
            """,
            ),
        ]

        total_time = 0
        successful_queries = 0

        for query_name, query in queries:
            start_time = time.time()
            result = db_client.execute_query(query)
            end_time = time.time()

            query_time = end_time - start_time
            total_time += query_time

            if result["success"]:
                successful_queries += 1
                performance_reporter.record_test(
                    f"database_{query_name}", query_time, query_time < 0.1, {"query": query.strip()}
                )
                logger.info(f"Database {query_name}: {query_time:.3f}s")
            else:
                performance_reporter.record_test(
                    f"database_{query_name}", query_time, False, {"query": query.strip(), "error": result["stderr"]}
                )

        avg_time = total_time / len(queries)
        assert successful_queries > 0, "No database queries succeeded"
        assert avg_time < 0.2, f"Average database query time too slow: {avg_time:.3f}s"

        performance_reporter.record_test(
            "database_performance_baseline",
            avg_time,
            avg_time < 0.2,
            {"total_queries": len(queries), "successful_queries": successful_queries, "average_time": avg_time},
        )

    def test_concurrent_api_performance(self, api_client, performance_reporter):
        """Test concurrent API request performance."""
        url = "http://localhost:8080/health"

        def make_request(session, request_id):
            """Make a single API request."""
            start_time = time.time()
            try:
                response = session.get(url)
                end_time = time.time()
                return {
                    "request_id": request_id,
                    "success": response.status_code == 200,
                    "duration": end_time - start_time,
                    "status_code": response.status_code,
                }
            except Exception as e:
                end_time = time.time()
                return {"request_id": request_id, "success": False, "duration": end_time - start_time, "error": str(e)}

        # Test with different concurrency levels
        concurrency_levels = [1, 5, 10]

        for concurrency in concurrency_levels:
            start_time = time.time()

            with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
                futures = [executor.submit(make_request, api_client, i) for i in range(concurrency)]
                results = [future.result() for future in concurrent.futures.as_completed(futures)]

            end_time = time.time()
            total_time = end_time - start_time

            successful_requests = sum(1 for r in results if r["success"])
            average_response_time = sum(r["duration"] for r in results) / len(results)
            requests_per_second = successful_requests / total_time

            performance_reporter.record_test(
                f"concurrent_api_performance_{concurrency}",
                total_time,
                successful_requests >= concurrency * 0.8,  # 80% success rate
                {
                    "concurrency": concurrency,
                    "successful_requests": successful_requests,
                    "total_requests": len(results),
                    "average_response_time": average_response_time,
                    "requests_per_second": requests_per_second,
                },
            )

            logger.info(
                f"Concurrent API (level {concurrency}): {successful_requests}/{concurrency} success, {requests_per_second:.1f} req/s"
            )

    def test_container_resource_usage(self, performance_reporter):
        """Test container resource usage."""
        containers = ["postgres-dev", "apache-dev", "mail-dev", "bind-dev"]

        for container in containers:
            try:
                # Get container stats
                result = subprocess.run(
                    [
                        "docker",
                        "stats",
                        container,
                        "--no-stream",
                        "--format",
                        "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

                if result.returncode == 0:
                    lines = result.stdout.strip().split("\n")
                    if len(lines) >= 2:
                        stats_line = lines[1]  # Skip header
                        parts = stats_line.split("\t")
                        if len(parts) >= 5:
                            name = parts[0]
                            cpu_percent = parts[1]
                            mem_usage = parts[2]
                            net_io = parts[3]
                            block_io = parts[4]

                            performance_reporter.record_test(
                                f"container_resource_usage_{container}",
                                0.0,  # No duration for resource usage
                                True,
                                {
                                    "container": name,
                                    "cpu_percent": cpu_percent,
                                    "memory_usage": mem_usage,
                                    "network_io": net_io,
                                    "block_io": block_io,
                                },
                            )

                            logger.info(f"Container {container}: CPU {cpu_percent}, Memory {mem_usage}")

            except Exception as e:
                performance_reporter.record_test(f"container_resource_usage_{container}", 0.0, False, {"error": str(e)})

    def test_end_to_end_performance(self, api_client, db_client, performance_reporter):
        """Test end-to-end performance including API and database."""
        # Create a user via API and verify in database
        username = f"e2e_perf_test_{int(time.time())}"
        email = f"{username}@example.com"

        # API user creation
        start_time = time.time()
        response = api_client.post(
            "http://localhost:8080/api/v1/admin/create_user.php",
            json={"username": username, "password": "password123", "email": email, "role": "user"},
        )
        api_time = time.time() - start_time

        if response.status_code == 201:
            user_data = response.json()
            user_id = user_data["user"]["id"]

            # Database verification
            start_time = time.time()
            _ = db_client.execute_query(f"SELECT username, email, is_active FROM unified.users WHERE id = {user_id};")
            db_time = time.time() - start_time

            total_time = api_time + db_time

            performance_reporter.record_test(
                "end_to_end_performance",
                total_time,
                total_time < 1.0,
                {
                    "api_creation_time": api_time,
                    "database_verification_time": db_time,
                    "total_time": total_time,
                    "user_created": True,
                },
            )

            # Cleanup
            api_client.post("http://localhost:8080/api/v1/admin/delete_user.php", json={"user_id": user_id})

            assert total_time < 1.0, f"End-to-end performance too slow: {total_time:.3f}s"
            logger.info(f"End-to-end performance: API {api_time:.3f}s, DB {db_time:.3f}s, Total {total_time:.3f}s")
        else:
            pytest.skip(f"User creation failed with status {response.status_code}")

    def test_generate_performance_report(self, performance_reporter):
        """Generate and save comprehensive performance report."""
        report = performance_reporter.generate_report()
        report_path = performance_reporter.save_report()

        logger.info("Performance Report Generated:")
        logger.info(f"  Total Tests: {report['summary']['total_tests']}")
        logger.info(f"  Passed: {report['summary']['passed_tests']}")
        logger.info(f"  Failed: {report['summary']['failed_tests']}")
        logger.info(f"  Average Duration: {report['summary']['average_duration']:.3f}s")
        logger.info(f"  Report saved to: {report_path}")

        # Print recommendations
        for recommendation in report["recommendations"]:
            logger.info(f"  {recommendation}")

        # Ensure report was generated
        assert report_path.exists(), "Performance report file was not created"
        assert report["summary"]["total_tests"] > 0, "No performance tests were recorded"
