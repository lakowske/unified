"""Performance test runner for container startup and shutdown testing.

This module provides a comprehensive test runner that orchestrates performance
testing of container environments, monitoring Docker events and health checks
to measure startup and shutdown performance.
"""

import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ..environments.manager import UnifiedEnvironmentManager
from .event_monitor import ContainerEventMonitor
from .health_watcher import HealthCheckWatcher
from .performance_collector import PerformanceCollector

logger = logging.getLogger(__name__)


class PerformanceTestRunner:
    """Orchestrates performance testing of container environments."""

    def __init__(
        self, project_dir: Union[str, Path], output_dir: Optional[Path] = None, environments_dir: str = "environments"
    ):
        """Initialize performance test runner.

        Args:
            project_dir: Project directory path
            output_dir: Directory to save performance data
            environments_dir: Directory containing environment subdirectories
        """
        self.project_dir = Path(project_dir)
        self.output_dir = output_dir or self.project_dir / "performance_data"
        self.output_dir.mkdir(exist_ok=True)

        # Initialize components
        self.environment_manager = UnifiedEnvironmentManager(self.project_dir, environments_dir)

        # If using test-data directory, override the config to use the right path
        if environments_dir == "environments/test-data":
            from ..environments.config import EnvironmentConfig

            class TestEnvironmentConfig(EnvironmentConfig):
                def load_environment(self, environment: str) -> Dict[str, Any]:
                    """Load configuration for a test environment."""
                    logger.info(f"Loading test environment configuration for: {environment}")

                    # Look in test-data directory structure
                    env_file = self.project_dir / "environments" / "test-data" / environment / f".env.{environment}"
                    if not env_file.exists():
                        raise FileNotFoundError(f"Test environment file not found: {env_file}")

                    self.env_vars = self._parse_env_file(env_file)

                    # Load docker-compose configuration
                    compose_file = (
                        self.project_dir
                        / "environments"
                        / "test-data"
                        / environment
                        / f"docker-compose.{environment}.yml"
                    )
                    if not compose_file.exists():
                        raise FileNotFoundError(f"Test docker compose file not found: {compose_file}")

                    self.compose_config = self._parse_compose_file(compose_file)

                    # Extract service configurations
                    self.service_configs = self._extract_service_configs()

                    # Return combined configuration
                    return {
                        "environment": environment,
                        "env_vars": self.env_vars,
                        "compose_config": self.compose_config,
                        "service_configs": self.service_configs,
                        **self.env_vars,  # Include all env vars at top level for backward compatibility
                    }

            self.environment_manager.config = TestEnvironmentConfig(self.project_dir)

        self.event_monitor = ContainerEventMonitor()
        self.health_watcher = HealthCheckWatcher()
        self.performance_collector = PerformanceCollector(self.output_dir)

        # Test configuration
        self.test_config = {
            "startup_timeout": 20,  # 20 seconds (user requirement)
            "shutdown_timeout": 30,  # 30 seconds
            "health_check_interval": 2.0,  # 2 seconds
            "warmup_iterations": 1,
            "test_iterations": 3,
            "cooldown_time": 10,  # 10 seconds between tests
        }

        # Setup monitoring callbacks
        self._setup_monitoring()

    def _setup_monitoring(self) -> None:
        """Setup monitoring callbacks for event collection."""

        # Event monitor callback
        def on_container_event(event):
            logger.debug(f"Container event: {event}")

        # Health watcher callback
        def on_health_change(health_status):
            logger.debug(f"Health change: {health_status}")

        self.event_monitor.add_event_callback(on_container_event)
        self.health_watcher.add_health_callback(on_health_change)

    def configure_test(self, **kwargs) -> None:
        """Configure test parameters.

        Args:
            **kwargs: Configuration parameters
        """
        self.test_config.update(kwargs)
        logger.info(f"Test configuration updated: {kwargs}")

    def run_environment_performance_test(
        self, environment_name: str, iterations: Optional[int] = None, include_warmup: bool = True
    ) -> Dict[str, Any]:
        """Run performance test for a specific environment.

        Args:
            environment_name: Name of the environment to test
            iterations: Number of test iterations (default from config)
            include_warmup: Whether to include warmup iteration

        Returns:
            Test results dictionary
        """
        iterations = iterations or self.test_config["test_iterations"]

        logger.info(f"Starting performance test for environment: {environment_name}")
        logger.info(f"Test iterations: {iterations}, Warmup: {include_warmup}")

        # Validate environment exists
        if environment_name not in self.environment_manager.list_environments():
            raise ValueError(f"Environment '{environment_name}' not found")

        # Initialize test results
        test_results = {
            "environment": environment_name,
            "start_time": datetime.now(),
            "iterations": iterations,
            "warmup_included": include_warmup,
            "results": [],
            "summary": {},
        }

        try:
            # Run warmup iteration if requested
            if include_warmup:
                logger.info("Running warmup iteration...")
                warmup_result = self._run_single_iteration(environment_name, "warmup")
                test_results["warmup_result"] = warmup_result

                # Cooldown after warmup
                time.sleep(self.test_config["cooldown_time"])

            # Run test iterations
            for i in range(iterations):
                logger.info(f"Running test iteration {i + 1}/{iterations}")

                iteration_result = self._run_single_iteration(environment_name, f"iteration_{i + 1}")
                test_results["results"].append(iteration_result)

                # Cooldown between iterations (except last)
                if i < iterations - 1:
                    time.sleep(self.test_config["cooldown_time"])

            # Calculate summary statistics
            test_results["summary"] = self._calculate_test_summary(test_results["results"])
            test_results["end_time"] = datetime.now()

            logger.info(f"Performance test completed for {environment_name}")
            return test_results

        except Exception as e:
            logger.error(f"Performance test failed for {environment_name}: {e}")
            test_results["error"] = str(e)
            test_results["end_time"] = datetime.now()
            return test_results

    def _run_single_iteration(self, environment_name: str, iteration_name: str) -> Dict[str, Any]:
        """Run a single test iteration.

        Args:
            environment_name: Environment name
            iteration_name: Name/ID of the iteration

        Returns:
            Iteration results
        """
        iteration_start = datetime.now()

        logger.info(f"Starting iteration: {iteration_name}")

        # Get environment configuration to determine containers
        env_config = self.environment_manager.config.load_environment(environment_name)
        expected_containers = self._get_expected_containers(env_config, environment_name)
        persistent_containers = self._get_persistent_containers(env_config, environment_name)

        # Setup monitoring for all containers (for events) but only wait for persistent ones
        self._setup_container_monitoring(expected_containers)

        # Clear previous monitoring data
        self.event_monitor.clear_events()
        self.health_watcher.clear_history()

        # Start monitoring
        self.event_monitor.start_monitoring()
        self.health_watcher.start_monitoring()

        startup_performance = {}
        startup_success = False
        shutdown_success = False
        cleanup_success = False
        startup_time = 0
        shutdown_time = 0
        healthy_times = {}
        error_message = None

        try:
            # Start environment
            startup_start = time.time()
            startup_result = self.environment_manager.start_environment(
                environment_name, timeout=self.test_config["startup_timeout"]
            )
            startup_end = time.time()
            startup_time = startup_end - startup_start

            if not startup_result.get("success", False):
                raise Exception(f"Failed to start environment: {startup_result.get('message', 'Unknown error')}")

            startup_success = True

            # Wait a moment for containers to be created and health monitoring to start
            time.sleep(1)

            # Re-setup health monitoring for containers that now exist
            try:
                self._setup_health_monitoring_for_running_containers(persistent_containers)
            except Exception as e:
                logger.warning(f"Health monitoring setup failed: {e}")

            # Wait for persistent containers to become healthy (skip one-time containers)
            try:
                healthy_times = self._wait_for_containers_healthy(persistent_containers)
            except Exception as e:
                logger.warning(f"Health check waiting failed: {e}")
                healthy_times = {}

            # Keep monitoring running through shutdown - don't stop yet

            # Collect startup performance data (monitoring still running)
            try:
                startup_performance = self._collect_startup_performance(
                    environment_name, expected_containers, startup_start, startup_end
                )
            except Exception as e:
                logger.warning(f"Performance data collection failed: {e}")
                startup_performance = {}

        except Exception as e:
            error_message = str(e)
            logger.error(f"Startup phase failed for iteration {iteration_name}: {e}")

        finally:
            # Always attempt shutdown and cleanup, regardless of startup success
            try:
                # Test shutdown performance (monitoring still running)
                shutdown_start = time.time()
                shutdown_result = self.environment_manager.stop_environment(environment_name)
                shutdown_end = time.time()
                shutdown_time = shutdown_end - shutdown_start

                if shutdown_result.get("success", False):
                    shutdown_success = True
                    logger.info(f"Environment {environment_name} shutdown completed")
                else:
                    logger.warning(f"Shutdown had issues: {shutdown_result.get('message', 'Unknown error')}")

            except Exception as e:
                logger.error(f"Shutdown failed for iteration {iteration_name}: {e}")

            try:
                # Cleanup environment (monitoring still running)
                cleanup_result = self.environment_manager.cleanup_environment(environment_name)

                if cleanup_result.get("success", False):
                    cleanup_success = True
                    logger.info(f"Environment {environment_name} cleanup completed")
                else:
                    logger.warning(f"Cleanup had issues: {cleanup_result.get('message', 'Unknown error')}")

            except Exception as e:
                logger.error(f"Cleanup failed for iteration {iteration_name}: {e}")

            # Wait a moment for final events to be captured
            time.sleep(2)

            # NOW stop monitoring and collect final data
            self.event_monitor.stop_monitoring()
            self.health_watcher.stop_monitoring()

            # Collect final performance data including shutdown events
            try:
                final_performance = self._collect_final_performance(
                    environment_name, expected_containers, shutdown_start, shutdown_end
                )
                # Update startup_performance with final data
                if final_performance:
                    startup_performance.update(final_performance)
            except Exception as e:
                logger.warning(f"Final performance data collection failed: {e}")

        # Calculate iteration results
        iteration_result = {
            "iteration": iteration_name,
            "start_time": iteration_start,
            "end_time": datetime.now(),
            "startup_time": startup_time,
            "shutdown_time": shutdown_time,
            "healthy_times": healthy_times,
            "startup_performance": startup_performance,
            "startup_success": startup_success,
            "shutdown_success": shutdown_success,
            "cleanup_success": cleanup_success,
            "containers": expected_containers,
        }

        if error_message:
            iteration_result["error"] = error_message
            logger.error(f"Iteration {iteration_name} failed: {error_message}")
        else:
            logger.info(f"Iteration {iteration_name} completed successfully")

        return iteration_result

    def _get_expected_containers(self, env_config: Dict[str, Any], environment_name: str) -> List[str]:
        """Get list of expected containers for an environment.

        Args:
            env_config: Environment configuration
            environment_name: Environment name

        Returns:
            List of expected container names
        """
        expected_containers = []

        # Extract from compose configuration
        compose_config = env_config.get("compose_config", {})
        services = compose_config.get("services", {})

        for service_name in services.keys():
            # Generate expected container name
            container_name = f"{service_name}-{environment_name}"
            expected_containers.append(container_name)

        return expected_containers

    def _get_persistent_containers(self, env_config: Dict[str, Any], environment_name: str) -> List[str]:
        """Get list of persistent containers that should have health checks.

        Args:
            env_config: Environment configuration
            environment_name: Environment name

        Returns:
            List of persistent container names (excludes one-time containers)
        """
        persistent_containers = []

        # Extract from compose configuration
        compose_config = env_config.get("compose_config", {})
        services = compose_config.get("services", {})

        # One-time containers that exit after completing their work
        one_time_services = {"volume-setup", "flyway"}

        for service_name in services.keys():
            if service_name not in one_time_services:
                container_name = f"{service_name}-{environment_name}"
                persistent_containers.append(container_name)

        return persistent_containers

    def _setup_container_monitoring(self, container_names: List[str]) -> None:
        """Setup monitoring for specific containers.

        Args:
            container_names: List of container names to monitor
        """
        # Clear existing filters
        self.event_monitor.container_filters.clear()
        self.health_watcher.monitored_containers.clear()

        # Add new filters
        for container_name in container_names:
            self.event_monitor.add_container_filter(container_name)
            self.health_watcher.add_container(container_name)

    def _setup_health_monitoring_for_running_containers(self, container_names: List[str]) -> None:
        """Setup health monitoring for containers that are now running.

        Args:
            container_names: List of container names to monitor
        """
        # Re-add containers that now exist
        for container_name in container_names:
            try:
                self.health_watcher.add_container(container_name)
            except Exception as e:
                logger.debug(f"Could not add health monitoring for {container_name}: {e}")

    def _wait_for_containers_healthy(self, container_names: List[str]) -> Dict[str, float]:
        """Wait for containers to become healthy and measure times.

        Args:
            container_names: List of container names

        Returns:
            Dictionary mapping container names to healthy times
        """
        healthy_times = {}
        timeout = self.test_config["startup_timeout"]

        for container_name in container_names:
            start_time = time.time()

            if self.health_watcher.wait_for_healthy(container_name, timeout):
                healthy_times[container_name] = time.time() - start_time
                logger.info(f"Container {container_name} became healthy in {healthy_times[container_name]:.2f}s")
            else:
                logger.warning(f"Container {container_name} did not become healthy within timeout")
                healthy_times[container_name] = timeout

        return healthy_times

    def _collect_startup_performance(
        self, environment_name: str, container_names: List[str], startup_start: float, startup_end: float
    ) -> Dict[str, Any]:
        """Collect startup performance data from monitors.

        Args:
            environment_name: Environment name
            container_names: List of container names
            startup_start: Startup start timestamp
            startup_end: Startup end timestamp

        Returns:
            Performance data dictionary
        """
        # Set environment start time
        env_metrics = self.performance_collector.add_environment(environment_name)
        env_metrics.start_time = datetime.fromtimestamp(startup_start)

        # Collect data from event monitor
        self.performance_collector.collect_from_event_monitor(self.event_monitor, environment_name)

        # Collect data from health watcher
        self.performance_collector.collect_from_health_watcher(self.health_watcher, environment_name)

        # Finalize environment metrics
        self.performance_collector.finalize_environment(environment_name)

        # Get environment metrics
        env_metrics = self.performance_collector.environments.get(environment_name)

        if env_metrics:
            return {
                "environment_metrics": env_metrics.environment_metrics,
                "container_metrics": {name: container.metrics for name, container in env_metrics.containers.items()},
            }

        return {}

    def _collect_final_performance(
        self, environment_name: str, container_names: List[str], shutdown_start: float, shutdown_end: float
    ) -> Dict[str, Any]:
        """Collect final performance data including shutdown events.

        Args:
            environment_name: Environment name
            container_names: List of container names
            shutdown_start: Shutdown start timestamp
            shutdown_end: Shutdown end timestamp

        Returns:
            Final performance data dictionary
        """
        # Collect final data from event monitor (includes shutdown events)
        self.performance_collector.collect_from_event_monitor(self.event_monitor, environment_name)

        # Collect final data from health watcher (includes final health states)
        self.performance_collector.collect_from_health_watcher(self.health_watcher, environment_name)

        # Finalize environment metrics with all data
        self.performance_collector.finalize_environment(environment_name)

        # Get final environment metrics
        env_metrics = self.performance_collector.environments.get(environment_name)

        if env_metrics:
            return {
                "final_environment_metrics": env_metrics.environment_metrics,
                "final_container_metrics": {
                    name: container.metrics for name, container in env_metrics.containers.items()
                },
            }

        return {}

    def _calculate_test_summary(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate summary statistics from test results.

        Args:
            results: List of iteration results

        Returns:
            Summary statistics
        """
        if not results:
            return {}

        # Filter successful iterations
        successful_results = [r for r in results if r.get("startup_success", False)]

        if not successful_results:
            return {"error": "No successful iterations"}

        # Calculate startup time statistics
        startup_times = [r["startup_time"] for r in successful_results]
        shutdown_times = [r["shutdown_time"] for r in successful_results if "shutdown_time" in r]

        summary = {
            "total_iterations": len(results),
            "successful_iterations": len(successful_results),
            "success_rate": len(successful_results) / len(results),
            "startup_times": {
                "min": min(startup_times),
                "max": max(startup_times),
                "average": sum(startup_times) / len(startup_times),
                "values": startup_times,
            },
        }

        if shutdown_times:
            summary["shutdown_times"] = {
                "min": min(shutdown_times),
                "max": max(shutdown_times),
                "average": sum(shutdown_times) / len(shutdown_times),
                "values": shutdown_times,
            }

        # Calculate per-container healthy time statistics
        container_healthy_times = {}
        for result in successful_results:
            for container_name, healthy_time in result.get("healthy_times", {}).items():
                if container_name not in container_healthy_times:
                    container_healthy_times[container_name] = []
                container_healthy_times[container_name].append(healthy_time)

        summary["container_healthy_times"] = {}
        for container_name, times in container_healthy_times.items():
            summary["container_healthy_times"][container_name] = {
                "min": min(times),
                "max": max(times),
                "average": sum(times) / len(times),
                "values": times,
            }

        return summary

    def run_all_environments_test(self, environment_filter: Optional[List[str]] = None) -> Dict[str, Any]:
        """Run performance tests for all environments.

        Args:
            environment_filter: Optional list of environment names to test

        Returns:
            Combined test results
        """
        all_environments = self.environment_manager.list_environments()

        if environment_filter:
            test_environments = [env for env in all_environments if env in environment_filter]
        else:
            test_environments = all_environments

        logger.info(f"Running performance tests for environments: {test_environments}")

        combined_results = {
            "start_time": datetime.now(),
            "environments": test_environments,
            "results": {},
            "summary": {},
        }

        # Run tests for each environment
        for env_name in test_environments:
            logger.info(f"\n{'='*60}")
            logger.info(f"Testing environment: {env_name}")
            logger.info(f"{'='*60}")

            try:
                env_results = self.run_environment_performance_test(env_name)
                combined_results["results"][env_name] = env_results

                # Add cooldown between environments
                if env_name != test_environments[-1]:
                    time.sleep(self.test_config["cooldown_time"])

            except Exception as e:
                logger.error(f"Failed to test environment {env_name}: {e}")
                combined_results["results"][env_name] = {"error": str(e), "environment": env_name}

        combined_results["end_time"] = datetime.now()

        # Calculate overall summary
        combined_results["summary"] = self._calculate_overall_summary(combined_results["results"])

        return combined_results

    def _calculate_overall_summary(self, environment_results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate overall summary across all environments.

        Args:
            environment_results: Results for all environments

        Returns:
            Overall summary
        """
        summary = {
            "total_environments": len(environment_results),
            "successful_environments": 0,
            "failed_environments": 0,
            "average_startup_times": {},
            "slowest_environment": None,
            "fastest_environment": None,
        }

        successful_envs = []
        avg_startup_times = {}

        for env_name, env_result in environment_results.items():
            if env_result.get("error"):
                summary["failed_environments"] += 1
                continue

            summary["successful_environments"] += 1
            successful_envs.append(env_name)

            # Get average startup time
            env_summary = env_result.get("summary", {})
            startup_times = env_summary.get("startup_times", {})
            avg_startup = startup_times.get("average")

            if avg_startup:
                avg_startup_times[env_name] = avg_startup

        # Find slowest and fastest environments
        if avg_startup_times:
            slowest_env = max(avg_startup_times, key=avg_startup_times.get)
            fastest_env = min(avg_startup_times, key=avg_startup_times.get)

            summary["slowest_environment"] = {"name": slowest_env, "startup_time": avg_startup_times[slowest_env]}
            summary["fastest_environment"] = {"name": fastest_env, "startup_time": avg_startup_times[fastest_env]}
            summary["average_startup_times"] = avg_startup_times

        return summary

    def save_results(self, results: Dict[str, Any], filename: Optional[str] = None) -> Path:
        """Save test results to JSON file.

        Args:
            results: Test results to save
            filename: Optional filename

        Returns:
            Path to saved file
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"performance-test-results-{timestamp}.json"

        # Save performance collector data
        collector_file = self.performance_collector.save_performance_data()

        # Save test results
        results_file = self.output_dir / filename

        # Convert datetime objects to ISO format
        serialized_results = self._serialize_datetime_objects(results)

        import json

        with open(results_file, "w") as f:
            json.dump(serialized_results, f, indent=2)

        logger.info(f"Test results saved to {results_file}")
        logger.info(f"Performance data saved to {collector_file}")

        return results_file

    def _serialize_datetime_objects(self, obj):
        """Recursively serialize datetime objects to ISO format strings."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, dict):
            return {key: self._serialize_datetime_objects(value) for key, value in obj.items()}
        if isinstance(obj, list):
            return [self._serialize_datetime_objects(item) for item in obj]
        return obj
