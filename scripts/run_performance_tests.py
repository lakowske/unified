#!/usr/bin/env python3
"""Performance test runner script.

This script provides a command-line interface for running container performance
tests and generating detailed performance reports.
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import List, Optional

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

try:
    from unified.performance.test_runner import PerformanceTestRunner
    from unified.environments.manager import UnifiedEnvironmentManager
except ImportError as e:
    print(f"Error importing performance modules: {e}")
    print("Please ensure you're running from the project root directory")
    sys.exit(1)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(project_root / "performance_data" / "performance_tests.log")
    ]
)
logger = logging.getLogger(__name__)


def run_single_environment_test(runner: PerformanceTestRunner, environment: str,
                               iterations: int, warmup: bool, save_results: bool) -> dict:
    """Run performance test for a single environment.
    
    Args:
        runner: Performance test runner
        environment: Environment name
        iterations: Number of test iterations
        warmup: Whether to include warmup iteration
        save_results: Whether to save results to file
        
    Returns:
        Test results dictionary
    """
    print(f"\n{'='*60}")
    print(f"Testing Environment: {environment}")
    print(f"{'='*60}")
    
    try:
        results = runner.run_environment_performance_test(
            environment, 
            iterations=iterations, 
            include_warmup=warmup
        )
        
        if "error" in results:
            print(f"❌ Test failed: {results['error']}")
            return results
        
        # Display summary
        summary = results["summary"]
        print(f"✅ Test completed successfully!")
        print(f"   Iterations: {summary['successful_iterations']}/{summary['total_iterations']}")
        print(f"   Success Rate: {summary['success_rate']:.1%}")
        print(f"   Average Startup Time: {summary['startup_times']['average']:.2f}s")
        print(f"   Min/Max Startup Time: {summary['startup_times']['min']:.2f}s / {summary['startup_times']['max']:.2f}s")
        
        if "shutdown_times" in summary:
            print(f"   Average Shutdown Time: {summary['shutdown_times']['average']:.2f}s")
        
        # Container-specific times
        if "container_healthy_times" in summary:
            print(f"   Container Healthy Times:")
            for container, times in summary["container_healthy_times"].items():
                print(f"     - {container}: {times['average']:.2f}s")
        
        if save_results:
            results_file = runner.save_results(results)
            print(f"   Results saved to: {results_file}")
        
        return results
    
    except Exception as e:
        logger.error(f"Error testing environment {environment}: {e}")
        return {"error": str(e)}


def run_all_environments_test(runner: PerformanceTestRunner, environments: Optional[List[str]],
                             iterations: int, warmup: bool, save_results: bool) -> dict:
    """Run performance tests for all environments.
    
    Args:
        runner: Performance test runner
        environments: List of environments to test (None for all)
        iterations: Number of test iterations
        warmup: Whether to include warmup iteration
        save_results: Whether to save results to file
        
    Returns:
        Combined test results dictionary
    """
    print(f"\n{'='*60}")
    print(f"Testing All Environments")
    print(f"{'='*60}")
    
    try:
        # Configure runner
        runner.configure_test(
            test_iterations=iterations,
            warmup_iterations=1 if warmup else 0
        )
        
        # Run tests
        results = runner.run_all_environments_test(environment_filter=environments)
        
        # Display summary
        summary = results["summary"]
        print(f"✅ All environment tests completed!")
        print(f"   Total Environments: {summary['total_environments']}")
        print(f"   Successful: {summary['successful_environments']}")
        print(f"   Failed: {summary['failed_environments']}")
        
        if "slowest_environment" in summary:
            slowest = summary["slowest_environment"]
            fastest = summary["fastest_environment"]
            print(f"   Slowest: {slowest['name']} ({slowest['startup_time']:.2f}s)")
            print(f"   Fastest: {fastest['name']} ({fastest['startup_time']:.2f}s)")
        
        # Individual environment results
        print(f"\nEnvironment Results:")
        for env_name, env_result in results["results"].items():
            if "error" in env_result:
                print(f"   ❌ {env_name}: {env_result['error']}")
            else:
                env_summary = env_result["summary"]
                avg_startup = env_summary["startup_times"]["average"]
                success_rate = env_summary["success_rate"]
                print(f"   ✅ {env_name}: {avg_startup:.2f}s avg startup, {success_rate:.1%} success")
        
        if save_results:
            results_file = runner.save_results(results)
            print(f"\nResults saved to: {results_file}")
        
        return results
    
    except Exception as e:
        logger.error(f"Error running all environments test: {e}")
        return {"error": str(e)}


def generate_performance_report(runner: PerformanceTestRunner) -> None:
    """Generate and display performance report.
    
    Args:
        runner: Performance test runner
    """
    print(f"\n{'='*60}")
    print(f"Performance Report")
    print(f"{'='*60}")
    
    try:
        report = runner.performance_collector.generate_performance_report()
        
        # Display summary
        summary = report["summary"]
        print(f"Report Generated: {report['timestamp']}")
        print(f"Total Environments: {summary['total_environments']}")
        print(f"Total Containers: {summary['total_containers']}")
        print(f"Has Baselines: {summary['has_baselines']}")
        
        # Environment details
        print(f"\nEnvironment Details:")
        for env_name, env_data in report["environments"].items():
            metrics = env_data["metrics"]
            print(f"  {env_name}:")
            print(f"    Containers: {env_data['container_count']}")
            if metrics.get("average_startup_time"):
                print(f"    Avg Startup: {metrics['average_startup_time']:.2f}s")
            if metrics.get("slowest_container"):
                print(f"    Slowest Container: {metrics['slowest_container']}")
            if metrics.get("health_check_failure_rate"):
                print(f"    Health Failure Rate: {metrics['health_check_failure_rate']:.1%}")
        
        # Recommendations
        if report["recommendations"]:
            print(f"\nRecommendations:")
            for rec in report["recommendations"]:
                print(f"  - {rec}")
        else:
            print(f"\nNo performance recommendations at this time.")
    
    except Exception as e:
        logger.error(f"Error generating performance report: {e}")
        print(f"❌ Failed to generate report: {e}")


def main():
    """Main entry point for the performance test runner."""
    parser = argparse.ArgumentParser(
        description="Run container performance tests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test single environment
  python scripts/run_performance_tests.py --environment test-env-1

  # Test all environments with 3 iterations
  python scripts/run_performance_tests.py --all --iterations 3

  # Test specific environments with warmup
  python scripts/run_performance_tests.py --environments test-env-1 test-env-2 --warmup

  # Generate performance report
  python scripts/run_performance_tests.py --report

  # Run comprehensive test suite
  python scripts/run_performance_tests.py --all --iterations 3 --warmup --save --report
        """
    )
    
    # Test selection
    test_group = parser.add_mutually_exclusive_group(required=True)
    test_group.add_argument(
        "--environment",
        type=str,
        help="Test a specific environment"
    )
    test_group.add_argument(
        "--environments",
        type=str,
        nargs="+",
        help="Test specific environments"
    )
    test_group.add_argument(
        "--all",
        action="store_true",
        help="Test all available environments"
    )
    test_group.add_argument(
        "--report",
        action="store_true",
        help="Generate performance report only"
    )
    
    # Test configuration
    parser.add_argument(
        "--iterations",
        type=int,
        default=2,
        help="Number of test iterations per environment (default: 2)"
    )
    parser.add_argument(
        "--warmup",
        action="store_true",
        help="Include warmup iteration"
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save results to file"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Startup timeout in seconds (default: 300)"
    )
    parser.add_argument(
        "--cooldown",
        type=int,
        default=10,
        help="Cooldown time between tests in seconds (default: 10)"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        help="Output directory for results"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Configure logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize test runner with correct environments directory
    output_dir = Path(args.output_dir) if args.output_dir else None
    
    # Determine environments directory based on what we're testing
    environments_dir = "environments"
    if args.environment and args.environment.startswith("test-env-"):
        environments_dir = "environments/test-data"
    elif args.environments and any(env.startswith("test-env-") for env in args.environments):
        environments_dir = "environments/test-data"
    elif args.all:
        # Check if we have test environments available
        test_manager = UnifiedEnvironmentManager(project_root, "environments/test-data")
        if test_manager.list_environments():
            environments_dir = "environments/test-data"
    
    runner = PerformanceTestRunner(project_root, output_dir, environments_dir)
    
    # Configure test parameters
    runner.configure_test(
        startup_timeout=args.timeout,
        cooldown_time=args.cooldown
    )
    
    print(f"Container Performance Test Runner")
    print(f"Project: {project_root}")
    print(f"Output: {runner.output_dir}")
    
    try:
        # Handle different test modes
        if args.report:
            generate_performance_report(runner)
        elif args.environment:
            run_single_environment_test(
                runner, args.environment, args.iterations, args.warmup, args.save
            )
        elif args.environments:
            run_all_environments_test(
                runner, args.environments, args.iterations, args.warmup, args.save
            )
        elif args.all:
            run_all_environments_test(
                runner, None, args.iterations, args.warmup, args.save
            )
        
        # Generate report if requested
        if args.save and not args.report:
            generate_performance_report(runner)
    
    except KeyboardInterrupt:
        print("\n❌ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Test runner error: {e}")
        print(f"❌ Test runner failed: {e}")
        sys.exit(1)
    finally:
        # Ensure monitoring is stopped
        runner.event_monitor.stop_monitoring()
        runner.health_watcher.stop_monitoring()


if __name__ == "__main__":
    main()