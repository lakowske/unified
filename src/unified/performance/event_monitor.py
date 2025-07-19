"""Docker events monitoring for container lifecycle tracking.

This module provides real-time monitoring of Docker events to track container
lifecycle events (create, start, health_status, stop, remove) for performance
analysis and optimization.
"""

import json
import logging
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class ContainerEvent:
    """Represents a Docker container event."""

    def __init__(self, event_data: Dict[str, Any]):
        self.timestamp = datetime.now()
        self.action = event_data.get("Action", "")
        self.container_id = event_data.get("id", "")
        self.container_name = event_data.get("Actor", {}).get("Attributes", {}).get("name", "")
        self.image = event_data.get("Actor", {}).get("Attributes", {}).get("image", "")
        self.raw_data = event_data

        # Parse event timestamp if available (prefer nanosecond precision)
        if "timeNano" in event_data:
            try:
                # Convert nanoseconds to seconds for datetime
                self.timestamp = datetime.fromtimestamp(event_data["timeNano"] / 1_000_000_000)
            except (ValueError, TypeError):
                pass
        elif "time" in event_data:
            try:
                self.timestamp = datetime.fromtimestamp(event_data["time"])
            except (ValueError, TypeError):
                pass

    def __str__(self) -> str:
        return f"ContainerEvent({self.action}, {self.container_name}, {self.timestamp})"

    def __repr__(self) -> str:
        return self.__str__()


class ContainerEventMonitor:
    """Monitors Docker events for container lifecycle tracking."""

    def __init__(self, container_filters: Optional[List[str]] = None, capture_all_events: bool = False):
        """Initialize container event monitor.

        Args:
            container_filters: List of container name patterns to monitor (ignored if capture_all_events=True)
            capture_all_events: If True, capture ALL Docker events regardless of filters
        """
        self.container_filters = container_filters or []
        self.capture_all_events = capture_all_events
        self.events: List[ContainerEvent] = []
        self.all_events_log: List[str] = []  # Raw event JSON strings for complete logging
        self.event_callbacks: List[Callable[[ContainerEvent], None]] = []
        self.monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.process: Optional[subprocess.Popen] = None

        # Track containers we're interested in
        self.tracked_containers: Set[str] = set()

        # Event type mapping
        self.lifecycle_events = {"create", "start", "restart", "stop", "kill", "die", "destroy", "health_status"}

    def add_container_filter(self, container_name: str) -> None:
        """Add a container name pattern to monitor.

        Args:
            container_name: Container name or pattern
        """
        self.container_filters.append(container_name)
        self.tracked_containers.add(container_name)

    def add_event_callback(self, callback: Callable[[ContainerEvent], None]) -> None:
        """Add a callback function for container events.

        Args:
            callback: Function to call when events occur
        """
        self.event_callbacks.append(callback)

    def start_monitoring(self) -> None:
        """Start monitoring Docker events."""
        if self.monitoring:
            logger.warning("Event monitoring already started")
            return

        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_events, daemon=True)
        self.monitor_thread.start()
        logger.info("Started Docker event monitoring")

    def stop_monitoring(self) -> None:
        """Stop monitoring Docker events."""
        if not self.monitoring:
            return

        self.monitoring = False

        # Terminate the docker events process
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            except Exception as e:
                logger.warning(f"Error terminating docker events process: {e}")

        # Wait for monitor thread to finish
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)

        logger.info("Stopped Docker event monitoring")

    def _monitor_events(self) -> None:
        """Monitor Docker events in a separate thread."""
        try:
            # Build docker events command
            cmd = ["docker", "events", "--format", "json"]

            # Add container filters if specified and not capturing all events
            if self.container_filters and not self.capture_all_events:
                for container in self.container_filters:
                    cmd.extend(["--filter", f"container={container}"])

            logger.info(f"Starting docker events monitoring with command: {' '.join(cmd)}")
            if self.capture_all_events:
                logger.info("Capturing ALL Docker events for comprehensive logging")

            # Start the process
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line buffered
            )

            # Read events line by line
            while self.monitoring and self.process.poll() is None:
                try:
                    line = self.process.stdout.readline()
                    if not line:
                        break

                    line = line.strip()
                    if not line:
                        continue

                    # Always store raw event for comprehensive logging
                    if self.capture_all_events:
                        self.all_events_log.append(line)

                    # Parse event JSON
                    event_data = json.loads(line)

                    # Filter for container events
                    if event_data.get("Type") == "container":
                        event = ContainerEvent(event_data)

                        # Check if this is a lifecycle event we care about
                        if event.action in self.lifecycle_events:
                            # Process all events if capture_all_events, otherwise apply filters
                            if self.capture_all_events or self._should_process_event(event):
                                self._process_event(event)

                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse event JSON: {e}")
                except Exception as e:
                    logger.error(f"Error processing event: {e}")

        except Exception as e:
            logger.error(f"Error in event monitoring thread: {e}")
        finally:
            if self.process:
                self.process = None

    def _process_event(self, event: ContainerEvent) -> None:
        """Process a container event.

        Args:
            event: The container event to process
        """
        # Store the event
        self.events.append(event)

        logger.debug(f"Captured Docker event: {event.action} for {event.container_name} at {event.timestamp}")

        # Call registered callbacks
        for callback in self.event_callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Error in event callback: {e}")

    def get_events_for_container(self, container_name: str) -> List[ContainerEvent]:
        """Get all events for a specific container.

        Args:
            container_name: Name of the container

        Returns:
            List of events for the container
        """
        return [event for event in self.events if event.container_name == container_name]

    def get_events_by_action(self, action: str) -> List[ContainerEvent]:
        """Get all events with a specific action.

        Args:
            action: The action to filter by

        Returns:
            List of events with the specified action
        """
        return [event for event in self.events if event.action == action]

    def get_lifecycle_timeline(self, container_name: str) -> Dict[str, Optional[datetime]]:
        """Get the lifecycle timeline for a container.

        Args:
            container_name: Name of the container

        Returns:
            Dictionary mapping lifecycle events to timestamps
        """
        events = self.get_events_for_container(container_name)
        timeline = {
            "create": None,
            "start": None,
            "health_status_starting": None,
            "health_status_healthy": None,
            "health_status_unhealthy": None,
            "stop": None,
            "destroy": None,
        }

        for event in events:
            if event.action == "create":
                timeline["create"] = event.timestamp
            elif event.action == "start":
                timeline["start"] = event.timestamp
            elif event.action == "health_status":
                # Parse health status from attributes
                attrs = event.raw_data.get("Actor", {}).get("Attributes", {})
                health_status = attrs.get("health_status", "")
                if health_status == "starting":
                    timeline["health_status_starting"] = event.timestamp
                elif health_status == "healthy":
                    timeline["health_status_healthy"] = event.timestamp
                elif health_status == "unhealthy":
                    timeline["health_status_unhealthy"] = event.timestamp
            elif event.action in ["stop", "kill", "die"]:
                timeline["stop"] = event.timestamp
            elif event.action == "destroy":
                timeline["destroy"] = event.timestamp

        return timeline

    def calculate_startup_time(self, container_name: str) -> Optional[float]:
        """Calculate the startup time for a container.

        Args:
            container_name: Name of the container

        Returns:
            Startup time in seconds, or None if not calculable
        """
        timeline = self.get_lifecycle_timeline(container_name)

        start_time = timeline.get("start")
        healthy_time = timeline.get("health_status_healthy")

        if start_time and healthy_time:
            return (healthy_time - start_time).total_seconds()

        return None

    def clear_events(self) -> None:
        """Clear all stored events."""
        self.events.clear()
        self.all_events_log.clear()
        logger.info("Cleared all stored events")

    def get_event_summary(self) -> Dict[str, Any]:
        """Get a summary of all events.

        Returns:
            Dictionary with event statistics
        """
        summary = {
            "total_events": len(self.events),
            "containers": len(set(event.container_name for event in self.events)),
            "event_types": {},
            "time_range": {"start": None, "end": None},
        }

        if self.events:
            # Calculate time range
            timestamps = [event.timestamp for event in self.events]
            summary["time_range"]["start"] = min(timestamps)
            summary["time_range"]["end"] = max(timestamps)

            # Count event types
            for event in self.events:
                action = event.action
                summary["event_types"][action] = summary["event_types"].get(action, 0) + 1

        return summary

    def _should_process_event(self, event: ContainerEvent) -> bool:
        """Check if an event should be processed based on container filters.

        Args:
            event: The container event to check

        Returns:
            True if the event should be processed
        """
        # Exclude our temporary log collection containers
        if event.container_name.startswith("log-collector-"):
            logger.debug(f"Excluding log collector container: {event.container_name}")
            return False

        if not self.container_filters:
            return True

        # Check if the container name matches any of our filters
        for container_filter in self.container_filters:
            if container_filter in event.container_name:
                return True

        return False

    def save_full_event_log(self, output_path: Path) -> Path:
        """Save the complete event log to a file.

        Args:
            output_path: Path where to save the event log

        Returns:
            Path to the saved event log file
        """
        output_path = Path(output_path)

        with open(output_path, "w") as f:
            # Write header
            f.write("# Docker Events Log\n")
            f.write(f"# Monitoring started: {datetime.now().isoformat()}\n")
            f.write(f"# Capture all events: {self.capture_all_events}\n")
            f.write(f"# Container filters: {self.container_filters}\n")
            f.write(f"# Total raw events: {len(self.all_events_log)}\n")
            f.write(f"# Total processed events: {len(self.events)}\n")
            f.write("# ================================================================================\n\n")

            # Write all raw events
            for event_json in self.all_events_log:
                f.write(f"{event_json}\n")

        logger.info(f"Saved {len(self.all_events_log)} raw events to {output_path}")
        return output_path

    def clear_all_events(self) -> None:
        """Clear all stored events and raw event logs."""
        self.events.clear()
        self.all_events_log.clear()
        logger.debug("Cleared all stored events")
