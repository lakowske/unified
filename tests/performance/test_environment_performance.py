"""Environment performance tests.

This module contains tests for measuring full environment startup and shutdown
performance, including multi-container orchestration and service dependencies.
"""

import logging
import pytest
from pathlib import Path
from typing import Dict, Any

from unified.performance.test_runner import PerformanceTestRunner

logger = logging.getLogger(__name__)


class TestEnvironmentPerformance:
    """Test environment-level performance metrics."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.project_dir = Path(__file__).parent.parent.parent
        self.runner = PerformanceTestRunner(self.project_dir)
        
        # Configure for comprehensive testing
        self.runner.configure_test(
            test_iterations=2,
            warmup_iterations=1,
            startup_timeout=300,
            shutdown_timeout=60,
            cooldown_time=10
        )
    
    def teardown_method(self):
        """Cleanup after tests."""
        self.runner.event_monitor.stop_monitoring()
        self.runner.health_watcher.stop_monitoring()
    
    def test_full_environment_lifecycle(self):
        """Test complete environment lifecycle performance."""
        environment = "test-env-1"
        
        logger.info(f"Testing full lifecycle performance for {environment}")
        
        # Run comprehensive performance test
        results = self.runner.run_environment_performance_test(
            environment, 
            iterations=2, 
            include_warmup=True
        )
        
        # Verify test completed successfully
        assert "error" not in results, f"Performance test failed: {results.get('error')}"
        assert results["iterations"] == 2
        assert len(results["results"]) == 2
        
        # Verify lifecycle phases
        for i, result in enumerate(results["results"]):
            # Startup phase
            assert result["startup_success"], f"Iteration {i+1} startup failed"
            assert result["startup_time"] > 0, f"Invalid startup time for iteration {i+1}"
            
            # Shutdown phase
            assert result["shutdown_success"], f"Iteration {i+1} shutdown failed"
            assert result["shutdown_time"] > 0, f"Invalid shutdown time for iteration {i+1}"
            
            # Cleanup phase
            assert result["cleanup_success"], f"Iteration {i+1} cleanup failed"
            
            # Container health
            assert "healthy_times" in result
            assert len(result["healthy_times"]) > 0, f"No healthy times recorded for iteration {i+1}"
        
        # Performance analysis
        summary = results["summary"]
        avg_startup = summary["startup_times"]["average"]
        avg_shutdown = summary["shutdown_times"]["average"]
        
        logger.info(f"Average startup time: {avg_startup:.2f}s")
        logger.info(f"Average shutdown time: {avg_shutdown:.2f}s")
        
        # Performance assertions
        assert avg_startup < 180, f"Average startup time too high: {avg_startup:.2f}s"
        assert avg_shutdown < 30, f"Average shutdown time too high: {avg_shutdown:.2f}s"
    
    def test_service_dependency_performance(self):
        """Test performance of service startup dependencies."""
        environment = "test-env-1"
        
        results = self.runner.run_environment_performance_test(
            environment, 
            iterations=1, 
            include_warmup=False
        )
        
        assert "error" not in results
        result = results["results"][0]
        
        # Analyze container startup order and timing
        healthy_times = result["healthy_times"]
        startup_performance = result.get("startup_performance", {})
        
        # Log container startup times
        for container_name, healthy_time in healthy_times.items():
            logger.info(f"Container {container_name} startup time: {healthy_time:.2f}s")
        
        # Verify all expected services started
        expected_services = ["postgres", "apache", "mail", "bind", "flyway", "volume-setup"]
        actual_containers = list(healthy_times.keys())
        
        # Check that we have containers for most expected services
        # (Note: flyway and volume-setup might not show up in healthy times if they're one-shot)
        core_services = ["postgres", "apache", "mail", "bind"]
        core_containers = [c for c in actual_containers if any(service in c for service in core_services)]
        
        assert len(core_containers) >= 3, f"Not enough core services started: {core_containers}"
        
        # Check startup performance data
        if startup_performance:
            container_metrics = startup_performance.get("container_metrics", {})
            
            for container_name, metrics in container_metrics.items():
                startup_duration = metrics.get("startup_duration")
                if startup_duration:
                    assert startup_duration > 0, f"Invalid startup duration for {container_name}"
                    logger.info(f"Container {container_name} detailed startup: {startup_duration:.2f}s")
    
    def test_environment_scaling_performance(self):
        """Test performance when running multiple environments."""
        environments = ["test-env-1", "test-env-2"]
        
        logger.info("Testing scaling performance with multiple environments")
        
        # Test environments sequentially to avoid resource conflicts
        results = {}
        for env in environments:
            logger.info(f"Testing environment: {env}")
            
            env_results = self.runner.run_environment_performance_test(
                env, 
                iterations=1, 
                include_warmup=False
            )
            
            results[env] = env_results
            assert "error" not in env_results, f"Environment {env} failed: {env_results.get('error')}"
        
        # Compare performance across environments
        startup_times = {}
        for env, env_results in results.items():
            startup_times[env] = env_results["summary"]["startup_times"]["average"]
        
        # Log performance comparison
        for env, startup_time in startup_times.items():
            logger.info(f"Environment {env} average startup: {startup_time:.2f}s")
        
        # Check that environments perform similarly (within reasonable variance)
        startup_values = list(startup_times.values())
        max_startup = max(startup_values)
        min_startup = min(startup_values)
        
        # Allow up to 50% difference between environments
        performance_variance = (max_startup - min_startup) / min_startup
        assert performance_variance < 0.5, f"Too much variance between environments: {performance_variance:.2f}"
    
    def test_resource_cleanup_performance(self):
        """Test performance of resource cleanup operations."""
        environment = "test-env-1"
        
        results = self.runner.run_environment_performance_test(
            environment, 
            iterations=1, 
            include_warmup=False
        )
        
        assert "error" not in results
        result = results["results"][0]
        
        # Check cleanup performance
        assert result["cleanup_success"], "Cleanup failed"
        
        # Verify timing
        startup_time = result["startup_time"]
        shutdown_time = result["shutdown_time"]
        
        logger.info(f"Startup time: {startup_time:.2f}s")
        logger.info(f"Shutdown time: {shutdown_time:.2f}s")
        
        # Cleanup should be faster than startup
        assert shutdown_time < startup_time, "Shutdown took longer than startup"
        
        # Reasonable cleanup time
        assert shutdown_time < 60, f"Cleanup took too long: {shutdown_time:.2f}s"
    
    def test_performance_under_load(self):
        """Test performance under repeated load."""
        environment = "test-env-1"
        
        # Run multiple iterations to simulate load
        results = self.runner.run_environment_performance_test(
            environment, 
            iterations=3, 
            include_warmup=True
        )
        
        assert "error" not in results
        assert results["summary"]["successful_iterations"] == 3
        
        # Analyze performance under load
        startup_times = results["summary"]["startup_times"]["values"]
        
        # Check for performance degradation
        first_startup = startup_times[0]
        last_startup = startup_times[-1]
        
        # Performance should not degrade significantly
        degradation = (last_startup - first_startup) / first_startup
        
        logger.info(f"Performance degradation: {degradation:.2%}")
        logger.info(f"Startup times: {[f'{t:.2f}s' for t in startup_times]}")
        
        # Allow up to 20% degradation
        assert degradation < 0.2, f"Performance degraded too much: {degradation:.2%}"
    
    def test_environment_health_monitoring(self):
        """Test health monitoring during environment startup."""
        environment = "test-env-1"
        
        results = self.runner.run_environment_performance_test(
            environment, 
            iterations=1, 
            include_warmup=False
        )
        
        assert "error" not in results
        
        # Check health monitoring data
        collector = self.runner.performance_collector
        env_metrics = collector.environments[environment]
        
        # Verify health data was collected
        health_failures = 0
        for container_name, container_metrics in env_metrics.containers.items():
            failures = container_metrics.metrics.get("health_check_failures", 0)
            health_failures += failures
            
            if failures > 0:
                logger.warning(f"Container {container_name} had {failures} health check failures")
        
        # Health failure rate should be low
        total_containers = len(env_metrics.containers)
        failure_rate = health_failures / max(total_containers, 1)
        
        assert failure_rate < 0.1, f"Health check failure rate too high: {failure_rate:.2%}"
    
    def test_environment_performance_baseline(self):
        """Test establishing and using performance baselines."""
        environment = "test-env-1"
        
        # Run initial test
        results1 = self.runner.run_environment_performance_test(
            environment, 
            iterations=2, 
            include_warmup=True
        )
        
        assert "error" not in results1
        
        # Save as baseline
        collector = self.runner.performance_collector
        collector.save_baselines()
        
        # Run second test
        results2 = self.runner.run_environment_performance_test(
            environment, 
            iterations=2, 
            include_warmup=True
        )
        
        assert "error" not in results2
        
        # Compare to baseline
        comparison = collector.compare_to_baseline(environment)
        
        assert comparison["has_baseline"], "Baseline not found"
        assert "startup_time_change" in comparison["summary"]
        
        change = comparison["summary"]["startup_time_change"]
        logger.info(f"Performance change from baseline: {change:.1f}%")
        
        # Log any improvements or regressions
        if comparison["improvements"]:
            logger.info(f"Improvements: {comparison['improvements']}")
        if comparison["regressions"]:
            logger.warning(f"Regressions: {comparison['regressions']}")
    
    @pytest.mark.slow
    def test_comprehensive_environment_analysis(self):
        """Test comprehensive environment performance analysis."""
        environments = ["test-env-1", "test-env-2"]
        
        # Run comprehensive test across all environments
        combined_results = self.runner.run_all_environments_test(environments)
        
        # Verify all environments tested successfully
        assert combined_results["environments"] == environments
        
        for env in environments:
            env_result = combined_results["results"][env]
            assert "error" not in env_result, f"Environment {env} failed"
            assert env_result["summary"]["successful_iterations"] > 0
        
        # Check overall summary
        summary = combined_results["summary"]
        assert summary["total_environments"] == len(environments)
        assert summary["successful_environments"] == len(environments)
        assert summary["failed_environments"] == 0
        
        # Performance analysis
        if "slowest_environment" in summary:
            slowest = summary["slowest_environment"]
            fastest = summary["fastest_environment"]
            
            logger.info(f"Slowest environment: {slowest['name']} ({slowest['startup_time']:.2f}s)")
            logger.info(f"Fastest environment: {fastest['name']} ({fastest['startup_time']:.2f}s)")
            
            # Performance difference should be reasonable
            performance_ratio = slowest["startup_time"] / fastest["startup_time"]
            assert performance_ratio < 2.0, f"Performance difference too large: {performance_ratio:.2f}x"
    
    def test_performance_report_generation(self):
        """Test generation of detailed performance reports."""
        environment = "test-env-1"
        
        # Run test
        results = self.runner.run_environment_performance_test(
            environment, 
            iterations=2, 
            include_warmup=True
        )
        
        assert "error" not in results
        
        # Generate performance report
        collector = self.runner.performance_collector
        report = collector.generate_performance_report()
        
        # Verify report structure
        assert "timestamp" in report
        assert "summary" in report
        assert "environments" in report
        assert "recommendations" in report
        
        # Check environment-specific data
        assert environment in report["environments"]
        env_data = report["environments"][environment]
        
        assert "metrics" in env_data
        assert "containers" in env_data
        assert env_data["container_count"] > 0
        
        # Check for performance recommendations
        recommendations = report["recommendations"]
        logger.info(f"Performance recommendations: {recommendations}")
        
        # Save report
        results_file = self.runner.save_results(results)
        assert results_file.exists()
        
        logger.info(f"Performance report saved to: {results_file}")
    
    def test_environment_optimization_insights(self):
        """Test generation of optimization insights."""
        environment = "test-env-1"
        
        # Run performance test
        results = self.runner.run_environment_performance_test(
            environment, 
            iterations=2, 
            include_warmup=True
        )
        
        assert "error" not in results
        
        # Analyze for optimization opportunities
        summary = results["summary"]
        container_times = summary.get("container_healthy_times", {})
        
        # Identify slowest containers
        slowest_containers = []
        for container_name, times_data in container_times.items():
            avg_time = times_data["average"]
            if avg_time > 30:  # Containers taking more than 30s
                slowest_containers.append((container_name, avg_time))
        
        # Log optimization insights
        if slowest_containers:
            slowest_containers.sort(key=lambda x: x[1], reverse=True)
            logger.info("Optimization opportunities:")
            for container_name, avg_time in slowest_containers:
                logger.info(f"  - {container_name}: {avg_time:.2f}s startup time")
        
        # Check for consistency issues
        for container_name, times_data in container_times.items():
            values = times_data["values"]
            if len(values) > 1:
                import statistics
                std_dev = statistics.stdev(values)
                cv = std_dev / times_data["average"]
                
                if cv > 0.2:  # High variability
                    logger.warning(f"Container {container_name} has inconsistent startup times (CV: {cv:.2f})")
        
        # Environment-level insights
        env_avg_startup = summary["startup_times"]["average"]
        if env_avg_startup > 120:
            logger.warning(f"Environment {environment} has slow startup time: {env_avg_startup:.2f}s")
        
        # Generate actionable recommendations
        recommendations = []
        
        if slowest_containers:
            slowest_name, slowest_time = slowest_containers[0]
            recommendations.append(f"Optimize {slowest_name} startup (currently {slowest_time:.2f}s)")
        
        if env_avg_startup > 60:
            recommendations.append("Consider parallel service startup to reduce overall time")
        
        logger.info(f"Recommendations: {recommendations}")