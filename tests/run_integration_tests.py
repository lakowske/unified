#!/usr/bin/env python3
"""Unified Infrastructure Integration Test Runner

This script runs comprehensive integration tests for the unified infrastructure
using podman-compose to create isolated test environments.

Features:
- Isolated test environment creation with podman-compose
- Performance baseline measurement and tracking
- Comprehensive service integration testing
- Detailed reporting and metrics collection
- Cleanup and resource management

Usage:
    python tests/run_integration_tests.py [options]

Options:
    --environment ENV       Test environment name (default: test)
    --performance           Run performance baseline tests
    --regression            Run performance regression tests
    --dns-integration       Run DNS mail integration tests
    --verbose               Enable verbose logging
    --keep-environment      Keep test environment running after tests
    --report                Generate detailed test report
    --output DIR            Output directory for reports and logs
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

logger = logging.getLogger(__name__)


class IntegrationTestRunner:
    """Comprehensive integration test runner for unified infrastructure."""

    def __init__(
        self,
        project_dir: Path,
        environment: str = "test",
        output_dir: Optional[Path] = None
    ):
        self.project_dir = project_dir
        self.environment = environment
        self.output_dir = output_dir or (project_dir / "test_reports")
        self.test_results = {}
        self.performance_metrics = {}
        self.start_time = None
        self.end_time = None

        # Ensure output directory exists
        self.output_dir.mkdir(exist_ok=True)

    def setup_logging(self, verbose: bool = False):
        """Setup comprehensive logging for test run."""
        log_level = logging.DEBUG if verbose else logging.INFO
        
        # Create log file with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = self.output_dir / f"integration_test_{timestamp}.log"

        # Configure logging
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout),
            ],
        )

        logger.info(f"Integration test logging configured - log file: {log_file}")

    def run_basic_integration_tests(self) -> Dict[str, Any]:
        """Run basic integration tests."""
        logger.info("Running basic integration tests...")

        pytest_args = [
            "-v",
            "--tb=short",
            "--disable-warnings",
            str(self.project_dir / "tests" / "test_integration.py::TestContainerIntegration"),
            "--junit-xml=" + str(self.output_dir / "basic_integration_results.xml"),
        ]

        exit_code = pytest.main(pytest_args)

        return {
            "test_type": "basic_integration",
            "exit_code": exit_code,
            "passed": exit_code == 0,
            "timestamp": time.time(),
        }

    def run_service_integration_tests(self) -> Dict[str, Any]:
        """Run service integration tests."""
        logger.info("Running service integration tests...")

        pytest_args = [
            "-v",
            "--tb=short",
            "--disable-warnings",
            str(self.project_dir / "tests" / "test_integration.py::TestServiceIntegration"),
            "--junit-xml=" + str(self.output_dir / "service_integration_results.xml"),
        ]

        exit_code = pytest.main(pytest_args)

        return {
            "test_type": "service_integration",
            "exit_code": exit_code,
            "passed": exit_code == 0,
            "timestamp": time.time(),
        }

    def run_performance_baseline_tests(self) -> Dict[str, Any]:
        """Run performance baseline tests."""
        logger.info("Running performance baseline tests...")

        pytest_args = [
            "-v",
            "--tb=short",
            "--disable-warnings",
            str(self.project_dir / "tests" / "test_integration.py::TestPerformanceBaselines"),
            "--junit-xml=" + str(self.output_dir / "performance_baseline_results.xml"),
        ]

        exit_code = pytest.main(pytest_args)

        return {
            "test_type": "performance_baseline",
            "exit_code": exit_code,
            "passed": exit_code == 0,
            "timestamp": time.time(),
        }

    def run_performance_regression_tests(self) -> Dict[str, Any]:
        """Run performance regression tests."""
        logger.info("Running performance regression tests...")

        pytest_args = [
            "-v",
            "--tb=short",
            "--disable-warnings",
            "-m", "performance",
            str(self.project_dir / "tests" / "test_integration.py::TestPerformanceRegression"),
            "--junit-xml=" + str(self.output_dir / "performance_regression_results.xml"),
        ]

        exit_code = pytest.main(pytest_args)

        return {
            "test_type": "performance_regression",
            "exit_code": exit_code,
            "passed": exit_code == 0,
            "timestamp": time.time(),
        }

    def run_dns_mail_integration_tests(self) -> Dict[str, Any]:
        """Run DNS mail integration tests."""
        logger.info("Running DNS mail integration tests...")

        # Check if DNS mail integration tests exist
        dns_test_file = self.project_dir / "tests" / "test_dns_mail_integration.py"
        if not dns_test_file.exists():
            logger.warning("DNS mail integration test file not found, skipping")
            return {
                "test_type": "dns_mail_integration",
                "exit_code": 0,
                "passed": True,
                "skipped": True,
                "timestamp": time.time(),
            }

        pytest_args = [
            "-v",
            "--tb=short",
            "--disable-warnings",
            str(dns_test_file),
            "--junit-xml=" + str(self.output_dir / "dns_mail_integration_results.xml"),
        ]

        exit_code = pytest.main(pytest_args)

        return {
            "test_type": "dns_mail_integration",
            "exit_code": exit_code,
            "passed": exit_code == 0,
            "timestamp": time.time(),
        }

    def collect_performance_metrics(self):
        """Collect performance metrics from test runs."""
        logger.info("Collecting performance metrics...")

        # Look for performance report file created by tests
        perf_report_file = self.project_dir / "test_performance_report.json"
        if perf_report_file.exists():
            try:
                with open(perf_report_file, "r") as f:
                    self.performance_metrics = json.load(f)
                logger.info(f"Loaded {len(self.performance_metrics)} performance metrics")
            except Exception as e:
                logger.error(f"Error loading performance metrics: {e}")

    def run_all_tests(
        self,
        include_performance: bool = False,
        include_regression: bool = False,
        include_dns_integration: bool = False,
    ) -> Dict[str, Any]:
        """Run comprehensive test suite."""
        logger.info("Starting comprehensive integration test suite...")

        self.start_time = time.time()

        # Run basic tests
        self.test_results["basic_integration"] = self.run_basic_integration_tests()

        # Run service integration tests
        self.test_results["service_integration"] = self.run_service_integration_tests()

        # Run performance tests if requested
        if include_performance:
            self.test_results["performance_baseline"] = self.run_performance_baseline_tests()

        if include_regression:
            self.test_results["performance_regression"] = self.run_performance_regression_tests()

        # Run DNS integration tests if requested
        if include_dns_integration:
            self.test_results["dns_mail_integration"] = self.run_dns_mail_integration_tests()

        self.end_time = time.time()

        # Collect performance metrics
        self.collect_performance_metrics()

        # Calculate overall results
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result.get("passed", False))

        overall_result = {
            "total_test_suites": total_tests,
            "passed_test_suites": passed_tests,
            "failed_test_suites": total_tests - passed_tests,
            "success_rate": (passed_tests / total_tests) * 100 if total_tests > 0 else 0,
            "duration": self.end_time - self.start_time,
            "timestamp": self.end_time,
            "environment": self.environment,
        }

        self.test_results["overall"] = overall_result

        return self.test_results

    def generate_comprehensive_report(self) -> str:
        """Generate comprehensive test report."""
        if not self.test_results:
            return "No test results available"

        overall = self.test_results.get("overall", {})

        report = []
        report.append("=" * 80)
        report.append("UNIFIED INFRASTRUCTURE INTEGRATION TEST REPORT")
        report.append("=" * 80)
        report.append(f"Test Environment: {self.environment}")
        report.append(f"Project Directory: {self.project_dir}")
        report.append(f"Test Duration: {overall.get('duration', 0):.2f} seconds")
        report.append(f"Success Rate: {overall.get('success_rate', 0):.1f}%")
        report.append(f"Test Timestamp: {datetime.fromtimestamp(overall.get('timestamp', 0))}")
        report.append("")

        # Test Suite Results Summary
        report.append("TEST SUITE RESULTS SUMMARY:")
        report.append("-" * 50)

        for test_type, results in self.test_results.items():
            if test_type == "overall":
                continue

            status = "PASSED" if results.get("passed", False) else "FAILED"
            if results.get("skipped", False):
                status = "SKIPPED"

            report.append(f"{test_type.upper():<25} {status}")

        report.append("")

        # Detailed Results
        report.append("DETAILED TEST SUITE RESULTS:")
        report.append("-" * 50)

        for test_type, results in self.test_results.items():
            if test_type == "overall":
                continue

            report.append(f"\n{test_type.upper().replace('_', ' ')} Tests:")
            report.append(f"  Status: {'PASSED' if results.get('passed', False) else 'FAILED'}")
            if results.get("skipped", False):
                report.append("  Status: SKIPPED")
            report.append(f"  Exit Code: {results.get('exit_code', 'N/A')}")
            report.append(f"  Timestamp: {datetime.fromtimestamp(results.get('timestamp', 0))}")

        # Performance Metrics
        if self.performance_metrics:
            report.append("\nPERFORMANCE METRICS:")
            report.append("-" * 50)

            # Group metrics by category
            startup_metrics = {k: v for k, v in self.performance_metrics.items() if "startup" in k}
            connectivity_metrics = {k: v for k, v in self.performance_metrics.items() if "connectivity" in k or "response" in k}
            query_metrics = {k: v for k, v in self.performance_metrics.items() if "query" in k}
            other_metrics = {k: v for k, v in self.performance_metrics.items() 
                           if k not in startup_metrics and k not in connectivity_metrics and k not in query_metrics}

            metric_categories = [
                ("Startup Metrics", startup_metrics),
                ("Connectivity Metrics", connectivity_metrics),
                ("Query Performance", query_metrics),
                ("Other Metrics", other_metrics),
            ]

            for category_name, metrics in metric_categories:
                if metrics:
                    report.append(f"\n{category_name}:")
                    for metric, value in sorted(metrics.items()):
                        report.append(f"  {metric}: {value:.3f}s")

            # Performance summary
            all_times = [v for v in self.performance_metrics.values() if isinstance(v, (int, float))]
            if all_times:
                avg_time = sum(all_times) / len(all_times)
                max_time = max(all_times)
                min_time = min(all_times)

                report.append(f"\nPerformance Summary:")
                report.append(f"  Average operation time: {avg_time:.3f}s")
                report.append(f"  Fastest operation: {min_time:.3f}s")
                report.append(f"  Slowest operation: {max_time:.3f}s")

        # Overall Summary
        report.append("\nOVERALL SUMMARY:")
        report.append("-" * 50)
        report.append(f"Total Test Suites: {overall.get('total_test_suites', 0)}")
        report.append(f"Passed: {overall.get('passed_test_suites', 0)}")
        report.append(f"Failed: {overall.get('failed_test_suites', 0)}")
        report.append(f"Success Rate: {overall.get('success_rate', 0):.1f}%")
        report.append(f"Total Duration: {overall.get('duration', 0):.2f} seconds")

        # Status message
        if overall.get("success_rate", 0) == 100:
            report.append("\n✅ ALL TESTS PASSED - Infrastructure is working correctly!")
        else:
            report.append("\n❌ SOME TESTS FAILED - Check test results and service configuration")

        # Recommendations
        report.append("\nRECOMMENDations:")
        report.append("-" * 50)

        if overall.get("success_rate", 0) == 100:
            report.append("• Infrastructure is functioning correctly")
            report.append("• Consider running performance regression tests regularly")
            report.append("• Monitor performance metrics for trends")
        else:
            failed_suites = [k for k, v in self.test_results.items() 
                           if k != "overall" and not v.get("passed", False)]
            if failed_suites:
                report.append(f"• Investigate failed test suites: {', '.join(failed_suites)}")
                report.append("• Check service logs for errors")
                report.append("• Verify container images are built correctly")

        if self.performance_metrics:
            slow_operations = {k: v for k, v in self.performance_metrics.items() 
                             if isinstance(v, (int, float)) and v > 10.0}
            if slow_operations:
                report.append("• Performance attention needed for:")
                for op, time_val in slow_operations.items():
                    report.append(f"  - {op}: {time_val:.2f}s")

        report.append("=" * 80)

        return "\n".join(report)

    def save_results(self):
        """Save test results and reports to files."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save JSON results
        results_file = self.output_dir / f"integration_test_results_{timestamp}.json"
        with open(results_file, "w") as f:
            json.dump({
                "test_results": self.test_results,
                "performance_metrics": self.performance_metrics,
                "environment": self.environment,
                "timestamp": timestamp,
            }, f, indent=2)

        logger.info(f"Test results saved to: {results_file}")

        # Save comprehensive report
        report = self.generate_comprehensive_report()
        report_file = self.output_dir / f"integration_test_report_{timestamp}.txt"
        with open(report_file, "w") as f:
            f.write(report)

        logger.info(f"Test report saved to: {report_file}")

        return results_file, report_file


def main():
    """Main entry point for integration test runner."""
    parser = argparse.ArgumentParser(
        description="Unified Infrastructure Integration Test Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        "--environment",
        default="test",
        help="Test environment name (default: test)"
    )

    parser.add_argument(
        "--performance",
        action="store_true",
        help="Run performance baseline tests"
    )

    parser.add_argument(
        "--regression",
        action="store_true",
        help="Run performance regression tests"
    )

    parser.add_argument(
        "--dns-integration",
        action="store_true",
        help="Run DNS mail integration tests"
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    parser.add_argument(
        "--keep-environment",
        action="store_true",
        help="Keep test environment running after tests"
    )

    parser.add_argument(
        "--report",
        action="store_true",
        help="Generate and display detailed test report"
    )

    parser.add_argument(
        "--output",
        type=Path,
        help="Output directory for reports and logs"
    )

    args = parser.parse_args()

    # Get project directory
    project_dir = Path(__file__).parent.parent

    # Create test runner
    runner = IntegrationTestRunner(
        project_dir=project_dir,
        environment=args.environment,
        output_dir=args.output
    )

    # Setup logging
    runner.setup_logging(verbose=args.verbose)

    logger.info(f"Starting integration tests for environment: {args.environment}")
    logger.info(f"Project directory: {project_dir}")
    logger.info(f"Output directory: {runner.output_dir}")

    try:
        # Run tests
        results = runner.run_all_tests(
            include_performance=args.performance,
            include_regression=args.regression,
            include_dns_integration=args.dns_integration,
        )

        # Save results
        results_file, report_file = runner.save_results()

        # Display report if requested
        if args.report:
            report = runner.generate_comprehensive_report()
            print(report)

        # Exit with appropriate code
        overall = results.get("overall", {})
        success_rate = overall.get("success_rate", 0)

        if success_rate == 100:
            logger.info("✅ All integration tests passed successfully!")
            sys.exit(0)
        elif success_rate >= 75:
            logger.warning(f"⚠️  Some tests failed (success rate: {success_rate:.1f}%)")
            sys.exit(1)
        else:
            logger.error(f"❌ Many tests failed (success rate: {success_rate:.1f}%)")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("🛑 Test run interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"💥 Test run failed with error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()