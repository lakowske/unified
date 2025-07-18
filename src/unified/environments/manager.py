"""Environment lifecycle management.

This module provides functionality to create, start, stop, and remove
Docker Compose environments for development, testing, and deployment.
"""

import logging
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .config import EnvironmentConfig

logger = logging.getLogger(__name__)


class EnvironmentManager:
    """Manages Docker Compose environment lifecycle operations."""

    def __init__(self, project_dir: Union[str, Path]):
        """Initialize environment manager.

        Args:
            project_dir: Path to the project directory containing Docker Compose files
        """
        self.project_dir = Path(project_dir)
        self.config = EnvironmentConfig(project_dir)
        self.active_environments: Dict[str, Dict[str, Any]] = {}

    def list_environments(self) -> List[str]:
        """List all available environments.

        Returns:
            List of environment names
        """
        env_files = list(self.project_dir.glob(".env.*"))
        environments = []

        for env_file in env_files:
            env_name = env_file.name.replace(".env.", "")
            if env_name and env_name != ".env":
                environments.append(env_name)

        return sorted(environments)

    def create_environment(
        self, environment: str, template: str = "dev", custom_vars: Optional[Dict[str, str]] = None
    ) -> bool:
        """Create a new environment based on a template.

        Args:
            environment: Name of the new environment
            template: Template environment to copy from
            custom_vars: Custom environment variables to override

        Returns:
            True if creation was successful, False otherwise
        """
        logger.info(f"Creating environment '{environment}' from template '{template}'")

        try:
            # Check if environment already exists
            if environment in self.list_environments():
                logger.warning(f"Environment '{environment}' already exists")
                return False

            # Copy template environment file
            template_file = self.project_dir / f".env.{template}"
            if not template_file.exists():
                logger.error(f"Template environment file not found: {template_file}")
                return False

            new_env_file = self.project_dir / f".env.{environment}"

            # Read template and apply customizations
            with template_file.open() as f:
                template_content = f.read()

            # Apply custom variables if provided
            if custom_vars:
                for key, value in custom_vars.items():
                    # Replace existing variable or add new one
                    if f"{key}=" in template_content:
                        # Replace existing variable
                        import re

                        pattern = rf"^{key}=.*$"
                        template_content = re.sub(pattern, f"{key}={value}", template_content, flags=re.MULTILINE)
                    else:
                        # Add new variable
                        template_content += f"\n{key}={value}\n"

            # Update environment name
            if "ENVIRONMENT=" in template_content:
                import re

                template_content = re.sub(
                    r"^ENVIRONMENT=.*$", f"ENVIRONMENT={environment}", template_content, flags=re.MULTILINE
                )
            else:
                template_content += f"\nENVIRONMENT={environment}\n"

            # Write new environment file
            with new_env_file.open("w") as f:
                f.write(template_content)

            logger.info(f"Environment '{environment}' created successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to create environment '{environment}': {e}")
            return False

    def start_environment(
        self, environment: str, services: Optional[List[str]] = None, wait_for_health: bool = True, timeout: int = 300
    ) -> bool:
        """Start an environment.

        Args:
            environment: Environment name
            services: List of specific services to start (None for all)
            wait_for_health: Whether to wait for services to be healthy
            timeout: Maximum time to wait for startup

        Returns:
            True if startup was successful, False otherwise
        """
        logger.info(f"Starting environment '{environment}'")

        try:
            # Load environment configuration
            env_config = self.config.load_environment(environment)

            # Build compose command
            cmd = self._build_compose_command(environment)

            # Start volume setup first if needed
            if "volume-setup" in env_config["service_configs"]:
                logger.info("Running volume setup...")
                volume_cmd = cmd + ["up", "-d", "volume-setup"]
                result = subprocess.run(volume_cmd, cwd=self.project_dir, capture_output=True, text=True)

                if result.returncode != 0:
                    logger.error(f"Volume setup failed: {result.stderr}")
                    return False

                # Wait for volume setup to complete
                time.sleep(10)

                # Stop volume setup container
                stop_cmd = cmd + ["stop", "volume-setup"]
                subprocess.run(stop_cmd, cwd=self.project_dir, capture_output=True, text=True)

            # Start main services
            start_cmd = cmd + ["up", "-d"]
            if services:
                start_cmd.extend(services)

            result = subprocess.run(start_cmd, cwd=self.project_dir, capture_output=True, text=True, timeout=timeout)

            if result.returncode != 0:
                logger.error(f"Failed to start environment '{environment}': {result.stderr}")
                return False

            # Wait for services to be healthy
            if wait_for_health:
                if not self._wait_for_services_healthy(environment, timeout):
                    logger.error(f"Services in environment '{environment}' did not become healthy")
                    return False

            # Track active environment
            self.active_environments[environment] = {
                "started_at": time.time(),
                "services": services or list(env_config["service_configs"].keys()),
            }

            logger.info(f"Environment '{environment}' started successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to start environment '{environment}': {e}")
            return False

    def stop_environment(self, environment: str, remove_volumes: bool = False) -> bool:
        """Stop an environment.

        Args:
            environment: Environment name
            remove_volumes: Whether to remove volumes

        Returns:
            True if stop was successful, False otherwise
        """
        logger.info(f"Stopping environment '{environment}'")

        try:
            cmd = self._build_compose_command(environment)

            # Build stop command
            stop_cmd = cmd + ["down"]
            if remove_volumes:
                stop_cmd.extend(["-v", "--remove-orphans"])

            result = subprocess.run(stop_cmd, cwd=self.project_dir, capture_output=True, text=True)

            if result.returncode != 0:
                logger.error(f"Failed to stop environment '{environment}': {result.stderr}")
                return False

            # Remove from active environments
            if environment in self.active_environments:
                del self.active_environments[environment]

            logger.info(f"Environment '{environment}' stopped successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to stop environment '{environment}': {e}")
            return False

    def remove_environment(self, environment: str, force: bool = False) -> bool:
        """Remove an environment completely.

        Args:
            environment: Environment name
            force: Force removal even if environment is running

        Returns:
            True if removal was successful, False otherwise
        """
        logger.info(f"Removing environment '{environment}'")

        try:
            # Stop environment first if it's running
            if environment in self.active_environments:
                if not force:
                    logger.error(f"Environment '{environment}' is running. Use force=True to stop and remove.")
                    return False

                if not self.stop_environment(environment, remove_volumes=True):
                    logger.error(f"Failed to stop environment '{environment}' before removal")
                    return False

            # Remove environment file
            env_file = self.project_dir / f".env.{environment}"
            if env_file.exists():
                env_file.unlink()
                logger.info(f"Removed environment file: {env_file}")

            # Remove environment-specific compose file if it exists
            compose_file = self.project_dir / f"docker-compose.{environment}.yml"
            if compose_file.exists():
                compose_file.unlink()
                logger.info(f"Removed compose override file: {compose_file}")

            logger.info(f"Environment '{environment}' removed successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to remove environment '{environment}': {e}")
            return False

    def get_environment_status(self, environment: str) -> Dict[str, Any]:
        """Get the status of an environment.

        Args:
            environment: Environment name

        Returns:
            Dictionary containing environment status information
        """
        try:
            cmd = self._build_compose_command(environment)
            status_cmd = cmd + ["ps", "--format", "json"]

            result = subprocess.run(status_cmd, cwd=self.project_dir, capture_output=True, text=True)

            if result.returncode != 0:
                return {"error": f"Failed to get status: {result.stderr}"}

            import json

            containers = []
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    containers.append(json.loads(line))

            # Parse container information
            services = {}
            for container in containers:
                service_name = container.get("Service", "unknown")
                services[service_name] = {
                    "state": container.get("State", "unknown"),
                    "health": container.get("Health", "unknown"),
                    "ports": container.get("Ports", []),
                    "created": container.get("CreatedAt", ""),
                    "image": container.get("Image", ""),
                    "container_name": container.get("Names", ""),
                }

            return {
                "environment": environment,
                "active": environment in self.active_environments,
                "services": services,
                "service_count": len(services),
                "healthy_services": sum(
                    1 for s in services.values() if s["health"] == "healthy" or s["state"] == "running"
                ),
            }

        except Exception as e:
            return {"error": f"Failed to get environment status: {e}"}

    def restart_environment(self, environment: str, services: Optional[List[str]] = None) -> bool:
        """Restart an environment or specific services.

        Args:
            environment: Environment name
            services: List of specific services to restart (None for all)

        Returns:
            True if restart was successful, False otherwise
        """
        logger.info(f"Restarting environment '{environment}'")

        try:
            cmd = self._build_compose_command(environment)
            restart_cmd = cmd + ["restart"]

            if services:
                restart_cmd.extend(services)

            result = subprocess.run(restart_cmd, cwd=self.project_dir, capture_output=True, text=True)

            if result.returncode != 0:
                logger.error(f"Failed to restart environment '{environment}': {result.stderr}")
                return False

            logger.info(f"Environment '{environment}' restarted successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to restart environment '{environment}': {e}")
            return False

    def execute_in_service(self, environment: str, service: str, command: List[str]) -> subprocess.CompletedProcess:
        """Execute a command in a service container.

        Args:
            environment: Environment name
            service: Service name
            command: Command to execute

        Returns:
            CompletedProcess with execution results
        """
        cmd = self._build_compose_command(environment)
        exec_cmd = cmd + ["exec", service] + command

        return subprocess.run(exec_cmd, cwd=self.project_dir, capture_output=True, text=True)

    def get_service_logs(self, environment: str, service: str, lines: int = 50) -> str:
        """Get logs from a service.

        Args:
            environment: Environment name
            service: Service name
            lines: Number of lines to retrieve

        Returns:
            Service logs as string
        """
        cmd = self._build_compose_command(environment)
        logs_cmd = cmd + ["logs", "--tail", str(lines), service]

        result = subprocess.run(logs_cmd, cwd=self.project_dir, capture_output=True, text=True)

        if result.returncode == 0:
            return result.stdout
        return f"Error getting logs: {result.stderr}"

    def _build_compose_command(self, environment: str) -> List[str]:
        """Build the docker compose command for an environment.

        Args:
            environment: Environment name

        Returns:
            List of command parts
        """
        env_file = self.project_dir / f".env.{environment}"
        compose_file = self.project_dir / "docker-compose.yml"
        override_file = self.project_dir / f"docker-compose.{environment}.yml"

        cmd = ["docker", "compose", "--env-file", str(env_file), "-f", str(compose_file)]

        if override_file.exists():
            cmd.extend(["-f", str(override_file)])

        return cmd

    def _wait_for_services_healthy(self, environment: str, timeout: int = 300) -> bool:
        """Wait for services to become healthy.

        Args:
            environment: Environment name
            timeout: Maximum time to wait

        Returns:
            True if all services are healthy, False otherwise
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            status = self.get_environment_status(environment)

            if "error" in status:
                logger.debug(f"Status check error: {status['error']}")
                time.sleep(5)
                continue

            services = status.get("services", {})
            if not services:
                logger.debug("No services found")
                time.sleep(5)
                continue

            # Check if all services are healthy or running
            healthy_count = 0
            for service_name, service_info in services.items():
                state = service_info.get("state", "")
                health = service_info.get("health", "")

                if state == "running" and (health == "healthy" or health == "unknown"):
                    healthy_count += 1

            if healthy_count == len(services):
                logger.info(f"All {len(services)} services are healthy")
                return True

            logger.debug(f"Waiting for services to be healthy: {healthy_count}/{len(services)}")
            time.sleep(5)

        logger.error(f"Services did not become healthy within {timeout} seconds")
        return False
