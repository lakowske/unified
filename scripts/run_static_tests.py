#!/usr/bin/env python3
"""Test runner for static environment testing.

This script provides a comprehensive test runner for the static environment
testing system, including test data validation, environment management,
and comprehensive reporting.
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

try:
    from unified.environments.config import EnvironmentConfig
    from unified.environments.manager import UnifiedEnvironmentManager
    from unified.environments.network import NetworkInfo
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Please ensure you're running from the project root directory")
    sys.exit(1)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(project_root / "logs" / "static_tests.log")],
)
logger = logging.getLogger(__name__)


class StaticTestRunner:
    """Comprehensive test runner for static environment testing."""

    def __init__(self, project_dir: Path) -> None:
        """Initialize the test runner.

        Args:
            project_dir: Path to the project root directory
        """
        self.project_dir = project_dir
        self.config = EnvironmentConfig(project_dir)
        self.manager = UnifiedEnvironmentManager(project_dir, environments_dir="environments/test-data")
        self.network = NetworkInfo(project_dir)

    def run_validation_tests(self) -> Dict[str, Any]:
        """Run validation tests for test data and configurations.

        Returns:
            Dictionary with validation test results
        """
        logger.info("Running validation tests...")

        results = {"structure_validation": False, "environment_configurations": {}, "test_report": {}}

        try:
            # Test data structure validation
            test_data_dir = self.project_dir / "environments" / "test-data"
            environments_dir = test_data_dir

            # Check if required directories exist
            required_dirs = [test_data_dir, environments_dir]
            required_files = [
                test_data_dir / "validation" / "expected_ports.json",
                test_data_dir / "validation" / "service_health.json",
                test_data_dir / "validation" / "startup_order.json",
            ]

            structure_valid = all(d.exists() for d in required_dirs) and all(f.exists() for f in required_files)
            results["structure_validation"] = structure_valid

            if structure_valid:
                logger.info("Test data structure validation passed")
            else:
                logger.error("Structure validation failed: missing directories or files")

            # Environment configuration validation
            environments = ["test-env-1", "test-env-2"]
            for env_name in environments:
                try:
                    # Check if environment files exist
                    env_dir = test_data_dir / env_name
                    env_file = env_dir / f".env.{env_name}"
                    compose_file = env_dir / f"docker-compose.{env_name}.yml"

                    files_exist = env_file.exists() and compose_file.exists()
                    results["environment_configurations"][env_name] = files_exist

                    if files_exist:
                        logger.info(f"Environment {env_name} validation passed")
                    else:
                        logger.error(f"Environment {env_name} configuration files missing")

                except Exception as e:
                    logger.error(f"Environment {env_name} validation failed: {e}")
                    results["environment_configurations"][env_name] = False

            # Generate simple test report
            results["test_report"] = {"environments": environments, "structure_valid": results["structure_validation"]}
            logger.info("Test report generated successfully")

        except Exception as e:
            logger.error(f"Error during validation tests: {e}")
            results["error"] = str(e)

        return results


def main() -> None:
    """Main entry point for the static test runner."""
    parser = argparse.ArgumentParser(description="Run static environment tests")
    parser.add_argument("--validation-only", action="store_true", help="Run only validation tests")
    parser.add_argument("--output", type=str, help="Output file for test results (JSON format)")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Initialize test runner
    project_dir = Path(__file__).parent.parent
    runner = StaticTestRunner(project_dir)

    try:
        results = runner.run_validation_tests()

        # Output results
        if args.output:
            output_file = Path(args.output)
            with output_file.open("w") as f:
                json.dump(results, f, indent=2)
            print(f"Test results written to: {output_file}")
        else:
            print(json.dumps(results, indent=2))

    except Exception as e:
        logger.error(f"Error running tests: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
