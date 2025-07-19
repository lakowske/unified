"""Unified environment lifecycle management.

This module provides functionality to create, start, stop, and remove
Docker Compose environments for development, testing, and deployment.
Supports both production and test environment directory structures.
"""

import logging
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .config import EnvironmentConfig

logger = logging.getLogger(__name__)


class UnifiedEnvironmentManager:
    """Unified manager for all Docker Compose environment lifecycle operations."""

    def __init__(self, project_dir: Union[str, Path], environments_dir: str = "environments"):
        """Initialize unified environment manager.

        Args:
            project_dir: Path to the project directory
            environments_dir: Directory containing environment subdirectories
        """
        self.project_dir = Path(project_dir)
        self.environments_dir = self.project_dir / environments_dir
        self.config = EnvironmentConfig(project_dir)
        self.active_environments: Dict[str, Dict[str, Any]] = {}

    def list_environments(self) -> List[str]:
        """List all available environments.

        Returns:
            List of environment names
        """
        if not self.environments_dir.exists():
            return []

        environments = []
        for env_dir in self.environments_dir.iterdir():
            if env_dir.is_dir():
                # Skip directories that don't contain environment files
                if self._has_environment_files(env_dir):
                    environments.append(env_dir.name)

        return sorted(environments)

    def _has_environment_files(self, env_dir: Path) -> bool:
        """Check if directory contains environment files.

        Args:
            env_dir: Directory to check

        Returns:
            True if environment files exist
        """
        env_name = env_dir.name

        # Look for .env.{environment} file
        env_file_patterns = [
            f".env.{env_name}",
            f".env.{env_name.replace('-', '_')}",
            f".env.{env_name.replace('_', '-')}",
        ]

        for pattern in env_file_patterns:
            if (env_dir / pattern).exists():
                return True

        return False

    def get_environment_files(self, environment: str) -> Dict[str, Optional[Path]]:
        """Get the file paths for an environment.

        Args:
            environment: Name of the environment

        Returns:
            Dictionary with env_file, compose_file, and env_dir paths
        """
        env_dir = self.environments_dir / environment

        if not env_dir.exists():
            return {"env_file": None, "compose_file": None, "env_dir": env_dir}

        # Look for .env files
        env_file_patterns = [
            f".env.{environment}",
            f".env.{environment.replace('-', '_')}",
            f".env.{environment.replace('_', '-')}",
        ]

        # Look for docker-compose files
        compose_file_patterns = [
            f"docker-compose.{environment}.yml",
            f"docker-compose.{environment.replace('-', '_')}.yml",
            f"docker-compose.{environment.replace('_', '-')}.yml",
        ]

        env_file = None
        compose_file = None

        for pattern in env_file_patterns:
            candidate = env_dir / pattern
            if candidate.exists():
                env_file = candidate
                break

        for pattern in compose_file_patterns:
            candidate = env_dir / pattern
            if candidate.exists():
                compose_file = candidate
                break

        return {"env_file": env_file, "compose_file": compose_file, "env_dir": env_dir}

    def create_environment(
        self, environment: str, template: str = "dev", custom_vars: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Create a new environment based on a template.

        Args:
            environment: Name of the new environment
            template: Template environment to copy from
            custom_vars: Custom environment variables to override

        Returns:
            Dictionary with success status and message
        """
        logger.info(f"Creating environment '{environment}' from template '{template}'")

        try:
            # Create environment directory
            env_dir = self.environments_dir / environment
            env_dir.mkdir(parents=True, exist_ok=True)

            # Copy template files
            template_files = self.get_environment_files(template)

            if not template_files["env_file"]:
                return {"success": False, "message": f"Template environment '{template}' not found"}

            # Copy and modify .env file
            new_env_file = env_dir / f".env.{environment}"
            template_content = template_files["env_file"].read_text()

            # Update environment name
            if "ENVIRONMENT=" in template_content:
                import re

                template_content = re.sub(
                    r"^ENVIRONMENT=.*$", f"ENVIRONMENT={environment}", template_content, flags=re.MULTILINE
                )
            else:
                template_content += f"\nENVIRONMENT={environment}\n"

            # Apply custom variables
            if custom_vars:
                for key, value in custom_vars.items():
                    if f"{key}=" in template_content:
                        import re

                        template_content = re.sub(
                            rf"^{key}=.*$", f"{key}={value}", template_content, flags=re.MULTILINE
                        )
                    else:
                        template_content += f"\n{key}={value}\n"

            new_env_file.write_text(template_content)

            # Copy docker-compose file if it exists
            if template_files["compose_file"]:
                new_compose_file = env_dir / f"docker-compose.{environment}.yml"
                compose_content = template_files["compose_file"].read_text()

                # Update compose project name and environment references
                compose_content = compose_content.replace(template, environment)
                new_compose_file.write_text(compose_content)

            logger.info(f"Environment '{environment}' created successfully")
            return {"success": True, "message": f"Environment '{environment}' created successfully"}

        except Exception as e:
            logger.error(f"Failed to create environment '{environment}': {e}")
            return {"success": False, "message": f"Failed to create environment '{environment}': {e}"}

    def start_environment(
        self, environment: str, services: Optional[List[str]] = None, wait_for_health: bool = True, timeout: int = 300
    ) -> Dict[str, Any]:
        """Start an environment.

        Args:
            environment: Name of the environment to start
            services: Specific services to start (optional)
            wait_for_health: Whether to wait for health checks
            timeout: Timeout in seconds

        Returns:
            Dictionary with success status and message
        """
        logger.info(f"Starting environment '{environment}'")

        files = self.get_environment_files(environment)

        if not files["env_file"]:
            return {"success": False, "message": f"Environment '{environment}' files not found"}

        try:
            # Build the docker-compose command
            cmd = ["docker", "compose"]

            # Add env file
            cmd.extend(["--env-file", str(files["env_file"].resolve())])

            # Add compose files - always start with base, then add environment-specific overrides
            default_compose = self.project_dir / "docker-compose.yml"
            if default_compose.exists():
                cmd.extend(["-f", str(default_compose.resolve())])

            # Add environment-specific compose file as override if it exists
            if files["compose_file"]:
                cmd.extend(["-f", str(files["compose_file"].resolve())])

            # Add services
            cmd.extend(["up", "-d"])
            if services:
                cmd.extend(services)

            # Execute command from environment directory
            result = subprocess.run(
                cmd, cwd=str(files["env_dir"].resolve()), capture_output=True, text=True, timeout=timeout
            )

            if result.returncode == 0:
                logger.info(f"Environment '{environment}' started successfully")
                return {"success": True, "message": f"Environment '{environment}' started successfully"}
            logger.error(f"Failed to start environment '{environment}': {result.stderr}")
            return {"success": False, "message": f"Failed to start environment '{environment}': {result.stderr}"}

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "message": f"Timeout starting environment '{environment}' after {timeout} seconds",
            }
        except Exception as e:
            logger.error(f"Error starting environment '{environment}': {e}")
            return {"success": False, "message": f"Error starting environment '{environment}': {e}"}

    def stop_environment(self, environment: str, remove_volumes: bool = False) -> Dict[str, Any]:
        """Stop an environment.

        Args:
            environment: Name of the environment to stop
            remove_volumes: Whether to remove volumes

        Returns:
            Dictionary with success status and message
        """
        logger.info(f"Stopping environment '{environment}'")

        files = self.get_environment_files(environment)

        if not files["env_file"]:
            return {"success": False, "message": f"Environment '{environment}' files not found"}

        try:
            # Build the docker-compose command
            cmd = ["docker", "compose"]

            # Add env file
            cmd.extend(["--env-file", str(files["env_file"].resolve())])

            # Add compose files - always start with base, then add environment-specific overrides
            default_compose = self.project_dir / "docker-compose.yml"
            if default_compose.exists():
                cmd.extend(["-f", str(default_compose.resolve())])

            # Add environment-specific compose file as override if it exists
            if files["compose_file"]:
                cmd.extend(["-f", str(files["compose_file"].resolve())])

            # Add down command
            cmd.append("down")
            if remove_volumes:
                cmd.append("-v")

            # Execute command from environment directory
            result = subprocess.run(
                cmd, cwd=str(files["env_dir"].resolve()), capture_output=True, text=True, timeout=120
            )

            if result.returncode == 0:
                logger.info(f"Environment '{environment}' stopped successfully")
                return {"success": True, "message": f"Environment '{environment}' stopped successfully"}
            logger.error(f"Failed to stop environment '{environment}': {result.stderr}")
            return {"success": False, "message": f"Failed to stop environment '{environment}': {result.stderr}"}

        except Exception as e:
            logger.error(f"Error stopping environment '{environment}': {e}")
            return {"success": False, "message": f"Error stopping environment '{environment}': {e}"}

    def stop_containers_only(self, environment: str) -> Dict[str, Any]:
        """Stop containers without removing them or volumes.

        Args:
            environment: Name of the environment to stop

        Returns:
            Dictionary with success status and message
        """
        logger.info(f"Stopping containers for environment '{environment}'")

        files = self.get_environment_files(environment)

        if not files["env_file"]:
            return {"success": False, "message": f"Environment '{environment}' files not found"}

        try:
            # Build the docker-compose command
            cmd = ["docker", "compose"]

            # Add env file
            cmd.extend(["--env-file", str(files["env_file"].resolve())])

            # Add compose files - always start with base, then add environment-specific overrides
            default_compose = self.project_dir / "docker-compose.yml"
            if default_compose.exists():
                cmd.extend(["-f", str(default_compose.resolve())])

            # Add environment-specific compose file as override if it exists
            if files["compose_file"]:
                cmd.extend(["-f", str(files["compose_file"].resolve())])

            # Use stop command (not down) to preserve containers
            cmd.append("stop")

            # Execute command from environment directory
            result = subprocess.run(
                cmd, cwd=str(files["env_dir"].resolve()), capture_output=True, text=True, timeout=120
            )

            if result.returncode == 0:
                logger.info(f"Containers for environment '{environment}' stopped successfully")
                return {"success": True, "message": f"Containers for environment '{environment}' stopped successfully"}
            logger.error(f"Failed to stop containers for environment '{environment}': {result.stderr}")
            return {
                "success": False,
                "message": f"Failed to stop containers for environment '{environment}': {result.stderr}",
            }

        except Exception as e:
            logger.error(f"Error stopping containers for environment '{environment}': {e}")
            return {"success": False, "message": f"Error stopping containers for environment '{environment}': {e}"}

    def remove_containers_and_volumes(self, environment: str, remove_volumes: bool = True) -> Dict[str, Any]:
        """Remove stopped containers and optionally volumes.

        Args:
            environment: Name of the environment to clean up
            remove_volumes: Whether to remove volumes

        Returns:
            Dictionary with success status and message
        """
        logger.info(f"Removing containers for environment '{environment}' (remove_volumes={remove_volumes})")

        files = self.get_environment_files(environment)

        if not files["env_file"]:
            return {"success": False, "message": f"Environment '{environment}' files not found"}

        try:
            # Build the docker-compose command
            cmd = ["docker", "compose"]

            # Add env file
            cmd.extend(["--env-file", str(files["env_file"].resolve())])

            # Add compose files - always start with base, then add environment-specific overrides
            default_compose = self.project_dir / "docker-compose.yml"
            if default_compose.exists():
                cmd.extend(["-f", str(default_compose.resolve())])

            # Add environment-specific compose file as override if it exists
            if files["compose_file"]:
                cmd.extend(["-f", str(files["compose_file"].resolve())])

            # Use down command to remove containers and optionally volumes
            cmd.append("down")
            if remove_volumes:
                cmd.append("-v")

            # Execute command from environment directory
            result = subprocess.run(
                cmd, cwd=str(files["env_dir"].resolve()), capture_output=True, text=True, timeout=120
            )

            if result.returncode == 0:
                logger.info(f"Containers for environment '{environment}' removed successfully")
                return {"success": True, "message": f"Containers for environment '{environment}' removed successfully"}
            logger.error(f"Failed to remove containers for environment '{environment}': {result.stderr}")
            return {
                "success": False,
                "message": f"Failed to remove containers for environment '{environment}': {result.stderr}",
            }

        except Exception as e:
            logger.error(f"Error removing containers for environment '{environment}': {e}")
            return {"success": False, "message": f"Error removing containers for environment '{environment}': {e}"}

    def collect_container_logs(self, environment: str) -> Dict[str, Any]:
        """Collect logs from all containers in an environment.

        Args:
            environment: Name of the environment

        Returns:
            Dictionary with success status and collected log information
        """
        logger.info(f"Collecting container logs for environment '{environment}'")

        # Get container names from environment configuration
        try:
            env_config = self.config.load_environment(environment)
            expected_containers = self._get_expected_containers(env_config, environment)

            # Import log collector
            from ..performance.log_collector import ContainerLogCollector

            # Create output directory for this environment's logs
            logs_dir = Path("/tmp") / f"container-logs-{environment}"
            log_collector = ContainerLogCollector(logs_dir)

            # Collect logs
            collection_results = log_collector.collect_container_logs(expected_containers)
            system_info = log_collector.collect_system_info()
            summary_file = log_collector.save_collection_summary(collection_results, system_info)

            return {
                "success": True,
                "message": f"Collected logs for {len(expected_containers)} containers",
                "containers": expected_containers,
                "collection_results": collection_results,
                "summary_file": str(summary_file),
                "logs_directory": str(logs_dir),
            }

        except Exception as e:
            logger.error(f"Error collecting container logs for environment '{environment}': {e}")
            return {
                "success": False,
                "message": f"Error collecting container logs: {e}",
                "containers": [],
                "collection_results": {},
                "summary_file": None,
                "logs_directory": None,
            }

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

    def cleanup_environment(self, environment: str) -> Dict[str, Any]:
        """Clean up an environment completely.

        Args:
            environment: Name of the environment to clean up

        Returns:
            Dictionary with success status and message
        """
        logger.info(f"Cleaning up environment '{environment}'")

        # First stop the environment with volume removal
        stop_result = self.stop_environment(environment, remove_volumes=True)

        if not stop_result["success"]:
            return stop_result

        return {"success": True, "message": f"Environment '{environment}' cleaned up successfully"}

    def get_environment_status(self, environment: str) -> Dict[str, Any]:
        """Get the status of an environment.

        Args:
            environment: Name of the environment

        Returns:
            Dictionary with environment status information
        """
        files = self.get_environment_files(environment)

        if not files["env_file"]:
            return {"error": f"Environment '{environment}' not found", "environment": environment, "active": False}

        try:
            # Build the docker-compose command
            cmd = ["docker", "compose"]

            # Add env file
            cmd.extend(["--env-file", str(files["env_file"].resolve())])

            # Add compose files - always start with base, then add environment-specific overrides
            default_compose = self.project_dir / "docker-compose.yml"
            if default_compose.exists():
                cmd.extend(["-f", str(default_compose.resolve())])

            # Add environment-specific compose file as override if it exists
            if files["compose_file"]:
                cmd.extend(["-f", str(files["compose_file"].resolve())])

            # Get status
            cmd.extend(["ps", "--format", "json"])

            # Execute command from environment directory
            result = subprocess.run(
                cmd, cwd=str(files["env_dir"].resolve()), capture_output=True, text=True, timeout=30
            )

            if result.returncode == 0:
                import json

                services = []
                if result.stdout.strip():
                    for line in result.stdout.strip().split("\n"):
                        if line.strip():
                            services.append(json.loads(line))

                active = len(services) > 0
                service_count = len(services)
                healthy_services = sum(1 for s in services if s.get("Health", "").lower() == "healthy")

                return {
                    "environment": environment,
                    "active": active,
                    "service_count": service_count,
                    "healthy_services": healthy_services,
                    "services": {
                        s["Name"]: {"state": s["State"], "health": s.get("Health", "unknown")} for s in services
                    },
                }
            return {
                "environment": environment,
                "active": False,
                "service_count": 0,
                "healthy_services": 0,
                "services": {},
            }

        except Exception as e:
            logger.error(f"Error getting status for environment '{environment}': {e}")
            return {"error": f"Error getting status: {e}", "environment": environment, "active": False}


# Maintain backward compatibility
EnvironmentManager = UnifiedEnvironmentManager
