"""Environment isolation utilities for testing and development.

This module provides utilities for creating isolated environments that don't
interfere with each other, particularly useful for testing and feature branch development.
"""

import logging
import random
import string
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Set, Union

from .config import EnvironmentConfig
from .manager import EnvironmentManager
from .network import NetworkInfo

logger = logging.getLogger(__name__)


class EnvironmentIsolation:
    """Provides utilities for creating isolated environments."""

    def __init__(self, project_dir: Union[str, Path]):
        """Initialize environment isolation utilities.

        Args:
            project_dir: Path to the project directory
        """
        self.project_dir = Path(project_dir)
        self.manager = EnvironmentManager(project_dir)
        self.network = NetworkInfo(project_dir)
        self.config = EnvironmentConfig(project_dir)

        # Track isolated environments for cleanup
        self._isolated_environments: Set[str] = set()

    def create_isolated_environment(
        self,
        base_environment: str = "dev",
        prefix: str = "test",
        port_offset: int = 1000,
        custom_vars: Optional[Dict[str, str]] = None,
    ) -> str:
        """Create an isolated environment with unique ports and identifiers.

        Args:
            base_environment: Base environment to copy from
            prefix: Prefix for the isolated environment name
            port_offset: Offset to add to ports to avoid conflicts
            custom_vars: Additional custom environment variables

        Returns:
            Name of the created isolated environment
        """
        # Generate unique environment name
        timestamp = int(time.time())
        random_suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        env_name = f"{prefix}_{timestamp}_{random_suffix}"

        logger.info(f"Creating isolated environment: {env_name}")

        try:
            # Load base environment to get port mappings
            base_config = self.config.load_environment(base_environment)

            # Calculate port offsets to avoid conflicts
            port_mappings = self._calculate_isolated_ports(base_config, port_offset)

            # Prepare custom variables
            isolation_vars = {
                "ENVIRONMENT": env_name,
                "COMPOSE_PROJECT_NAME": f"unified_{env_name}",
                **port_mappings,
                **(custom_vars or {}),
            }

            # Create the isolated environment
            if self.manager.create_environment(env_name, base_environment, isolation_vars):
                self._isolated_environments.add(env_name)
                logger.info(f"Isolated environment '{env_name}' created successfully")
                return env_name
            msg = f"Failed to create isolated environment '{env_name}'"
            raise RuntimeError(msg)

        except Exception as e:
            logger.error(f"Error creating isolated environment: {e}")
            raise

    def create_feature_branch_environment(
        self, branch_name: str, base_environment: str = "dev", auto_start: bool = True
    ) -> str:
        """Create an isolated environment for a feature branch.

        Args:
            branch_name: Name of the feature branch
            base_environment: Base environment to copy from
            auto_start: Whether to start the environment automatically

        Returns:
            Name of the created feature branch environment
        """
        # Sanitize branch name for use as environment name
        safe_branch_name = self._sanitize_branch_name(branch_name)
        env_name = f"feature_{safe_branch_name}"

        logger.info(f"Creating feature branch environment: {env_name}")

        try:
            # Check if environment already exists
            if env_name in self.manager.list_environments():
                logger.warning(f"Feature branch environment '{env_name}' already exists")
                return env_name

            # Find available port range for this feature branch
            existing_envs = self.manager.list_environments()
            port_offset = self._find_available_port_offset(existing_envs, base_offset=2000)

            # Create custom variables for feature branch
            custom_vars = {
                "FEATURE_BRANCH": branch_name,
                "ENVIRONMENT_TYPE": "feature",
            }

            # Create the environment
            isolated_env = self.create_isolated_environment(
                base_environment=base_environment, prefix="feature", port_offset=port_offset, custom_vars=custom_vars
            )

            # Start the environment if requested
            if auto_start:
                if self.manager.start_environment(isolated_env):
                    logger.info(f"Feature branch environment '{isolated_env}' started")
                else:
                    logger.warning(f"Failed to start feature branch environment '{isolated_env}'")

            return isolated_env

        except Exception as e:
            logger.error(f"Error creating feature branch environment: {e}")
            raise

    def cleanup_isolated_environment(self, env_name: str, force: bool = True) -> bool:
        """Clean up an isolated environment.

        Args:
            env_name: Name of the isolated environment
            force: Force cleanup even if environment is running

        Returns:
            True if cleanup was successful, False otherwise
        """
        logger.info(f"Cleaning up isolated environment: {env_name}")

        try:
            # Remove the environment
            if self.manager.remove_environment(env_name, force=force):
                self._isolated_environments.discard(env_name)
                logger.info(f"Isolated environment '{env_name}' cleaned up successfully")
                return True
            logger.error(f"Failed to clean up isolated environment '{env_name}'")
            return False

        except Exception as e:
            logger.error(f"Error cleaning up isolated environment: {e}")
            return False

    def cleanup_all_isolated_environments(self, force: bool = True) -> List[str]:
        """Clean up all tracked isolated environments.

        Args:
            force: Force cleanup even if environments are running

        Returns:
            List of successfully cleaned up environment names
        """
        logger.info("Cleaning up all isolated environments")

        cleaned_up = []

        for env_name in list(self._isolated_environments):
            if self.cleanup_isolated_environment(env_name, force=force):
                cleaned_up.append(env_name)

        logger.info(f"Cleaned up {len(cleaned_up)} isolated environments")
        return cleaned_up

    def list_isolated_environments(self) -> List[Dict[str, Any]]:
        """List all isolated environments with their status.

        Returns:
            List of isolated environment information
        """
        isolated_envs = []

        # Find all environments that look like isolated environments
        all_envs = self.manager.list_environments()

        for env_name in all_envs:
            if self._is_isolated_environment(env_name):
                try:
                    status = self.manager.get_environment_status(env_name)
                    env_info = {
                        "name": env_name,
                        "type": self._get_environment_type(env_name),
                        "active": status.get("active", False),
                        "service_count": status.get("service_count", 0),
                        "healthy_services": status.get("healthy_services", 0),
                        "ports": self._get_environment_ports(env_name),
                        "created": self._get_environment_creation_time(env_name),
                    }
                    isolated_envs.append(env_info)
                except Exception as e:
                    logger.error(f"Error getting info for environment '{env_name}': {e}")

        return sorted(isolated_envs, key=lambda x: x["name"])

    def find_available_ports(self, count: int = 1, start_port: int = 8000) -> List[int]:
        """Find available ports for use in isolated environments.

        Args:
            count: Number of ports to find
            start_port: Starting port number to search from

        Returns:
            List of available port numbers
        """
        import socket

        available_ports: List[int] = []
        current_port = start_port

        while len(available_ports) < count and current_port < 65535:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.bind(("localhost", current_port))
                    available_ports.append(current_port)
            except OSError:
                # Port is in use, try next one
                pass

            current_port += 1

        return available_ports

    def get_environment_conflicts(self, env_name: str) -> List[Dict[str, Any]]:
        """Check for port conflicts with other environments.

        Args:
            env_name: Environment name to check

        Returns:
            List of port conflicts
        """
        conflicts = []

        try:
            # Get ports used by this environment
            env_ports = self._get_environment_ports(env_name)

            # Check against all other environments
            other_envs = [e for e in self.manager.list_environments() if e != env_name]

            for other_env in other_envs:
                other_ports = self._get_environment_ports(other_env)

                # Find common ports
                common_ports = set(env_ports).intersection(set(other_ports))

                for port in common_ports:
                    conflicts.append(
                        {
                            "port": port,
                            "environment1": env_name,
                            "environment2": other_env,
                            "service1": self.network.find_service_by_port(env_name, port),
                            "service2": self.network.find_service_by_port(other_env, port),
                        }
                    )

            return conflicts

        except Exception as e:
            logger.error(f"Error checking environment conflicts: {e}")
            return []

    @contextmanager
    def temporary_environment(
        self, base_environment: str = "dev", auto_start: bool = True, cleanup_on_exit: bool = True
    ) -> Iterator[str]:
        """Context manager for temporary isolated environments.

        Args:
            base_environment: Base environment to copy from
            auto_start: Whether to start the environment automatically
            cleanup_on_exit: Whether to clean up on exit

        Yields:
            Name of the temporary environment
        """
        temp_env = None

        try:
            # Create temporary environment
            temp_env = self.create_isolated_environment(base_environment=base_environment, prefix="temp")

            # Start if requested
            if auto_start:
                if not self.manager.start_environment(temp_env):
                    msg = f"Failed to start temporary environment '{temp_env}'"
                    raise RuntimeError(msg)

            yield temp_env

        finally:
            # Clean up if requested and environment was created
            if temp_env and cleanup_on_exit:
                self.cleanup_isolated_environment(temp_env, force=True)

    def _calculate_isolated_ports(self, base_config: Dict[str, Any], port_offset: int) -> Dict[str, str]:
        """Calculate port mappings for isolated environment.

        Args:
            base_config: Base environment configuration
            port_offset: Offset to add to ports

        Returns:
            Dictionary of port environment variables
        """
        port_vars = {}

        # Extract port mappings from service configs
        for service_name, service_config in base_config["service_configs"].items():
            for port_mapping in service_config.get("ports", []):
                host_port = port_mapping.get("host_port")
                if host_port and host_port.isdigit():
                    new_port = int(host_port) + port_offset

                    # Create environment variable name
                    var_name = f"{service_name.upper()}_PORT"
                    port_vars[var_name] = str(new_port)

        return port_vars

    def _find_available_port_offset(self, existing_envs: List[str], base_offset: int = 1000) -> int:
        """Find an available port offset that doesn't conflict with existing environments.

        Args:
            existing_envs: List of existing environment names
            base_offset: Base offset to start from

        Returns:
            Available port offset
        """
        # This is a simplified approach - in production you'd want more sophisticated conflict detection
        used_offsets = set()

        for env_name in existing_envs:
            if "_" in env_name:
                try:
                    # Extract potential offset from environment name
                    parts = env_name.split("_")
                    if len(parts) >= 2 and parts[1].isdigit():
                        used_offsets.add(int(parts[1]))
                except (ValueError, IndexError):
                    pass

        # Find available offset
        offset = base_offset
        while offset in used_offsets:
            offset += 1000

        return offset

    def _sanitize_branch_name(self, branch_name: str) -> str:
        """Sanitize branch name for use as environment name.

        Args:
            branch_name: Original branch name

        Returns:
            Sanitized branch name
        """
        # Remove invalid characters and replace with underscores
        import re

        sanitized = re.sub(r"[^a-zA-Z0-9_-]", "_", branch_name)

        # Remove leading/trailing underscores and convert to lowercase
        sanitized = sanitized.strip("_").lower()

        # Limit length
        if len(sanitized) > 50:
            sanitized = sanitized[:50]

        return sanitized

    def _is_isolated_environment(self, env_name: str) -> bool:
        """Check if an environment is an isolated environment.

        Args:
            env_name: Environment name

        Returns:
            True if environment appears to be isolated
        """
        # Check for common isolated environment patterns
        isolation_patterns = ["test_", "feature_", "temp_", "isolated_"]

        return any(env_name.startswith(pattern) for pattern in isolation_patterns)

    def _get_environment_type(self, env_name: str) -> str:
        """Get the type of an isolated environment.

        Args:
            env_name: Environment name

        Returns:
            Environment type
        """
        if env_name.startswith("test_"):
            return "test"
        if env_name.startswith("feature_"):
            return "feature"
        if env_name.startswith("temp_"):
            return "temporary"
        if env_name.startswith("isolated_"):
            return "isolated"
        return "unknown"

    def _get_environment_ports(self, env_name: str) -> List[str]:
        """Get all ports used by an environment.

        Args:
            env_name: Environment name

        Returns:
            List of port numbers
        """
        try:
            exposed_ports = self.network.list_exposed_ports(env_name)
            return [port["host_port"] for port in exposed_ports]
        except Exception:
            return []

    def _get_environment_creation_time(self, env_name: str) -> Optional[str]:
        """Get the creation time of an environment.

        Args:
            env_name: Environment name

        Returns:
            Creation time string or None
        """
        try:
            env_file = self.project_dir / f".env.{env_name}"
            if env_file.exists():
                stat = env_file.stat()
                return time.ctime(stat.st_ctime)
        except Exception:
            pass

        return None
