"""Performance data collection and aggregation.

This module provides functionality to collect, aggregate, and analyze performance
data from container lifecycle events and health checks.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .event_monitor import ContainerEvent, ContainerEventMonitor
from .health_watcher import HealthCheckWatcher, HealthStatus

logger = logging.getLogger(__name__)


class ContainerPerformanceMetrics:
    """Performance metrics for a single container."""
    
    def __init__(self, container_name: str, image: str = ""):
        self.container_name = container_name
        self.image = image
        self.metrics = {
            "create_time": None,
            "start_time": None,
            "health_starting_time": None,
            "health_healthy_time": None,
            "health_unhealthy_time": None,
            "stop_time": None,
            "destroy_time": None,
            "startup_duration": None,
            "health_check_duration": None,
            "total_startup_time": None,
            "shutdown_duration": None,
            "health_check_failures": 0,
            "restart_count": 0
        }
        self.events: List[ContainerEvent] = []
        self.health_history: List[HealthStatus] = []
    
    def add_event(self, event: ContainerEvent) -> None:
        """Add a container event to the metrics.
        
        Args:
            event: Container event to add
        """
        self.events.append(event)
        
        # Update container image if not set and event has it
        if not self.image and event.image:
            self.image = event.image
        
        # Update metrics based on event type
        if event.action == "create":
            self.metrics["create_time"] = event.timestamp
        elif event.action == "start":
            self.metrics["start_time"] = event.timestamp
        elif event.action == "restart":
            self.metrics["restart_count"] += 1
        elif event.action in ["stop", "kill", "die"]:
            self.metrics["stop_time"] = event.timestamp
        elif event.action == "destroy":
            self.metrics["destroy_time"] = event.timestamp
        elif event.action == "health_status":
            # Parse health status from event
            attrs = event.raw_data.get("Actor", {}).get("Attributes", {})
            health_status = attrs.get("health_status", "")
            if health_status == "starting":
                self.metrics["health_starting_time"] = event.timestamp
            elif health_status == "healthy":
                self.metrics["health_healthy_time"] = event.timestamp
            elif health_status == "unhealthy":
                self.metrics["health_unhealthy_time"] = event.timestamp
                self.metrics["health_check_failures"] += 1
        
        # Recalculate derived metrics
        self._calculate_derived_metrics()
    
    def add_health_status(self, health_status: HealthStatus) -> None:
        """Add a health status record to the metrics.
        
        Args:
            health_status: Health status to add
        """
        self.health_history.append(health_status)
        
        # Update metrics based on health status
        if health_status.status == "starting":
            self.metrics["health_starting_time"] = health_status.timestamp
        elif health_status.status == "healthy":
            self.metrics["health_healthy_time"] = health_status.timestamp
        elif health_status.status == "unhealthy":
            self.metrics["health_unhealthy_time"] = health_status.timestamp
            self.metrics["health_check_failures"] += 1
        
        # Recalculate derived metrics
        self._calculate_derived_metrics()
    
    def _calculate_derived_metrics(self) -> None:
        """Calculate derived performance metrics."""
        # Calculate startup duration (start to healthy)
        start_time = self.metrics.get("start_time")
        healthy_time = self.metrics.get("health_healthy_time")
        
        if start_time and healthy_time:
            self.metrics["startup_duration"] = (healthy_time - start_time).total_seconds()
        
        # Calculate health check duration (starting to healthy)
        starting_time = self.metrics.get("health_starting_time")
        if starting_time and healthy_time:
            self.metrics["health_check_duration"] = (healthy_time - starting_time).total_seconds()
        
        # Calculate total startup time (create to healthy)
        create_time = self.metrics.get("create_time")
        if create_time and healthy_time:
            self.metrics["total_startup_time"] = (healthy_time - create_time).total_seconds()
        elif create_time and start_time:
            # For containers without health checks, use create to start
            self.metrics["total_startup_time"] = (start_time - create_time).total_seconds()
        
        # Calculate shutdown duration (stop to destroy)
        stop_time = self.metrics.get("stop_time")
        destroy_time = self.metrics.get("destroy_time")
        
        if stop_time and destroy_time:
            self.metrics["shutdown_duration"] = (destroy_time - stop_time).total_seconds()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary representation.
        
        Returns:
            Dictionary representation of metrics
        """
        # Calculate derived metrics before serialization
        self._calculate_derived_metrics()
        
        # Convert datetime objects to ISO format strings
        serialized_metrics = {}
        for key, value in self.metrics.items():
            if isinstance(value, datetime):
                serialized_metrics[key] = value.isoformat()
            else:
                serialized_metrics[key] = value
        
        return {
            "container_name": self.container_name,
            "image": self.image,
            "metrics": serialized_metrics,
            "event_count": len(self.events),
            "health_record_count": len(self.health_history)
        }


class EnvironmentPerformanceMetrics:
    """Performance metrics for an entire environment."""
    
    def __init__(self, environment_name: str):
        self.environment_name = environment_name
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.containers: Dict[str, ContainerPerformanceMetrics] = {}
        self.environment_metrics = {
            "total_startup_time": None,
            "total_shutdown_time": None,
            "slowest_container": None,
            "fastest_container": None,
            "average_startup_time": None,
            "health_check_failure_rate": 0.0,
            "container_count": 0
        }
    
    def add_container(self, container_name: str, image: str = "") -> ContainerPerformanceMetrics:
        """Add a container to the environment metrics.
        
        Args:
            container_name: Name of the container
            image: Container image name
            
        Returns:
            Container performance metrics object
        """
        if container_name not in self.containers:
            self.containers[container_name] = ContainerPerformanceMetrics(container_name, image)
        
        return self.containers[container_name]
    
    def get_container(self, container_name: str) -> Optional[ContainerPerformanceMetrics]:
        """Get container metrics by name.
        
        Args:
            container_name: Name of the container
            
        Returns:
            Container metrics or None if not found
        """
        return self.containers.get(container_name)
    
    def calculate_environment_metrics(self) -> None:
        """Calculate environment-level performance metrics."""
        if not self.containers:
            return
        
        startup_times = []
        shutdown_times = []
        total_failures = 0
        
        for container_metrics in self.containers.values():
            metrics = container_metrics.metrics
            
            # Collect startup times
            if metrics.get("startup_duration"):
                startup_times.append(metrics["startup_duration"])
            
            # Collect shutdown times
            if metrics.get("shutdown_duration"):
                shutdown_times.append(metrics["shutdown_duration"])
            
            # Count health check failures
            total_failures += metrics.get("health_check_failures", 0)
        
        # Calculate environment metrics
        self.environment_metrics["container_count"] = len(self.containers)
        
        if startup_times:
            self.environment_metrics["total_startup_time"] = max(startup_times)
            self.environment_metrics["average_startup_time"] = sum(startup_times) / len(startup_times)
            
            # Find slowest and fastest containers
            slowest_time = max(startup_times)
            fastest_time = min(startup_times)
            
            for container_name, container_metrics in self.containers.items():
                if container_metrics.metrics.get("startup_duration") == slowest_time:
                    self.environment_metrics["slowest_container"] = container_name
                if container_metrics.metrics.get("startup_duration") == fastest_time:
                    self.environment_metrics["fastest_container"] = container_name
        
        if shutdown_times:
            self.environment_metrics["total_shutdown_time"] = max(shutdown_times)
        
        # Calculate health check failure rate
        total_health_checks = sum(len(c.health_history) for c in self.containers.values())
        if total_health_checks > 0:
            self.environment_metrics["health_check_failure_rate"] = total_failures / total_health_checks
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert environment metrics to dictionary representation.
        
        Returns:
            Dictionary representation of environment metrics
        """
        return {
            "environment_name": self.environment_name,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "environment_metrics": self.environment_metrics,
            "containers": {name: container.to_dict() for name, container in self.containers.items()}
        }


class PerformanceCollector:
    """Collects and aggregates performance data from multiple sources."""
    
    def __init__(self, output_dir: Optional[Path] = None):
        """Initialize performance collector.
        
        Args:
            output_dir: Directory to save performance data
        """
        self.output_dir = output_dir or Path("performance_data")
        self.output_dir.mkdir(exist_ok=True)
        
        self.environments: Dict[str, EnvironmentPerformanceMetrics] = {}
        self.baselines: Dict[str, Dict[str, float]] = {}
        
        # Load baseline data if it exists
        self._load_baselines()
    
    def add_environment(self, environment_name: str) -> EnvironmentPerformanceMetrics:
        """Add an environment for performance tracking.
        
        Args:
            environment_name: Name of the environment
            
        Returns:
            Environment performance metrics object
        """
        if environment_name not in self.environments:
            self.environments[environment_name] = EnvironmentPerformanceMetrics(environment_name)
        
        return self.environments[environment_name]
    
    def collect_from_event_monitor(self, event_monitor: ContainerEventMonitor, 
                                  environment_name: str) -> None:
        """Collect performance data from event monitor.
        
        Args:
            event_monitor: Event monitor to collect data from
            environment_name: Environment name
        """
        env_metrics = self.add_environment(environment_name)
        
        # Group events by container
        container_events: Dict[str, List[ContainerEvent]] = {}
        for event in event_monitor.events:
            if event.container_name:
                if event.container_name not in container_events:
                    container_events[event.container_name] = []
                container_events[event.container_name].append(event)
        
        # Add events to container metrics
        for container_name, events in container_events.items():
            container_metrics = env_metrics.add_container(container_name)
            for event in events:
                container_metrics.add_event(event)
    
    def collect_from_health_watcher(self, health_watcher: HealthCheckWatcher, 
                                   environment_name: str) -> None:
        """Collect performance data from health watcher.
        
        Args:
            health_watcher: Health watcher to collect data from
            environment_name: Environment name
        """
        env_metrics = self.add_environment(environment_name)
        
        # Group health history by container
        container_health: Dict[str, List[HealthStatus]] = {}
        for health_status in health_watcher.health_history:
            if health_status.container_name not in container_health:
                container_health[health_status.container_name] = []
            container_health[health_status.container_name].append(health_status)
        
        # Add health data to container metrics
        for container_name, health_history in container_health.items():
            container_metrics = env_metrics.add_container(container_name)
            for health_status in health_history:
                container_metrics.add_health_status(health_status)
    
    def finalize_environment(self, environment_name: str) -> None:
        """Finalize environment metrics and calculate derived values.
        
        Args:
            environment_name: Environment name
        """
        if environment_name in self.environments:
            env_metrics = self.environments[environment_name]
            env_metrics.end_time = datetime.now()
            env_metrics.calculate_environment_metrics()
    
    def save_performance_data(self, filename: Optional[str] = None) -> Path:
        """Save performance data to JSON file.
        
        Args:
            filename: Optional filename (default: lifecycle-performance.json)
            
        Returns:
            Path to saved file
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"lifecycle-performance-{timestamp}.json"
        
        output_path = self.output_dir / filename
        
        # Prepare data for serialization
        data = {
            "timestamp": datetime.now().isoformat(),
            "environments": {name: env.to_dict() for name, env in self.environments.items()},
            "baselines": self.baselines
        }
        
        # Save to JSON file
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Performance data saved to {output_path}")
        return output_path
    
    def load_performance_data(self, filename: Union[str, Path]) -> None:
        """Load performance data from JSON file.
        
        Args:
            filename: Path to JSON file
        """
        file_path = Path(filename)
        
        if not file_path.exists():
            logger.warning(f"Performance data file not found: {file_path}")
            return
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Load environments (simplified - just for reference)
            self.environments.clear()
            for env_name, env_data in data.get("environments", {}).items():
                env_metrics = EnvironmentPerformanceMetrics(env_name)
                if env_data.get("start_time"):
                    env_metrics.start_time = datetime.fromisoformat(env_data["start_time"])
                if env_data.get("end_time"):
                    env_metrics.end_time = datetime.fromisoformat(env_data["end_time"])
                env_metrics.environment_metrics = env_data.get("environment_metrics", {})
                self.environments[env_name] = env_metrics
            
            # Load baselines
            self.baselines = data.get("baselines", {})
            
            logger.info(f"Performance data loaded from {file_path}")
        
        except Exception as e:
            logger.error(f"Error loading performance data from {file_path}: {e}")
    
    def _load_baselines(self) -> None:
        """Load baseline performance data."""
        baseline_file = self.output_dir / "performance_baselines.json"
        
        if baseline_file.exists():
            try:
                with open(baseline_file, 'r') as f:
                    self.baselines = json.load(f)
                logger.info("Loaded performance baselines")
            except Exception as e:
                logger.error(f"Error loading baselines: {e}")
    
    def save_baselines(self) -> None:
        """Save current performance data as baselines."""
        baseline_file = self.output_dir / "performance_baselines.json"
        
        # Calculate baselines from current data
        new_baselines = {}
        
        for env_name, env_metrics in self.environments.items():
            env_baselines = {}
            
            # Calculate average startup times
            startup_times = []
            for container_metrics in env_metrics.containers.values():
                startup_duration = container_metrics.metrics.get("startup_duration")
                if startup_duration:
                    startup_times.append(startup_duration)
            
            if startup_times:
                env_baselines["average_startup_time"] = sum(startup_times) / len(startup_times)
                env_baselines["max_startup_time"] = max(startup_times)
                env_baselines["min_startup_time"] = min(startup_times)
            
            if env_baselines:
                new_baselines[env_name] = env_baselines
        
        # Update baselines
        self.baselines.update(new_baselines)
        
        # Save to file
        try:
            with open(baseline_file, 'w') as f:
                json.dump(self.baselines, f, indent=2)
            logger.info(f"Baselines saved to {baseline_file}")
        except Exception as e:
            logger.error(f"Error saving baselines: {e}")
    
    def compare_to_baseline(self, environment_name: str) -> Dict[str, Any]:
        """Compare current performance to baseline.
        
        Args:
            environment_name: Environment name
            
        Returns:
            Comparison results
        """
        comparison = {
            "environment": environment_name,
            "has_baseline": environment_name in self.baselines,
            "performance_regression": False,
            "improvements": [],
            "regressions": [],
            "summary": {}
        }
        
        if environment_name not in self.environments:
            comparison["error"] = "Environment not found"
            return comparison
        
        env_metrics = self.environments[environment_name]
        baseline = self.baselines.get(environment_name, {})
        
        if not baseline:
            comparison["error"] = "No baseline available"
            return comparison
        
        # Compare average startup time
        current_avg = env_metrics.environment_metrics.get("average_startup_time")
        baseline_avg = baseline.get("average_startup_time")
        
        if current_avg and baseline_avg:
            improvement = ((baseline_avg - current_avg) / baseline_avg) * 100
            comparison["summary"]["startup_time_change"] = improvement
            
            if improvement > 5:  # 5% improvement threshold
                comparison["improvements"].append(f"Startup time improved by {improvement:.1f}%")
            elif improvement < -5:  # 5% regression threshold
                comparison["regressions"].append(f"Startup time regressed by {-improvement:.1f}%")
                comparison["performance_regression"] = True
        
        return comparison
    
    def generate_performance_report(self) -> Dict[str, Any]:
        """Generate a comprehensive performance report.
        
        Returns:
            Performance report dictionary
        """
        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_environments": len(self.environments),
                "total_containers": sum(len(env.containers) for env in self.environments.values()),
                "has_baselines": len(self.baselines) > 0
            },
            "environments": {},
            "recommendations": []
        }
        
        # Add environment details
        for env_name, env_metrics in self.environments.items():
            env_report = {
                "metrics": env_metrics.environment_metrics,
                "container_count": len(env_metrics.containers),
                "containers": {}
            }
            
            # Add container details
            for container_name, container_metrics in env_metrics.containers.items():
                env_report["containers"][container_name] = {
                    "startup_duration": container_metrics.metrics.get("startup_duration"),
                    "health_check_failures": container_metrics.metrics.get("health_check_failures"),
                    "restart_count": container_metrics.metrics.get("restart_count")
                }
            
            report["environments"][env_name] = env_report
        
        # Add recommendations
        self._add_performance_recommendations(report)
        
        return report
    
    def _add_performance_recommendations(self, report: Dict[str, Any]) -> None:
        """Add performance recommendations to report.
        
        Args:
            report: Report dictionary to add recommendations to
        """
        recommendations = []
        
        for env_name, env_data in report["environments"].items():
            metrics = env_data["metrics"]
            
            # Check for slow startup times
            avg_startup = metrics.get("average_startup_time")
            if avg_startup and avg_startup > 60:  # 60 seconds threshold
                recommendations.append(f"Environment {env_name} has slow average startup time ({avg_startup:.1f}s)")
            
            # Check for health check failures
            failure_rate = metrics.get("health_check_failure_rate", 0)
            if failure_rate > 0.1:  # 10% failure rate threshold
                recommendations.append(f"Environment {env_name} has high health check failure rate ({failure_rate:.1%})")
            
            # Check for container restarts
            for container_name, container_data in env_data["containers"].items():
                restart_count = container_data.get("restart_count", 0)
                if restart_count > 0:
                    recommendations.append(f"Container {container_name} in {env_name} has {restart_count} restarts")
        
        report["recommendations"] = recommendations