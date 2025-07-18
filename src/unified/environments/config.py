"""Environment configuration parsing and management.

This module provides functionality to parse and manage environment configurations
including .env files, docker-compose.yml files, and environment-specific settings.
"""

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

logger = logging.getLogger(__name__)


class EnvironmentConfig:
    """Manages environment configuration parsing and validation."""

    def __init__(self, project_dir: Union[str, Path]):
        """Initialize environment configuration.

        Args:
            project_dir: Path to the project directory containing configuration files
        """
        self.project_dir = Path(project_dir)
        self.env_vars: Dict[str, str] = {}
        self.compose_config: Dict[str, Any] = {}
        self.service_configs: Dict[str, Dict[str, Any]] = {}

    def load_environment(self, environment: str) -> Dict[str, Any]:
        """Load configuration for a specific environment.

        Args:
            environment: Environment name (e.g., 'dev', 'test', 'staging')

        Returns:
            Dictionary containing environment configuration

        Raises:
            FileNotFoundError: If environment configuration files are not found
            ValueError: If configuration is invalid
        """
        logger.info(f"Loading environment configuration for: {environment}")

        # Try to find environment file in new directory structure first
        env_file = self.project_dir / "environments" / environment / f".env.{environment}"
        if not env_file.exists():
            # Fall back to old flat structure
            env_file = self.project_dir / f".env.{environment}"
            if not env_file.exists():
                msg = f"Environment file not found: {env_file}"
                raise FileNotFoundError(msg)

        self.env_vars = self._parse_env_file(env_file)

        # Try to find compose file in new directory structure first
        compose_file = self.project_dir / "environments" / environment / f"docker-compose.{environment}.yml"
        if not compose_file.exists():
            # Fall back to main docker-compose.yml
            compose_file = self.project_dir / "docker-compose.yml"
            if not compose_file.exists():
                msg = f"Docker compose file not found: {compose_file}"
                raise FileNotFoundError(msg)

        self.compose_config = self._parse_compose_file(compose_file)

        # Load environment-specific overrides (old structure)
        override_file = self.project_dir / f"docker-compose.{environment}.yml"
        if override_file.exists():
            override_config = self._parse_compose_file(override_file)
            self.compose_config = self._merge_compose_configs(self.compose_config, override_config)

        # Parse service configurations
        self.service_configs = self._extract_service_configs()

        return {
            "environment": environment,
            "env_vars": self.env_vars,
            "compose_config": self.compose_config,
            "service_configs": self.service_configs,
        }

    def _parse_env_file(self, env_file: Path) -> Dict[str, str]:
        """Parse .env file and return environment variables.

        Args:
            env_file: Path to .env file

        Returns:
            Dictionary of environment variables
        """
        env_vars = {}

        try:
            with env_file.open() as f:
                for line in f:
                    line = line.strip()

                    # Skip empty lines and comments
                    if not line or line.startswith("#"):
                        continue

                    # Parse key=value pairs
                    if "=" in line:
                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.strip()

                        # Remove inline comments (everything after #)
                        if "#" in value:
                            value = value.split("#")[0].strip()

                        # Remove quotes if present
                        if (
                            value.startswith('"')
                            and value.endswith('"')
                            or value.startswith("'")
                            and value.endswith("'")
                        ):
                            value = value[1:-1]

                        env_vars[key] = value

        except Exception as e:
            msg = f"Error parsing environment file {env_file}: {e}"
            raise ValueError(msg) from e

        logger.debug(f"Parsed {len(env_vars)} environment variables from {env_file}")
        return env_vars

    def _parse_compose_file(self, compose_file: Path) -> Dict[str, Any]:
        """Parse docker-compose.yml file.

        Args:
            compose_file: Path to docker-compose.yml file

        Returns:
            Dictionary containing compose configuration
        """
        try:
            with compose_file.open() as f:
                compose_config = yaml.safe_load(f)

            logger.debug(f"Parsed compose configuration from {compose_file}")
            return compose_config

        except Exception as e:
            msg = f"Error parsing compose file {compose_file}: {e}"
            raise ValueError(msg) from e

    def _merge_compose_configs(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Merge compose configurations with override taking precedence.

        Args:
            base: Base compose configuration
            override: Override compose configuration

        Returns:
            Merged configuration
        """
        merged = base.copy()

        # Merge services
        if "services" in override:
            if "services" not in merged:
                merged["services"] = {}

            for service_name, service_config in override["services"].items():
                if service_name in merged["services"]:
                    # Merge service configuration
                    merged["services"][service_name].update(service_config)
                else:
                    # Add new service
                    merged["services"][service_name] = service_config

        # Merge other top-level keys
        for key, value in override.items():
            if key != "services":
                merged[key] = value

        return merged

    def _extract_service_configs(self) -> Dict[str, Dict[str, Any]]:
        """Extract service-specific configurations from compose config.

        Returns:
            Dictionary mapping service names to their configurations
        """
        service_configs: Dict[str, Dict[str, Any]] = {}

        if "services" not in self.compose_config:
            return service_configs

        for service_name, service_config in self.compose_config["services"].items():
            service_configs[service_name] = {
                "image": service_config.get("image"),
                "ports": self._parse_port_mappings(service_config.get("ports", [])),
                "environment": service_config.get("environment", {}),
                "volumes": service_config.get("volumes", []),
                "depends_on": service_config.get("depends_on", []),
                "healthcheck": service_config.get("healthcheck", {}),
                "container_name": service_config.get("container_name", ""),
            }

        return service_configs

    def _parse_port_mappings(self, ports: List[str]) -> List[Dict[str, Any]]:
        """Parse port mappings from compose configuration.

        Args:
            ports: List of port mapping strings

        Returns:
            List of port mapping dictionaries
        """
        port_mappings = []

        for port_spec in ports:
            if isinstance(port_spec, str):
                # Parse "host:container" format
                if ":" in port_spec:
                    host_port, container_port = port_spec.split(":", 1)

                    # Handle variable substitution
                    host_port = self._substitute_variables(host_port)
                    container_port = self._substitute_variables(container_port)

                    port_mappings.append(
                        {
                            "host_port": host_port,
                            "container_port": container_port,
                            "protocol": "tcp",  # Default protocol
                        }
                    )
                else:
                    # Single port specification
                    port = self._substitute_variables(port_spec)
                    port_mappings.append({"host_port": port, "container_port": port, "protocol": "tcp"})
            elif isinstance(port_spec, dict):
                # Handle dictionary format
                port_mappings.append(port_spec)

        return port_mappings

    def _substitute_variables(self, value: Union[str, Any]) -> str:
        """Substitute environment variables in configuration values.

        Args:
            value: Value that may contain variable references

        Returns:
            Value with variables substituted
        """
        if not isinstance(value, str):
            return value

        # Handle ${VAR} format
        pattern = r"\$\{([^}]+)\}"

        def replace_var(match: re.Match[str]) -> str:
            var_name = match.group(1)
            return self.env_vars.get(var_name, match.group(0))

        return re.sub(pattern, replace_var, value)

    def get_service_port(self, service_name: str, container_port: Optional[str] = None) -> Optional[str]:
        """Get the host port for a service.

        Args:
            service_name: Name of the service
            container_port: Specific container port to look for (optional)

        Returns:
            Host port string or None if not found
        """
        if service_name not in self.service_configs:
            return None

        service_config = self.service_configs[service_name]
        port_mappings = service_config.get("ports", [])

        if not port_mappings:
            return None

        # If container_port is specified, find matching mapping
        if container_port:
            for mapping in port_mappings:
                if mapping.get("container_port") == container_port:
                    return mapping.get("host_port")

        # Return first port mapping
        return port_mappings[0].get("host_port")

    def get_service_url(self, service_name: str, protocol: str = "http") -> Optional[str]:
        """Get the URL for a service.

        Args:
            service_name: Name of the service
            protocol: Protocol to use (http, https, etc.)

        Returns:
            Service URL or None if not found
        """
        port = self.get_service_port(service_name)
        if not port:
            return None

        return f"{protocol}://localhost:{port}"

    def list_services(self) -> List[str]:
        """List all services in the configuration.

        Returns:
            List of service names
        """
        return list(self.service_configs.keys())

    def get_environment_name(self) -> str:
        """Get the environment name from configuration.

        Returns:
            Environment name
        """
        return self.env_vars.get("ENVIRONMENT", "unknown")

    def validate_configuration(self) -> Dict[str, Any]:
        """Validate the environment configuration.

        Returns:
            Dictionary with validation results
        """
        results: Dict[str, Any] = {"valid": True, "errors": [], "warnings": []}

        # Check required environment variables
        required_vars = ["ENVIRONMENT", "DB_NAME", "DB_USER", "DB_PASSWORD"]
        for var in required_vars:
            if var not in self.env_vars:
                results["errors"].append(f"Missing required environment variable: {var}")
                results["valid"] = False

        # Check service configurations
        if not self.service_configs:
            results["errors"].append("No services configured")
            results["valid"] = False

        # Check for port conflicts
        used_ports = set()
        for service_name, service_config in self.service_configs.items():
            for port_mapping in service_config.get("ports", []):
                host_port = port_mapping.get("host_port")
                if host_port in used_ports:
                    results["errors"].append(f"Port conflict: {host_port} used by multiple services")
                    results["valid"] = False
                used_ports.add(host_port)

        # Check for missing dependencies
        for service_name, service_config in self.service_configs.items():
            depends_on = service_config.get("depends_on", [])
            if isinstance(depends_on, dict):
                depends_on = list(depends_on.keys())

            for dependency in depends_on:
                if dependency not in self.service_configs:
                    results["warnings"].append(
                        f"Service {service_name} depends on {dependency} which is not configured"
                    )

        return results
