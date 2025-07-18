"""Test data management utilities for static environment testing.

This module provides utilities for managing test data, validating test
configurations, and setting up test environments with static data.
"""
import json
import logging
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import pytest

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestDataManager:
    """Manages test data and validation for static environments."""
    
    def __init__(self, project_dir: Path) -> None:
        """Initialize test data manager.
        
        Args:
            project_dir: Path to the project root directory
        """
        self.project_dir = project_dir
        self.test_data_dir = project_dir / "test_data"
        self.environments_dir = self.test_data_dir / "environments"
        self.validation_dir = self.test_data_dir / "validation"
        self.fixtures_dir = self.test_data_dir / "fixtures"
    
    def validate_test_data_structure(self) -> Dict[str, Any]:
        """Validate the test data directory structure.
        
        Returns:
            Dictionary with validation results
        """
        result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "structure": {}
        }
        
        # Check main directories
        required_dirs = [
            self.test_data_dir,
            self.environments_dir,
            self.validation_dir,
            self.fixtures_dir
        ]
        
        for dir_path in required_dirs:
            if not dir_path.exists():
                result["valid"] = False
                result["errors"].append(f"Missing directory: {dir_path}")
            else:
                result["structure"][dir_path.name] = "exists"
        
        # Check environment directories
        expected_environments = [
            "minimal",
            "full-stack",
            "port-conflict",
            "isolated-feature",
            "performance"
        ]
        
        for env_name in expected_environments:
            env_dir = self.environments_dir / env_name
            if not env_dir.exists():
                result["valid"] = False
                result["errors"].append(f"Missing environment directory: {env_dir}")
            else:
                # Check for required files
                required_files = [f".env.{env_name}", f"docker-compose.{env_name}.yml"]
                for file_name in required_files:
                    file_path = env_dir / file_name
                    if not file_path.exists():
                        result["errors"].append(f"Missing file: {file_path}")
        
        # Check validation files
        validation_files = [
            "expected_ports.json",
            "service_health.json",
            "startup_order.json"
        ]
        
        for file_name in validation_files:
            file_path = self.validation_dir / file_name
            if not file_path.exists():
                result["valid"] = False
                result["errors"].append(f"Missing validation file: {file_path}")
            else:
                # Validate JSON structure
                try:
                    with file_path.open() as f:
                        json.load(f)
                    result["structure"][file_name] = "valid_json"
                except json.JSONDecodeError as e:
                    result["valid"] = False
                    result["errors"].append(f"Invalid JSON in {file_path}: {e}")
        
        # Check fixture files
        fixture_files = [
            "test_users.json",
            "dns_records.json",
            "mail_config.json"
        ]
        
        for file_name in fixture_files:
            file_path = self.fixtures_dir / file_name
            if not file_path.exists():
                result["warnings"].append(f"Missing fixture file: {file_path}")
            else:
                try:
                    with file_path.open() as f:
                        json.load(f)
                    result["structure"][file_name] = "valid_json"
                except json.JSONDecodeError as e:
                    result["warnings"].append(f"Invalid JSON in {file_path}: {e}")
        
        return result
    
    def detect_port_conflicts(self) -> Dict[str, List[str]]:
        """Detect port conflicts between environments.
        
        Returns:
            Dictionary mapping ports to conflicting environments
        """
        conflicts = {}
        port_usage = {}
        
        # Load expected ports data
        expected_ports_file = self.validation_dir / "expected_ports.json"
        if not expected_ports_file.exists():
            return conflicts
        
        with expected_ports_file.open() as f:
            expected_ports = json.load(f)
        
        # Collect port usage
        for env_name, env_data in expected_ports["environments"].items():
            if "ports" in env_data:
                for service, port in env_data["ports"].items():
                    if port not in port_usage:
                        port_usage[port] = []
                    port_usage[port].append(f"{env_name}:{service}")
        
        # Identify conflicts
        for port, users in port_usage.items():
            if len(users) > 1:
                conflicts[str(port)] = users
        
        return conflicts
    
    def validate_environment_configuration(self, env_name: str) -> Dict[str, Any]:
        """Validate a specific environment configuration.
        
        Args:
            env_name: Name of the environment to validate
            
        Returns:
            Dictionary with validation results
        """
        result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "config": {}
        }
        
        env_dir = self.environments_dir / env_name
        if not env_dir.exists():
            result["valid"] = False
            result["errors"].append(f"Environment directory not found: {env_dir}")
            return result
        
        # Check environment file
        env_file = env_dir / f".env.{env_name}"
        if not env_file.exists():
            result["valid"] = False
            result["errors"].append(f"Environment file not found: {env_file}")
        else:
            # Parse environment file
            try:
                env_vars = {}
                with env_file.open() as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            if "=" in line:
                                key, value = line.split("=", 1)
                                env_vars[key] = value
                
                result["config"]["env_vars"] = env_vars
                
                # Validate required variables
                required_vars = ["ENVIRONMENT", "DB_NAME", "DB_USER", "DB_PASSWORD"]
                for var in required_vars:
                    if var not in env_vars:
                        result["warnings"].append(f"Missing required environment variable: {var}")
                
            except Exception as e:
                result["valid"] = False
                result["errors"].append(f"Error parsing environment file: {e}")
        
        # Check docker-compose file
        compose_file = env_dir / f"docker-compose.{env_name}.yml"
        if not compose_file.exists():
            result["valid"] = False
            result["errors"].append(f"Docker Compose file not found: {compose_file}")
        else:
            # Basic YAML validation
            try:
                import yaml
                with compose_file.open() as f:
                    compose_data = yaml.safe_load(f)
                
                result["config"]["compose"] = compose_data
                
                # Validate structure
                if "services" not in compose_data:
                    result["errors"].append("Docker Compose file missing 'services' section")
                elif not compose_data["services"]:
                    result["errors"].append("Docker Compose file has empty 'services' section")
                
            except ImportError:
                result["warnings"].append("PyYAML not available for Docker Compose validation")
            except Exception as e:
                result["valid"] = False
                result["errors"].append(f"Error parsing Docker Compose file: {e}")
        
        return result
    
    def generate_test_report(self) -> Dict[str, Any]:
        """Generate a comprehensive test data report.
        
        Returns:
            Dictionary with test data report
        """
        report = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "structure_validation": self.validate_test_data_structure(),
            "port_conflicts": self.detect_port_conflicts(),
            "environments": {},
            "summary": {
                "total_environments": 0,
                "valid_environments": 0,
                "total_ports": 0,
                "conflicting_ports": 0
            }
        }
        
        # Validate each environment
        environment_names = [
            "minimal",
            "full-stack",
            "feature-auth",
            "performance",
            "conflict1",
            "conflict2"
        ]
        
        valid_count = 0
        total_ports = set()
        
        for env_name in environment_names:
            env_validation = self.validate_environment_configuration(env_name)
            report["environments"][env_name] = env_validation
            
            if env_validation["valid"]:
                valid_count += 1
            
            # Count ports
            if "config" in env_validation and "env_vars" in env_validation["config"]:
                env_vars = env_validation["config"]["env_vars"]
                for key, value in env_vars.items():
                    if key.endswith("_PORT") and value.isdigit():
                        total_ports.add(int(value))
        
        report["summary"]["total_environments"] = len(environment_names)
        report["summary"]["valid_environments"] = valid_count
        report["summary"]["total_ports"] = len(total_ports)
        report["summary"]["conflicting_ports"] = len(report["port_conflicts"])
        
        return report
    
    def setup_test_environment(self, env_name: str) -> Dict[str, Any]:
        """Set up a test environment with proper data initialization.
        
        Args:
            env_name: Name of the environment to set up
            
        Returns:
            Dictionary with setup results
        """
        result = {
            "success": True,
            "environment": env_name,
            "steps": [],
            "errors": []
        }
        
        try:
            # Validate environment configuration
            validation = self.validate_environment_configuration(env_name)
            if not validation["valid"]:
                result["success"] = False
                result["errors"].extend(validation["errors"])
                return result
            
            result["steps"].append("Environment configuration validated")
            
            # Check for Docker availability
            try:
                subprocess.run(
                    ["docker", "--version"],
                    capture_output=True,
                    check=True,
                    timeout=10
                )
                result["steps"].append("Docker availability confirmed")
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                result["success"] = False
                result["errors"].append("Docker not available")
                return result
            
            # Build required container images if needed
            base_image = "localhost/unified/base-debian:latest"
            try:
                subprocess.run(
                    ["docker", "image", "inspect", base_image],
                    capture_output=True,
                    check=True,
                    timeout=10
                )
                result["steps"].append("Base container image available")
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                result["steps"].append("Base container image not found - would need to build")
            
            # Prepare environment-specific data
            env_dir = self.environments_dir / env_name
            env_file = env_dir / f".env.{env_name}"
            compose_file = env_dir / f"docker-compose.{env_name}.yml"
            
            if env_file.exists() and compose_file.exists():
                result["steps"].append("Environment files prepared")
            else:
                result["success"] = False
                result["errors"].append("Environment files not found")
                return result
            
            # Initialize test data if needed
            if env_name == "feature-auth":
                # Set up authentication test data
                auth_data = self._load_auth_test_data()
                if auth_data:
                    result["steps"].append("Authentication test data loaded")
                else:
                    result["steps"].append("Authentication test data not available")
            
            if env_name == "performance":
                # Set up performance test data
                perf_data = self._load_performance_test_data()
                if perf_data:
                    result["steps"].append("Performance test data loaded")
                else:
                    result["steps"].append("Performance test data not available")
            
            result["steps"].append("Test environment setup completed")
            
        except Exception as e:
            result["success"] = False
            result["errors"].append(f"Unexpected error during setup: {e}")
        
        return result
    
    def _load_auth_test_data(self) -> Optional[Dict[str, Any]]:
        """Load authentication test data."""
        try:
            users_file = self.fixtures_dir / "test_users.json"
            if users_file.exists():
                with users_file.open() as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Error loading auth test data: {e}")
        return None
    
    def _load_performance_test_data(self) -> Optional[Dict[str, Any]]:
        """Load performance test data."""
        try:
            # Load multiple test data files for performance testing
            test_data = {}
            
            # Load user data
            users_file = self.fixtures_dir / "test_users.json"
            if users_file.exists():
                with users_file.open() as f:
                    test_data["users"] = json.load(f)
            
            # Load DNS data
            dns_file = self.fixtures_dir / "dns_records.json"
            if dns_file.exists():
                with dns_file.open() as f:
                    test_data["dns"] = json.load(f)
            
            # Load mail data
            mail_file = self.fixtures_dir / "mail_config.json"
            if mail_file.exists():
                with mail_file.open() as f:
                    test_data["mail"] = json.load(f)
            
            return test_data if test_data else None
            
        except Exception as e:
            logger.warning(f"Error loading performance test data: {e}")
        return None
    
    def cleanup_test_environment(self, env_name: str) -> Dict[str, Any]:
        """Clean up a test environment and its data.
        
        Args:
            env_name: Name of the environment to clean up
            
        Returns:
            Dictionary with cleanup results
        """
        result = {
            "success": True,
            "environment": env_name,
            "steps": [],
            "errors": []
        }
        
        try:
            # Stop and remove containers
            container_prefix = f"{env_name}-"
            try:
                # Get containers with the environment prefix
                proc = subprocess.run(
                    ["docker", "ps", "-a", "--filter", f"name={container_prefix}", "--format", "{{.Names}}"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if proc.returncode == 0:
                    container_names = [name.strip() for name in proc.stdout.split("\n") if name.strip()]
                    
                    if container_names:
                        # Stop containers
                        subprocess.run(
                            ["docker", "stop"] + container_names,
                            capture_output=True,
                            timeout=60
                        )
                        
                        # Remove containers
                        subprocess.run(
                            ["docker", "rm"] + container_names,
                            capture_output=True,
                            timeout=30
                        )
                        
                        result["steps"].append(f"Removed {len(container_names)} containers")
                    else:
                        result["steps"].append("No containers found to remove")
                
            except subprocess.TimeoutExpired:
                result["errors"].append("Timeout during container cleanup")
            except Exception as e:
                result["errors"].append(f"Error during container cleanup: {e}")
            
            # Remove volumes
            try:
                volume_prefix = f"{env_name}-"
                proc = subprocess.run(
                    ["docker", "volume", "ls", "--filter", f"name={volume_prefix}", "--format", "{{.Name}}"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if proc.returncode == 0:
                    volume_names = [name.strip() for name in proc.stdout.split("\n") if name.strip()]
                    
                    if volume_names:
                        subprocess.run(
                            ["docker", "volume", "rm"] + volume_names,
                            capture_output=True,
                            timeout=30
                        )
                        result["steps"].append(f"Removed {len(volume_names)} volumes")
                    else:
                        result["steps"].append("No volumes found to remove")
                
            except subprocess.TimeoutExpired:
                result["errors"].append("Timeout during volume cleanup")
            except Exception as e:
                result["errors"].append(f"Error during volume cleanup: {e}")
            
            # Clean up temporary test data
            temp_dir = self.test_data_dir / "temp" / env_name
            if temp_dir.exists():
                import shutil
                shutil.rmtree(temp_dir)
                result["steps"].append("Removed temporary test data")
            
            result["steps"].append("Test environment cleanup completed")
            
        except Exception as e:
            result["success"] = False
            result["errors"].append(f"Unexpected error during cleanup: {e}")
        
        return result


class TestStaticDataManagement:
    """Test suite for static data management utilities."""
    
    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.project_dir = Path(__file__).parent.parent.parent
        self.manager = TestDataManager(self.project_dir)
    
    def test_test_data_structure_validation(self) -> None:
        """Test validation of test data directory structure."""
        result = self.manager.validate_test_data_structure()
        
        # Check that validation runs without errors
        assert isinstance(result, dict)
        assert "valid" in result
        assert "errors" in result
        assert "warnings" in result
        assert "structure" in result
        
        # If validation fails, log the errors for debugging
        if not result["valid"]:
            logger.error(f"Test data structure validation failed: {result['errors']}")
        
        # The result should be valid if all test data is properly set up
        assert result["valid"], f"Test data structure validation failed: {result['errors']}"
    
    def test_port_conflict_detection(self) -> None:
        """Test detection of port conflicts."""
        conflicts = self.manager.detect_port_conflicts()
        
        # Should detect conflicts between conflict1 and conflict2
        assert isinstance(conflicts, dict)
        
        # Check if expected conflicts are detected
        # (conflict1 and conflict2 should use the same ports)
        conflicting_ports = [port for port, users in conflicts.items() if len(users) > 1]
        logger.info(f"Detected port conflicts: {conflicting_ports}")
        
        # Should have conflicts for the intentionally conflicting environments
        assert len(conflicting_ports) > 0, "Expected port conflicts not detected"
    
    @pytest.mark.parametrize("env_name", ["minimal", "full-stack", "feature-auth", "performance"])
    def test_environment_configuration_validation(self, env_name: str) -> None:
        """Test validation of individual environment configurations."""
        result = self.manager.validate_environment_configuration(env_name)
        
        assert isinstance(result, dict)
        assert "valid" in result
        assert "errors" in result
        assert "warnings" in result
        assert "config" in result
        
        # If validation fails, log the errors for debugging
        if not result["valid"]:
            logger.error(f"Environment {env_name} validation failed: {result['errors']}")
        
        # The result should be valid if the environment is properly configured
        assert result["valid"], f"Environment {env_name} validation failed: {result['errors']}"
    
    def test_test_report_generation(self) -> None:
        """Test generation of comprehensive test data report."""
        report = self.manager.generate_test_report()
        
        assert isinstance(report, dict)
        assert "timestamp" in report
        assert "structure_validation" in report
        assert "port_conflicts" in report
        assert "environments" in report
        assert "summary" in report
        
        # Check summary data
        summary = report["summary"]
        assert "total_environments" in summary
        assert "valid_environments" in summary
        assert "total_ports" in summary
        assert "conflicting_ports" in summary
        
        # Should have reasonable values
        assert summary["total_environments"] > 0
        assert summary["valid_environments"] >= 0
        assert summary["total_ports"] > 0
        
        logger.info(f"Test report summary: {summary}")
    
    def test_environment_setup_validation(self) -> None:
        """Test environment setup validation."""
        env_name = "minimal"
        result = self.manager.setup_test_environment(env_name)
        
        assert isinstance(result, dict)
        assert "success" in result
        assert "environment" in result
        assert "steps" in result
        assert "errors" in result
        
        assert result["environment"] == env_name
        assert isinstance(result["steps"], list)
        assert len(result["steps"]) > 0
        
        # If setup fails, log the errors for debugging
        if not result["success"]:
            logger.error(f"Environment setup failed: {result['errors']}")
        
        # Log setup steps for debugging
        logger.info(f"Environment setup steps: {result['steps']}")
    
    def test_environment_cleanup_validation(self) -> None:
        """Test environment cleanup validation."""
        env_name = "minimal"
        result = self.manager.cleanup_test_environment(env_name)
        
        assert isinstance(result, dict)
        assert "success" in result
        assert "environment" in result
        assert "steps" in result
        assert "errors" in result
        
        assert result["environment"] == env_name
        assert isinstance(result["steps"], list)
        
        # If cleanup fails, log the errors for debugging
        if not result["success"]:
            logger.error(f"Environment cleanup failed: {result['errors']}")
        
        # Log cleanup steps for debugging
        logger.info(f"Environment cleanup steps: {result['steps']}")