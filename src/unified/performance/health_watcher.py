"""Health check monitoring for container readiness tracking.

This module provides monitoring of Docker container health checks to track
when containers transition from starting to healthy state, providing accurate
startup time measurements.
"""

import logging
import subprocess
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class HealthStatus:
    """Represents a container health status."""

    STARTING = "starting"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    NONE = "none"

    def __init__(self, container_name: str, status: str, timestamp: Optional[datetime] = None):
        self.container_name = container_name
        self.status = status
        self.timestamp = timestamp or datetime.now()

    def __str__(self) -> str:
        return f"HealthStatus({self.container_name}, {self.status}, {self.timestamp})"

    def __repr__(self) -> str:
        return self.__str__()


class HealthCheckWatcher:
    """Monitors Docker container health checks."""

    def __init__(self, check_interval: float = 2.0):
        """Initialize health check watcher.

        Args:
            check_interval: Interval in seconds between health checks
        """
        self.check_interval = check_interval
        self.monitored_containers: Dict[str, str] = {}  # container_name -> container_id
        self.health_history: List[HealthStatus] = []
        self.health_callbacks: List[Callable[[HealthStatus], None]] = []
        self.monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None

        # Track current health status for each container
        self.current_status: Dict[str, str] = {}

    def add_container(self, container_name: str, container_id: Optional[str] = None) -> None:
        """Add a container to monitor.

        Args:
            container_name: Name of the container
            container_id: Container ID (will be resolved if not provided)
        """
        if not container_id:
            container_id = self._resolve_container_id(container_name)

        if container_id:
            self.monitored_containers[container_name] = container_id
            logger.info(f"Added container {container_name} ({container_id}) to health monitoring")
        else:
            logger.warning(f"Could not resolve container ID for {container_name}")

    def remove_container(self, container_name: str) -> None:
        """Remove a container from monitoring.

        Args:
            container_name: Name of the container to remove
        """
        if container_name in self.monitored_containers:
            del self.monitored_containers[container_name]
            if container_name in self.current_status:
                del self.current_status[container_name]
            logger.info(f"Removed container {container_name} from health monitoring")

    def add_health_callback(self, callback: Callable[[HealthStatus], None]) -> None:
        """Add a callback function for health status changes.

        Args:
            callback: Function to call when health status changes
        """
        self.health_callbacks.append(callback)

    def start_monitoring(self) -> None:
        """Start monitoring container health checks."""
        if self.monitoring:
            logger.warning("Health monitoring already started")
            return

        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_health, daemon=True)
        self.monitor_thread.start()
        logger.info("Started health check monitoring")

    def stop_monitoring(self) -> None:
        """Stop monitoring container health checks."""
        if not self.monitoring:
            return

        self.monitoring = False

        # Wait for monitor thread to finish
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)

        logger.info("Stopped health check monitoring")

    def _resolve_container_id(self, container_name: str) -> Optional[str]:
        """Resolve container ID from container name.

        Args:
            container_name: Name of the container

        Returns:
            Container ID or None if not found
        """
        try:
            result = subprocess.run(
                ["docker", "ps", "-q", "--filter", f"name={container_name}"], capture_output=True, text=True, timeout=10
            )

            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip().split("\n")[0]

        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout resolving container ID for {container_name}")
        except Exception as e:
            logger.error(f"Error resolving container ID for {container_name}: {e}")

        return None

    def _monitor_health(self) -> None:
        """Monitor container health in a separate thread."""
        try:
            while self.monitoring:
                # Check health status for all monitored containers
                for container_name, container_id in self.monitored_containers.items():
                    try:
                        health_status = self._get_container_health(container_id)

                        # Check if status changed
                        current_status = self.current_status.get(container_name)
                        if health_status != current_status:
                            self._process_health_change(container_name, health_status)

                    except Exception as e:
                        logger.error(f"Error checking health for {container_name}: {e}")

                # Wait before next check
                time.sleep(self.check_interval)

        except Exception as e:
            logger.error(f"Error in health monitoring thread: {e}")

    def _get_container_health(self, container_id: str) -> str:
        """Get the health status of a container.

        Args:
            container_id: Container ID

        Returns:
            Health status string
        """
        try:
            result = subprocess.run(
                ["docker", "inspect", container_id, "--format", "{{.State.Health.Status}}"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                status = result.stdout.strip()
                # Handle case where container has no health check
                if status == "<no value>":
                    return HealthStatus.NONE
                return status
            logger.warning(f"Failed to get health status for container {container_id}: {result.stderr}")

        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout getting health status for container {container_id}")
        except Exception as e:
            logger.error(f"Error getting health status for container {container_id}: {e}")

        return HealthStatus.NONE

    def _process_health_change(self, container_name: str, new_status: str) -> None:
        """Process a health status change.

        Args:
            container_name: Name of the container
            new_status: New health status
        """
        # Update current status
        old_status = self.current_status.get(container_name)
        self.current_status[container_name] = new_status

        # Create health status record
        health_status = HealthStatus(container_name, new_status)
        self.health_history.append(health_status)

        logger.info(f"Health status change: {container_name} {old_status} -> {new_status}")

        # Call registered callbacks
        for callback in self.health_callbacks:
            try:
                callback(health_status)
            except Exception as e:
                logger.error(f"Error in health callback: {e}")

    def get_health_history(self, container_name: str) -> List[HealthStatus]:
        """Get health history for a container.

        Args:
            container_name: Name of the container

        Returns:
            List of health status records
        """
        return [status for status in self.health_history if status.container_name == container_name]

    def get_current_status(self, container_name: str) -> str:
        """Get current health status for a container.

        Args:
            container_name: Name of the container

        Returns:
            Current health status
        """
        return self.current_status.get(container_name, HealthStatus.NONE)

    def wait_for_healthy(self, container_name: str, timeout: float = 120.0) -> bool:
        """Wait for a container to become healthy.

        Args:
            container_name: Name of the container
            timeout: Timeout in seconds

        Returns:
            True if container became healthy, False if timeout
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            if self.get_current_status(container_name) == HealthStatus.HEALTHY:
                return True
            time.sleep(1.0)

        return False

    def wait_for_status(self, container_name: str, target_status: str, timeout: float = 120.0) -> bool:
        """Wait for a container to reach a specific status.

        Args:
            container_name: Name of the container
            target_status: Target health status
            timeout: Timeout in seconds

        Returns:
            True if container reached target status, False if timeout
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            if self.get_current_status(container_name) == target_status:
                return True
            time.sleep(1.0)

        return False

    def calculate_time_to_healthy(self, container_name: str) -> Optional[float]:
        """Calculate time from starting to healthy for a container.

        Args:
            container_name: Name of the container

        Returns:
            Time in seconds, or None if not calculable
        """
        history = self.get_health_history(container_name)

        starting_time = None
        healthy_time = None

        for status in history:
            if status.status == HealthStatus.STARTING:
                starting_time = status.timestamp
            elif status.status == HealthStatus.HEALTHY and starting_time:
                healthy_time = status.timestamp
                break

        if starting_time and healthy_time:
            return (healthy_time - starting_time).total_seconds()

        return None

    def get_health_summary(self) -> Dict[str, Any]:
        """Get a summary of health monitoring.

        Returns:
            Dictionary with health monitoring statistics
        """
        summary = {
            "monitored_containers": len(self.monitored_containers),
            "total_health_records": len(self.health_history),
            "current_status": self.current_status.copy(),
            "containers": {},
        }

        # Add per-container statistics
        for container_name in self.monitored_containers:
            history = self.get_health_history(container_name)
            time_to_healthy = self.calculate_time_to_healthy(container_name)

            summary["containers"][container_name] = {
                "health_records": len(history),
                "current_status": self.get_current_status(container_name),
                "time_to_healthy": time_to_healthy,
            }

        return summary

    def clear_history(self) -> None:
        """Clear health history."""
        self.health_history.clear()
        self.current_status.clear()
        logger.info("Cleared health history")
