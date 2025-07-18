"""Network information queries for environments.

This module provides functionality to query network information about services
including ports, URLs, health checks, and connectivity tests.
"""

import json
import logging
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .config import EnvironmentConfig

logger = logging.getLogger(__name__)


class NetworkInfo:
    """Provides network information queries for Docker Compose environments."""

    def __init__(self, project_dir: Union[str, Path]):
        """Initialize network information provider.

        Args:
            project_dir: Path to the project directory containing Docker Compose files
        """
        self.project_dir = Path(project_dir)
        self.config = EnvironmentConfig(project_dir)
        self._cached_status: Dict[str, Any] = {}
        self._cache_expiry = 0
        self._cache_ttl = 30  # Cache for 30 seconds

    def get_service_port(self, environment: str, service: str, container_port: Optional[str] = None) -> Optional[str]:
        """Get the host port for a service.

        Args:
            environment: Environment name
            service: Service name
            container_port: Specific container port to look for

        Returns:
            Host port string or None if not found
        """
        try:
            # Load environment configuration
            env_config = self.config.load_environment(environment)

            if service not in env_config["service_configs"]:
                logger.warning(f"Service '{service}' not found in environment '{environment}'")
                return None

            service_config = env_config["service_configs"][service]
            port_mappings = service_config.get("ports", [])

            if not port_mappings:
                logger.debug(f"No port mappings found for service '{service}'")
                return None

            # If container_port is specified, find matching mapping
            if container_port:
                for mapping in port_mappings:
                    if mapping.get("container_port") == container_port:
                        port = mapping.get("host_port")
                        return str(port) if port else None
                logger.debug(f"Container port '{container_port}' not found for service '{service}'")
                return None

            # Return first port mapping
            port = port_mappings[0].get("host_port")
            return str(port) if port else None

        except Exception as e:
            logger.error(f"Error getting service port: {e}")
            return None

    def get_service_ports(self, environment: str, service: str) -> List[Dict[str, Any]]:
        """Get all port mappings for a service.

        Args:
            environment: Environment name
            service: Service name

        Returns:
            List of port mapping dictionaries
        """
        try:
            env_config = self.config.load_environment(environment)

            if service not in env_config["service_configs"]:
                return []

            service_config = env_config["service_configs"][service]
            ports = service_config.get("ports", [])
            return ports if isinstance(ports, list) else []

        except Exception as e:
            logger.error(f"Error getting service ports: {e}")
            return []

    def get_service_url(
        self, environment: str, service: str, protocol: str = "http", container_port: Optional[str] = None
    ) -> Optional[str]:
        """Get the URL for a service.

        Args:
            environment: Environment name
            service: Service name
            protocol: Protocol to use (http, https, tcp, etc.)
            container_port: Specific container port to use

        Returns:
            Service URL or None if not found
        """
        port = self.get_service_port(environment, service, container_port)
        if not port:
            return None

        return f"{protocol}://localhost:{port}"

    def get_all_service_urls(self, environment: str) -> Dict[str, List[str]]:
        """Get URLs for all services in an environment.

        Args:
            environment: Environment name

        Returns:
            Dictionary mapping service names to lists of URLs
        """
        try:
            env_config = self.config.load_environment(environment)
            service_urls: Dict[str, List[str]] = {}

            for service_name in env_config["service_configs"].keys():
                urls = []
                ports = self.get_service_ports(environment, service_name)

                for port_mapping in ports:
                    host_port = port_mapping.get("host_port")
                    if host_port:
                        # Determine protocol based on common ports
                        protocol = self._guess_protocol(host_port)
                        urls.append(f"{protocol}://localhost:{host_port}")

                if urls:
                    service_urls[service_name] = urls

            return service_urls

        except Exception as e:
            logger.error(f"Error getting service URLs: {e}")
            return {}

    def test_service_connectivity(
        self, environment: str, service: str, container_port: Optional[str] = None, timeout: int = 5
    ) -> Dict[str, Any]:
        """Test connectivity to a service.

        Args:
            environment: Environment name
            service: Service name
            container_port: Specific container port to test
            timeout: Connection timeout in seconds

        Returns:
            Dictionary with connectivity test results
        """
        result = {
            "service": service,
            "environment": environment,
            "accessible": False,
            "response_time": None,
            "error": None,
            "tested_urls": [],
        }

        try:
            # Get service ports
            if container_port:
                port = self.get_service_port(environment, service, container_port)
                ports_to_test = [port] if port else []
            else:
                port_mappings = self.get_service_ports(environment, service)
                ports_to_test = [str(p.get("host_port")) for p in port_mappings if p.get("host_port")]

            if not ports_to_test:
                result["error"] = f"No accessible ports found for service '{service}'"
                return result

            # Test each port
            for port in ports_to_test:
                if not port:
                    continue

                test_result = self._test_port_connectivity("localhost", int(port), timeout)
                result["tested_urls"].append(test_result)

                if test_result["accessible"]:
                    result["accessible"] = True
                    result["response_time"] = test_result["response_time"]
                    break

            return result

        except Exception as e:
            result["error"] = str(e)
            return result

    def get_network_topology(self, environment: str) -> Dict[str, Any]:
        """Get network topology information for an environment.

        Args:
            environment: Environment name

        Returns:
            Dictionary with network topology information
        """
        try:
            env_config = self.config.load_environment(environment)

            topology = {
                "environment": environment,
                "services": {},
                "networks": [],
                "volumes": [],
                "port_mappings": {},
                "dependencies": {},
            }

            # Extract service information
            for service_name, service_config in env_config["service_configs"].items():
                topology["services"][service_name] = {
                    "image": service_config.get("image", ""),
                    "container_name": service_config.get("container_name", ""),
                    "ports": service_config.get("ports", []),
                    "volumes": service_config.get("volumes", []),
                    "environment": service_config.get("environment", {}),
                    "depends_on": service_config.get("depends_on", []),
                }

                # Extract port mappings
                for port_mapping in service_config.get("ports", []):
                    host_port = port_mapping.get("host_port")
                    if host_port:
                        topology["port_mappings"][host_port] = {
                            "service": service_name,
                            "container_port": port_mapping.get("container_port"),
                            "protocol": port_mapping.get("protocol", "tcp"),
                        }

                # Extract dependencies
                depends_on = service_config.get("depends_on", [])
                if isinstance(depends_on, dict):
                    depends_on = list(depends_on.keys())

                if depends_on:
                    topology["dependencies"][service_name] = depends_on

            # Extract networks and volumes from compose config
            compose_config = env_config.get("compose_config", {})
            topology["networks"] = list(compose_config.get("networks", {}).keys())
            topology["volumes"] = list(compose_config.get("volumes", {}).keys())

            return topology

        except Exception as e:
            logger.error(f"Error getting network topology: {e}")
            return {"error": str(e)}

    def get_service_health(self, environment: str, service: str) -> Dict[str, Any]:
        """Get health information for a service.

        Args:
            environment: Environment name
            service: Service name

        Returns:
            Dictionary with service health information
        """
        try:
            # Get current container status
            status = self._get_service_status(environment, service)

            health_info = {
                "service": service,
                "environment": environment,
                "state": status.get("state", "unknown"),
                "health": status.get("health", "unknown"),
                "healthy": False,
                "uptime": None,
                "created": status.get("created", ""),
                "ports": status.get("ports", []),
            }

            # Determine if service is healthy
            state = health_info["state"]
            health = health_info["health"]

            if state == "running" and (health == "healthy" or health == "unknown"):
                health_info["healthy"] = True

            # Calculate uptime if available
            if health_info["created"]:
                try:
                    from datetime import datetime

                    created_time = datetime.fromisoformat(health_info["created"].replace("Z", "+00:00"))
                    uptime = (datetime.now(created_time.tzinfo) - created_time).total_seconds()
                    health_info["uptime"] = uptime
                except Exception:
                    pass

            return health_info

        except Exception as e:
            logger.error(f"Error getting service health: {e}")
            return {"error": str(e)}

    def get_environment_health(self, environment: str) -> Dict[str, Any]:
        """Get health information for all services in an environment.

        Args:
            environment: Environment name

        Returns:
            Dictionary with environment health information
        """
        try:
            env_config = self.config.load_environment(environment)

            health_info = {
                "environment": environment,
                "services": {},
                "healthy_services": 0,
                "total_services": 0,
                "overall_healthy": False,
            }

            # Check health of each service
            for service_name in env_config["service_configs"].keys():
                service_health = self.get_service_health(environment, service_name)
                health_info["services"][service_name] = service_health

                if service_health.get("healthy", False):
                    health_info["healthy_services"] += 1

                health_info["total_services"] += 1

            # Determine overall health
            if health_info["total_services"] > 0:
                health_info["overall_healthy"] = health_info["healthy_services"] == health_info["total_services"]

            return health_info

        except Exception as e:
            logger.error(f"Error getting environment health: {e}")
            return {"error": str(e)}

    def find_service_by_port(self, environment: str, port: str) -> Optional[str]:
        """Find which service is using a specific port.

        Args:
            environment: Environment name
            port: Port number to search for

        Returns:
            Service name or None if not found
        """
        try:
            topology = self.get_network_topology(environment)

            if "error" in topology:
                return None

            port_mappings = topology.get("port_mappings", {})

            if port in port_mappings:
                return port_mappings[port]["service"]

            return None

        except Exception as e:
            logger.error(f"Error finding service by port: {e}")
            return None

    def list_exposed_ports(self, environment: str) -> List[Dict[str, Any]]:
        """List all exposed ports in an environment.

        Args:
            environment: Environment name

        Returns:
            List of port information dictionaries
        """
        try:
            topology = self.get_network_topology(environment)

            if "error" in topology:
                return []

            exposed_ports = []
            port_mappings = topology.get("port_mappings", {})

            for host_port, info in port_mappings.items():
                exposed_ports.append(
                    {
                        "host_port": host_port,
                        "container_port": info.get("container_port"),
                        "service": info.get("service"),
                        "protocol": info.get("protocol", "tcp"),
                        "url": f"http://localhost:{host_port}",
                    }
                )

            return sorted(exposed_ports, key=lambda x: int(x["host_port"]))

        except Exception as e:
            logger.error(f"Error listing exposed ports: {e}")
            return []

    def _get_service_status(self, environment: str, service: str) -> Dict[str, Any]:
        """Get current status of a service from Docker Compose.

        Args:
            environment: Environment name
            service: Service name

        Returns:
            Dictionary with service status
        """
        try:
            # Check cache first
            cache_key = f"{environment}:{service}"
            current_time = time.time()

            if cache_key in self._cached_status and current_time < self._cache_expiry:
                return self._cached_status[cache_key]

            # Build compose command
            env_file = self.project_dir / f".env.{environment}"
            compose_file = self.project_dir / "docker-compose.yml"
            override_file = self.project_dir / f"docker-compose.{environment}.yml"

            cmd = ["docker", "compose", "--env-file", str(env_file), "-f", str(compose_file)]

            if override_file.exists():
                cmd.extend(["-f", str(override_file)])

            cmd.extend(["ps", "--format", "json", service])

            result = subprocess.run(cmd, cwd=self.project_dir, capture_output=True, text=True)

            if result.returncode != 0:
                return {"state": "unknown", "health": "unknown"}

            # Parse JSON output
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    container_info = json.loads(line)
                    status = {
                        "state": container_info.get("State", "unknown"),
                        "health": container_info.get("Health", "unknown"),
                        "ports": container_info.get("Ports", []),
                        "created": container_info.get("CreatedAt", ""),
                        "image": container_info.get("Image", ""),
                        "names": container_info.get("Names", ""),
                    }

                    # Cache the result
                    self._cached_status[cache_key] = status
                    self._cache_expiry = current_time + self._cache_ttl

                    return status

            return {"state": "unknown", "health": "unknown"}

        except Exception as e:
            logger.error(f"Error getting service status: {e}")
            return {"state": "unknown", "health": "unknown"}

    def _test_port_connectivity(self, host: str, port: int, timeout: int = 5) -> Dict[str, Any]:
        """Test connectivity to a specific port.

        Args:
            port: Port to test
            timeout: Connection timeout

        Returns:
            Dictionary with test results
        """
        import socket

        result = {"port": port, "accessible": False, "response_time": None, "error": None}

        try:
            start_time = time.time()

            with socket.create_connection((host, port), timeout=timeout):
                result["accessible"] = True
                result["response_time"] = time.time() - start_time

        except Exception as e:
            result["error"] = str(e)

        return result

    def _guess_protocol(self, port: str) -> str:
        """Guess the protocol based on common port numbers.

        Args:
            port: Port number

        Returns:
            Protocol string
        """
        common_ports = {
            "80": "http",
            "443": "https",
            "8080": "http",
            "8443": "https",
            "3000": "http",
            "3001": "http",
            "5000": "http",
            "5432": "postgresql",
            "3306": "mysql",
            "6379": "redis",
            "25": "smtp",
            "587": "smtp",
            "465": "smtps",
            "143": "imap",
            "993": "imaps",
            "53": "dns",
            "22": "ssh",
            "21": "ftp",
        }

        return common_ports.get(port, "tcp")
