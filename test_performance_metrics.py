#!/usr/bin/env python3
"""Simple script to run performance test and generate metrics files."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from unified.performance.test_runner import PerformanceTestRunner


def main():
    project_dir = Path(__file__).parent
    runner = PerformanceTestRunner(project_dir)

    # Configure for quick test
    runner.configure_test(
        test_iterations=1, warmup_iterations=0, startup_timeout=120, shutdown_timeout=30, cooldown_time=5
    )

    print("Starting performance test...")

    # Run performance test
    results = runner.run_environment_performance_test("dev", iterations=1, include_warmup=False)

    print("Performance test completed!")
    print(f"Results available in: {runner.current_run_dir}")

    # Save results and generate performance metrics
    results_file = runner.save_results(results)
    print(f"Results saved to: {results_file}")

    # Print summary
    if "error" not in results:
        summary = results.get("summary", {})
        startup_times = summary.get("startup_times", {})
        shutdown_times = summary.get("shutdown_times", {})

        print("\nPerformance Summary:")
        print(f"  Average startup time: {startup_times.get('average', 'N/A'):.2f}s")
        print(f"  Average shutdown time: {shutdown_times.get('average', 'N/A'):.2f}s")

        # Show container breakdown
        container_times = summary.get("container_healthy_times", {})
        if container_times:
            print("\nContainer startup times:")
            for container, times in container_times.items():
                print(f"  {container}: {times.get('average', 'N/A'):.2f}s")
    else:
        print(f"Error: {results['error']}")


if __name__ == "__main__":
    main()
