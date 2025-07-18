"""Container performance tests.

This module contains tests for measuring container startup and shutdown
performance using the performance testing framework.
"""

import logging
import pytest
from pathlib import Path
from typing import Dict, Any

from unified.performance.test_runner import PerformanceTestRunner

logger = logging.getLogger(__name__)


class TestContainerPerformance:
    """Test container performance metrics."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.project_dir = Path(__file__).parent.parent.parent
        self.runner = PerformanceTestRunner(self.project_dir)
        
        # Configure for faster testing
        self.runner.configure_test(
            test_iterations=2,
            warmup_iterations=1,
            startup_timeout=180,
            cooldown_time=5
        )
    
    def teardown_method(self):
        """Cleanup after tests."""
        # Ensure monitoring is stopped
        self.runner.event_monitor.stop_monitoring()
        self.runner.health_watcher.stop_monitoring()
    
    @pytest.mark.parametrize("environment", ["test-env-1", "test-env-2"])
    def test_environment_startup_performance(self, environment: str):
        """Test startup performance for test environments.
        
        Args:
            environment: Environment name to test
        """
        logger.info(f"Testing startup performance for {environment}")
        
        # Run performance test
        results = self.runner.run_environment_performance_test(
            environment, 
            iterations=2, 
            include_warmup=True
        )
        
        # Verify test completed successfully
        assert "error" not in results, f"Performance test failed: {results.get('error')}"
        assert results["iterations"] == 2
        assert len(results["results"]) == 2
        
        # Verify all iterations were successful
        for i, result in enumerate(results["results"]):
            assert result["startup_success"], f"Iteration {i+1} startup failed"
            assert result["startup_time"] > 0, f"Invalid startup time for iteration {i+1}"
        
        # Check summary statistics
        summary = results["summary"]
        assert summary["successful_iterations"] == 2
        assert summary["success_rate"] == 1.0
        assert "startup_times" in summary
        
        # Performance assertions
        avg_startup = summary["startup_times"]["average"]
        max_startup = summary["startup_times"]["max"]
        
        # Log performance metrics
        logger.info(f"Average startup time: {avg_startup:.2f}s")
        logger.info(f"Maximum startup time: {max_startup:.2f}s")
        
        # Performance thresholds (adjust based on your requirements)
        assert avg_startup < 120, f"Average startup time too high: {avg_startup:.2f}s"
        assert max_startup < 180, f"Maximum startup time too high: {max_startup:.2f}s"
    
    def test_container_health_check_performance(self):
        """Test health check performance measurement."""
        environment = "test-env-1"
        
        # Run single iteration to test health check monitoring
        results = self.runner.run_environment_performance_test(
            environment, 
            iterations=1, 
            include_warmup=False
        )
        
        # Verify health check data was collected
        assert "error" not in results
        assert len(results["results"]) == 1
        
        result = results["results"][0]
        assert "healthy_times" in result
        assert len(result["healthy_times"]) > 0
        
        # Check that all containers reported healthy times
        for container_name, healthy_time in result["healthy_times"].items():
            assert healthy_time > 0, f"Container {container_name} has invalid healthy time"
            assert healthy_time < 120, f"Container {container_name} took too long to become healthy: {healthy_time:.2f}s"
            
            logger.info(f"Container {container_name} healthy time: {healthy_time:.2f}s")
    
    def test_startup_performance_consistency(self):
        """Test that startup performance is consistent across iterations."""
        environment = "test-env-1"
        
        # Run multiple iterations
        results = self.runner.run_environment_performance_test(
            environment, 
            iterations=3, 
            include_warmup=True
        )
        
        assert "error" not in results
        assert results["summary"]["successful_iterations"] == 3
        
        # Check consistency of startup times
        startup_times = results["summary"]["startup_times"]["values"]
        avg_startup = results["summary"]["startup_times"]["average"]
        
        # Calculate coefficient of variation (std dev / mean)
        import statistics
        std_dev = statistics.stdev(startup_times)
        cv = std_dev / avg_startup
        
        logger.info(f"Startup time consistency - CV: {cv:.2f}, std dev: {std_dev:.2f}s")
        
        # Assert reasonable consistency (CV < 0.3 means std dev is < 30% of mean)
        assert cv < 0.3, f"Startup times are too inconsistent: CV={cv:.2f}"
    
    def test_performance_data_collection(self):
        """Test that performance data is properly collected."""
        environment = "test-env-1"
        
        # Run performance test
        results = self.runner.run_environment_performance_test(
            environment, 
            iterations=1, 
            include_warmup=False
        )
        
        assert "error" not in results
        
        # Check that performance data was collected
        collector = self.runner.performance_collector
        assert environment in collector.environments
        
        env_metrics = collector.environments[environment]
        assert len(env_metrics.containers) > 0
        
        # Check container metrics
        for container_name, container_metrics in env_metrics.containers.items():
            metrics = container_metrics.metrics
            
            # Verify key metrics are present
            assert "create_time" in metrics
            assert "start_time" in metrics
            
            # Check for startup duration if health checks are available
            if metrics.get("health_healthy_time"):
                assert metrics.get("startup_duration") is not None
                assert metrics["startup_duration"] > 0
            
            logger.info(f"Container {container_name} metrics: {metrics}")
    
    def test_environment_comparison(self):
        """Test comparing performance between environments."""
        environments = ["test-env-1", "test-env-2"]
        
        # Run tests for both environments
        all_results = {}
        for env in environments:
            results = self.runner.run_environment_performance_test(
                env, 
                iterations=2, 
                include_warmup=True
            )
            all_results[env] = results
        
        # Compare performance between environments
        for env in environments:
            assert "error" not in all_results[env]
            assert all_results[env]["summary"]["successful_iterations"] == 2
        
        # Extract average startup times
        startup_times = {}
        for env in environments:
            startup_times[env] = all_results[env]["summary"]["startup_times"]["average"]
        
        # Log comparison
        for env, avg_time in startup_times.items():
            logger.info(f"Environment {env} average startup time: {avg_time:.2f}s")
        
        # Check that both environments perform reasonably well
        for env, avg_time in startup_times.items():
            assert avg_time < 120, f"Environment {env} startup time too high: {avg_time:.2f}s"
    
    def test_performance_regression_detection(self):
        """Test performance regression detection capability."""
        environment = "test-env-1"
        
        # Run initial test to establish baseline
        results = self.runner.run_environment_performance_test(
            environment, 
            iterations=2, 
            include_warmup=True
        )
        
        assert "error" not in results
        
        # Save as baseline
        collector = self.runner.performance_collector
        collector.save_baselines()
        
        # Run another test
        results2 = self.runner.run_environment_performance_test(
            environment, 
            iterations=2, 
            include_warmup=True
        )
        
        assert "error" not in results2
        
        # Compare to baseline
        comparison = collector.compare_to_baseline(environment)
        
        assert comparison["has_baseline"]
        assert "startup_time_change" in comparison["summary"]
        
        logger.info(f"Performance comparison: {comparison}")
    
    @pytest.mark.slow
    def test_comprehensive_performance_report(self):
        """Test generating comprehensive performance report."""
        # Run tests for multiple environments
        environments = ["test-env-1", "test-env-2"]
        
        for env in environments:
            results = self.runner.run_environment_performance_test(
                env, 
                iterations=1, 
                include_warmup=False
            )
            assert "error" not in results
        
        # Generate comprehensive report
        collector = self.runner.performance_collector
        report = collector.generate_performance_report()
        
        # Verify report structure
        assert "timestamp" in report
        assert "summary" in report
        assert "environments" in report
        assert "recommendations" in report
        
        # Check summary
        summary = report["summary"]
        assert summary["total_environments"] == len(environments)
        assert summary["total_containers"] > 0
        
        # Check environment details
        for env in environments:
            assert env in report["environments"]
            env_data = report["environments"][env]
            assert "metrics" in env_data
            assert "containers" in env_data
            assert env_data["container_count"] > 0
        
        logger.info(f"Performance report generated with {len(report['recommendations'])} recommendations")
    
    def test_save_performance_results(self):
        """Test saving performance results to files."""
        environment = "test-env-1"
        
        # Run performance test
        results = self.runner.run_environment_performance_test(
            environment, 
            iterations=1, 
            include_warmup=False
        )
        
        assert "error" not in results
        
        # Save results
        results_file = self.runner.save_results(results)
        
        # Verify file was created
        assert results_file.exists()
        assert results_file.suffix == ".json"
        
        # Verify performance data was also saved
        performance_files = list(self.runner.output_dir.glob("lifecycle-performance-*.json"))
        assert len(performance_files) > 0
        
        logger.info(f"Results saved to {results_file}")
        logger.info(f"Performance data files: {performance_files}")


class TestPerformanceMonitoring:
    """Test performance monitoring components."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.project_dir = Path(__file__).parent.parent.parent
        self.runner = PerformanceTestRunner(self.project_dir)
    
    def teardown_method(self):
        """Cleanup after tests."""
        self.runner.event_monitor.stop_monitoring()
        self.runner.health_watcher.stop_monitoring()
    
    def test_event_monitor_functionality(self):
        """Test that event monitor captures container events."""
        from unified.performance.event_monitor import ContainerEventMonitor
        
        monitor = ContainerEventMonitor()
        
        # Test adding container filters
        monitor.add_container_filter("test-container")
        assert "test-container" in monitor.container_filters
        
        # Test event collection setup
        events_collected = []
        monitor.add_event_callback(lambda event: events_collected.append(event))
        
        # Start monitoring briefly
        monitor.start_monitoring()
        assert monitor.monitoring
        
        # Stop monitoring
        monitor.stop_monitoring()
        assert not monitor.monitoring
        
        # Test event summary
        summary = monitor.get_event_summary()
        assert "total_events" in summary
        assert "containers" in summary
        assert "event_types" in summary
    
    def test_health_watcher_functionality(self):
        """Test that health watcher monitors container health."""
        from unified.performance.health_watcher import HealthCheckWatcher
        
        watcher = HealthCheckWatcher()
        
        # Test adding containers (will fail to resolve IDs but that's ok for test)
        watcher.add_container("test-container")
        
        # Test health status tracking
        health_changes = []
        watcher.add_health_callback(lambda status: health_changes.append(status))
        
        # Start monitoring briefly
        watcher.start_monitoring()
        assert watcher.monitoring
        
        # Stop monitoring
        watcher.stop_monitoring()
        assert not watcher.monitoring
        
        # Test health summary
        summary = watcher.get_health_summary()
        assert "monitored_containers" in summary
        assert "total_health_records" in summary
        assert "current_status" in summary
    
    def test_performance_collector_functionality(self):
        """Test performance data collection and aggregation."""
        from unified.performance.performance_collector import PerformanceCollector
        
        collector = PerformanceCollector()
        
        # Test adding environments
        env_metrics = collector.add_environment("test-env")
        assert env_metrics.environment_name == "test-env"
        assert "test-env" in collector.environments
        
        # Test adding containers
        container_metrics = env_metrics.add_container("test-container", "test-image")
        assert container_metrics.container_name == "test-container"
        assert container_metrics.image == "test-image"
        
        # Test environment finalization
        collector.finalize_environment("test-env")
        assert env_metrics.end_time is not None
        
        # Test performance report generation
        report = collector.generate_performance_report()
        assert "timestamp" in report
        assert "summary" in report
        assert "environments" in report
        assert "test-env" in report["environments"]