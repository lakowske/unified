#!/usr/bin/env python3
"""DNS Mail Integration Test Runner

This script runs comprehensive DNS and mail integration tests to validate:
- DNS server functionality
- Mail domain record resolution
- SPF, DKIM, DMARC record validation
- DNS-Mail server integration
- Performance testing

Usage:
    python tests/run_dns_mail_tests.py [options]

Options:
    --domain DOMAIN     Mail domain to test (default: lab.sethlakowske.com)
    --server SERVER     DNS server to test (default: localhost)
    --port PORT         DNS port to test (default: 53)
    --verbose           Enable verbose logging
    --performance       Run performance tests
    --integration       Run integration tests
    --report            Generate detailed test report
"""

import argparse
import json
import logging
import os
import sys
import time
from typing import Any, Dict

import pytest

logger = logging.getLogger(__name__)


class DNSMailTestRunner:
    """Test runner for DNS mail integration tests."""

    def __init__(self, domain: str, dns_server: str, dns_port: int):
        self.domain = domain
        self.dns_server = dns_server
        self.dns_port = dns_port
        self.test_results = {}
        self.start_time = None
        self.end_time = None

    def setup_environment(self):
        """Setup environment variables for tests."""
        os.environ["MAIL_DOMAIN"] = self.domain
        os.environ["DNS_SERVER"] = self.dns_server
        os.environ["DNS_PORT"] = str(self.dns_port)

        # Set mail server IP based on DNS resolution
        try:
            import subprocess

            result = subprocess.run(
                ["dig", f"@{self.dns_server}", "-p", str(self.dns_port), self.domain, "A", "+short"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0 and result.stdout.strip():
                mail_ip = result.stdout.strip().split("\n")[0]
                os.environ["MAIL_SERVER_IP"] = mail_ip
                logger.info(f"Set MAIL_SERVER_IP from DNS: {mail_ip}")
            else:
                logger.warning(f"Could not resolve {self.domain} A record, using default IP")
                os.environ["MAIL_SERVER_IP"] = "192.168.0.156"

        except Exception as e:
            logger.warning(f"Error resolving mail server IP: {e}")
            os.environ["MAIL_SERVER_IP"] = "192.168.0.156"

    def run_basic_tests(self) -> Dict[str, Any]:
        """Run basic DNS mail tests."""
        logger.info("Running basic DNS mail tests...")

        pytest_args = [
            "-v",
            "--tb=short",
            "--confcutdir=tests",
            "tests/test_dns_mail_integration.py::TestDNSMailIntegration",
            "-p",
            "no:warnings",
        ]

        result = pytest.main(pytest_args)

        return {"test_type": "basic", "exit_code": result, "passed": result == 0, "timestamp": time.time()}

    def run_advanced_tests(self) -> Dict[str, Any]:
        """Run advanced DNS mail tests."""
        logger.info("Running advanced DNS mail tests...")

        pytest_args = [
            "-v",
            "--tb=short",
            "--confcutdir=tests",
            "tests/test_dns_mail_integration.py::TestDNSMailIntegrationAdvanced",
            "-p",
            "no:warnings",
        ]

        result = pytest.main(pytest_args)

        return {"test_type": "advanced", "exit_code": result, "passed": result == 0, "timestamp": time.time()}

    def run_integration_tests(self) -> Dict[str, Any]:
        """Run live integration tests."""
        logger.info("Running live integration tests...")

        pytest_args = [
            "-v",
            "--tb=short",
            "--confcutdir=tests",
            "tests/test_dns_mail_integration.py::TestDNSMailIntegrationLive",
            "-m",
            "integration",
            "-p",
            "no:warnings",
        ]

        result = pytest.main(pytest_args)

        return {"test_type": "integration", "exit_code": result, "passed": result == 0, "timestamp": time.time()}

    def run_performance_tests(self) -> Dict[str, Any]:
        """Run performance tests."""
        logger.info("Running performance tests...")

        pytest_args = [
            "-v",
            "--tb=short",
            "--confcutdir=tests",
            "tests/test_dns_mail_integration.py::TestDNSMailIntegration::test_dns_performance",
            "-p",
            "no:warnings",
        ]

        result = pytest.main(pytest_args)

        return {"test_type": "performance", "exit_code": result, "passed": result == 0, "timestamp": time.time()}

    def run_all_tests(self, include_integration: bool = False, include_performance: bool = False) -> Dict[str, Any]:
        """Run all DNS mail tests."""
        logger.info("Starting comprehensive DNS mail integration tests...")

        self.start_time = time.time()

        # Run basic tests
        basic_results = self.run_basic_tests()
        self.test_results["basic"] = basic_results

        # Run advanced tests
        advanced_results = self.run_advanced_tests()
        self.test_results["advanced"] = advanced_results

        # Run integration tests if requested
        if include_integration:
            integration_results = self.run_integration_tests()
            self.test_results["integration"] = integration_results

        # Run performance tests if requested
        if include_performance:
            performance_results = self.run_performance_tests()
            self.test_results["performance"] = performance_results

        self.end_time = time.time()

        # Calculate overall results
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result["passed"])

        overall_result = {
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": total_tests - passed_tests,
            "success_rate": (passed_tests / total_tests) * 100 if total_tests > 0 else 0,
            "duration": self.end_time - self.start_time,
            "timestamp": self.end_time,
        }

        self.test_results["overall"] = overall_result

        return self.test_results

    def generate_report(self) -> str:
        """Generate detailed test report."""
        if not self.test_results:
            return "No test results available"

        overall = self.test_results.get("overall", {})

        report = []
        report.append("=" * 60)
        report.append("DNS MAIL INTEGRATION TEST REPORT")
        report.append("=" * 60)
        report.append(f"Domain: {self.domain}")
        report.append(f"DNS Server: {self.dns_server}:{self.dns_port}")
        report.append(f"Test Duration: {overall.get('duration', 0):.2f} seconds")
        report.append(f"Success Rate: {overall.get('success_rate', 0):.1f}%")
        report.append("")

        # Test results summary
        report.append("TEST RESULTS SUMMARY:")
        report.append("-" * 40)

        for test_type, results in self.test_results.items():
            if test_type == "overall":
                continue

            status = "PASSED" if results["passed"] else "FAILED"
            report.append(f"{test_type.upper():<15} {status}")

        report.append("")

        # Detailed results
        report.append("DETAILED RESULTS:")
        report.append("-" * 40)

        for test_type, results in self.test_results.items():
            if test_type == "overall":
                continue

            report.append(f"\n{test_type.upper()} Tests:")
            report.append(f"  Status: {'PASSED' if results['passed'] else 'FAILED'}")
            report.append(f"  Exit Code: {results['exit_code']}")
            report.append(f"  Timestamp: {time.ctime(results['timestamp'])}")

        # Overall summary
        report.append("\nOVERALL SUMMARY:")
        report.append("-" * 40)
        report.append(f"Total Test Suites: {overall.get('total_tests', 0)}")
        report.append(f"Passed: {overall.get('passed_tests', 0)}")
        report.append(f"Failed: {overall.get('failed_tests', 0)}")
        report.append(f"Success Rate: {overall.get('success_rate', 0):.1f}%")

        if overall.get("success_rate", 0) == 100:
            report.append("\n✅ ALL TESTS PASSED - DNS mail integration is working correctly!")
        else:
            report.append("\n❌ SOME TESTS FAILED - Check DNS and mail server configuration")

        report.append("=" * 60)

        return "\n".join(report)

    def save_results(self, output_file: str):
        """Save test results to JSON file."""
        with open(output_file, "w") as f:
            json.dump(self.test_results, f, indent=2)

        logger.info(f"Test results saved to: {output_file}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="DNS Mail Integration Test Runner", formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "--domain", default=os.environ.get("MAIL_DOMAIN", "lab.sethlakowske.com"), help="Mail domain to test"
    )

    parser.add_argument("--server", default=os.environ.get("DNS_SERVER", "localhost"), help="DNS server to test")

    parser.add_argument("--port", type=int, default=int(os.environ.get("DNS_PORT", "53")), help="DNS port to test")

    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    parser.add_argument("--performance", action="store_true", help="Run performance tests")

    parser.add_argument("--integration", action="store_true", help="Run integration tests")

    parser.add_argument("--report", action="store_true", help="Generate detailed test report")

    parser.add_argument("--output", default="dns_mail_test_results.json", help="Output file for test results")

    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    logger.info(f"Starting DNS mail integration tests for domain: {args.domain}")

    # Create test runner
    runner = DNSMailTestRunner(args.domain, args.server, args.port)

    # Setup environment
    runner.setup_environment()

    # Run tests
    try:
        results = runner.run_all_tests(include_integration=args.integration, include_performance=args.performance)

        # Save results
        runner.save_results(args.output)

        # Generate report
        if args.report:
            report = runner.generate_report()
            print(report)

            # Save report to file
            report_file = args.output.replace(".json", "_report.txt")
            with open(report_file, "w") as f:
                f.write(report)
            logger.info(f"Test report saved to: {report_file}")

        # Exit with appropriate code
        overall = results.get("overall", {})
        if overall.get("success_rate", 0) == 100:
            logger.info("All tests passed!")
            sys.exit(0)
        else:
            logger.error("Some tests failed!")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("Test run interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Test run failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
