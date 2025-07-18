"""CLI interface for network information queries.

This module provides command-line interface for querying network information
about services, ports, URLs, and connectivity in Docker Compose environments.
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import List, Optional

from ..environments import EnvironmentConfig, EnvironmentManager, NetworkInfo

logger = logging.getLogger(__name__)


class QueryCLI:
    """Command-line interface for network information queries."""

    def __init__(self, project_dir: Optional[Path] = None):
        """Initialize the CLI.

        Args:
            project_dir: Project directory path (defaults to current directory)
        """
        self.project_dir = project_dir or Path.cwd()
        self.network = NetworkInfo(self.project_dir)
        self.manager = EnvironmentManager(self.project_dir)
        self.config = EnvironmentConfig(self.project_dir)

    def create_parser(self) -> argparse.ArgumentParser:
        """Create the argument parser for network queries.

        Returns:
            Configured argument parser
        """
        parser = argparse.ArgumentParser(
            description="Query network information about Docker Compose environments",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  # What port is the DNS container bound to?
  query port dev dns

  # What are all the URLs for the mail service?
  query urls dev mail

  # What services are running in the test environment?
  query services test

  # Check connectivity to the Apache service
  query connectivity dev apache

  # Show network topology
  query topology dev

  # Find which service is using port 8080
  query find-service dev 8080

  # List all exposed ports
  query ports dev

  # Check health of all services
  query health dev
            """,
        )

        # Global options
        parser.add_argument("--project-dir", type=Path, default=self.project_dir, help="Project directory path")
        parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
        parser.add_argument("--json", action="store_true", help="Output in JSON format")

        # Subcommands
        subparsers = parser.add_subparsers(dest="command", help="Available query commands")

        # Port query
        port_parser = subparsers.add_parser("port", help="Get port for a service")
        port_parser.add_argument("environment", help="Environment name")
        port_parser.add_argument("service", help="Service name")
        port_parser.add_argument("--container-port", help="Specific container port to look for")

        # Ports query (all ports for a service)
        ports_parser = subparsers.add_parser("ports", help="Get all ports for a service or environment")
        ports_parser.add_argument("environment", help="Environment name")
        ports_parser.add_argument("service", nargs="?", help="Service name (optional, shows all if not specified)")

        # URL query
        url_parser = subparsers.add_parser("url", help="Get URL for a service")
        url_parser.add_argument("environment", help="Environment name")
        url_parser.add_argument("service", help="Service name")
        url_parser.add_argument("--protocol", default="http", help="Protocol to use (default: http)")
        url_parser.add_argument("--container-port", help="Specific container port to use")

        # URLs query (all URLs for a service or environment)
        urls_parser = subparsers.add_parser("urls", help="Get all URLs for a service or environment")
        urls_parser.add_argument("environment", help="Environment name")
        urls_parser.add_argument("service", nargs="?", help="Service name (optional, shows all if not specified)")

        # Services query
        services_parser = subparsers.add_parser("services", help="List all services in an environment")
        services_parser.add_argument("environment", help="Environment name")

        # Connectivity test
        connectivity_parser = subparsers.add_parser("connectivity", help="Test service connectivity")
        connectivity_parser.add_argument("environment", help="Environment name")
        connectivity_parser.add_argument("service", help="Service name")
        connectivity_parser.add_argument("--container-port", help="Specific container port to test")
        connectivity_parser.add_argument("--timeout", type=int, default=5, help="Connection timeout in seconds")

        # Health query
        health_parser = subparsers.add_parser("health", help="Get health information")
        health_parser.add_argument("environment", help="Environment name")
        health_parser.add_argument("service", nargs="?", help="Service name (optional, shows all if not specified)")

        # Topology query
        topology_parser = subparsers.add_parser("topology", help="Get network topology")
        topology_parser.add_argument("environment", help="Environment name")

        # Find service by port
        find_service_parser = subparsers.add_parser("find-service", help="Find service using a port")
        find_service_parser.add_argument("environment", help="Environment name")
        find_service_parser.add_argument("port", help="Port number")

        # Configuration query
        config_parser = subparsers.add_parser("config", help="Get environment configuration")
        config_parser.add_argument("environment", help="Environment name")
        config_parser.add_argument("--validate", action="store_true", help="Validate configuration")

        # Quick query (natural language-like queries)
        quick_parser = subparsers.add_parser("quick", help="Quick natural language queries")
        quick_parser.add_argument("environment", help="Environment name")
        quick_parser.add_argument("query", nargs="+", help="Natural language query")

        return parser

    def run(self, args: Optional[List[str]] = None) -> int:
        """Run the CLI with the given arguments.

        Args:
            args: Command line arguments (defaults to sys.argv)

        Returns:
            Exit code
        """
        parser = self.create_parser()
        parsed_args = parser.parse_args(args)

        # Configure logging
        if parsed_args.verbose:
            logging.basicConfig(level=logging.DEBUG)
        else:
            logging.basicConfig(level=logging.INFO)

        # Update project directory if specified
        if parsed_args.project_dir:
            self.project_dir = parsed_args.project_dir
            self.network = NetworkInfo(self.project_dir)
            self.manager = EnvironmentManager(self.project_dir)
            self.config = EnvironmentConfig(self.project_dir)

        # Route to appropriate command handler
        if not parsed_args.command:
            parser.print_help()
            return 1

        try:
            method_name = f"_handle_{parsed_args.command.replace('-', '_')}"
            handler = getattr(self, method_name, None)

            if handler:
                result = handler(parsed_args)
                return result if isinstance(result, int) else 0
            print(f"Unknown command: {parsed_args.command}", file=sys.stderr)
            return 1

        except Exception as e:
            logger.error(f"Error executing query: {e}")
            if parsed_args.verbose:
                import traceback

                traceback.print_exc()
            return 1

    def _handle_port(self, args: argparse.Namespace) -> int:
        """Handle port query command."""
        port = self.network.get_service_port(args.environment, args.service, args.container_port)

        if args.json:
            result = {
                "environment": args.environment,
                "service": args.service,
                "container_port": args.container_port,
                "host_port": port,
            }
            print(json.dumps(result, indent=2))
        else:
            if port:
                print(f"Port: {port}")
            else:
                print("No port found", file=sys.stderr)
                return 1

        return 0

    def _handle_ports(self, args: argparse.Namespace) -> int:
        """Handle ports query command."""
        if args.service:
            # Get ports for specific service
            ports = self.network.get_service_ports(args.environment, args.service)

            if args.json:
                result = {"environment": args.environment, "service": args.service, "ports": ports}
                print(json.dumps(result, indent=2))
            else:
                if ports:
                    print(f"Ports for {args.service}:")
                    for port_mapping in ports:
                        host_port = port_mapping.get("host_port")
                        container_port = port_mapping.get("container_port")
                        protocol = port_mapping.get("protocol", "tcp")
                        print(f"  {host_port}:{container_port} ({protocol})")
                else:
                    print(f"No ports found for service {args.service}")
        else:
            # Get all exposed ports in environment
            exposed_ports = self.network.list_exposed_ports(args.environment)

            if args.json:
                result = {"environment": args.environment, "exposed_ports": exposed_ports}
                print(json.dumps(result, indent=2))
            else:
                if exposed_ports:
                    print(f"Exposed ports in {args.environment}:")
                    for port_info in exposed_ports:
                        host_port = port_info["host_port"]
                        container_port = port_info["container_port"]
                        service = port_info["service"]
                        protocol = port_info["protocol"]
                        print(f"  {host_port}:{container_port} ({protocol}) -> {service}")
                else:
                    print(f"No exposed ports found in environment {args.environment}")

        return 0

    def _handle_url(self, args: argparse.Namespace) -> int:
        """Handle URL query command."""
        url = self.network.get_service_url(args.environment, args.service, args.protocol, args.container_port)

        if args.json:
            result = {
                "environment": args.environment,
                "service": args.service,
                "protocol": args.protocol,
                "container_port": args.container_port,
                "url": url,
            }
            print(json.dumps(result, indent=2))
        else:
            if url:
                print(f"URL: {url}")
            else:
                print("No URL found", file=sys.stderr)
                return 1

        return 0

    def _handle_urls(self, args: argparse.Namespace) -> int:
        """Handle URLs query command."""
        if args.service:
            # Get URLs for specific service
            ports = self.network.get_service_ports(args.environment, args.service)
            urls = []

            for port_mapping in ports:
                host_port = port_mapping.get("host_port")
                if host_port:
                    protocol = self._guess_protocol(host_port)
                    urls.append(f"{protocol}://localhost:{host_port}")

            if args.json:
                result = {"environment": args.environment, "service": args.service, "urls": urls}
                print(json.dumps(result, indent=2))
            else:
                if urls:
                    print(f"URLs for {args.service}:")
                    for url in urls:
                        print(f"  {url}")
                else:
                    print(f"No URLs found for service {args.service}")
        else:
            # Get all URLs in environment
            all_urls = self.network.get_all_service_urls(args.environment)

            if args.json:
                result = {"environment": args.environment, "service_urls": all_urls}
                print(json.dumps(result, indent=2))
            else:
                if all_urls:
                    print(f"Service URLs in {args.environment}:")
                    for service, urls in all_urls.items():
                        print(f"  {service}:")
                        for url in urls:
                            print(f"    {url}")
                else:
                    print(f"No service URLs found in environment {args.environment}")

        return 0

    def _handle_services(self, args: argparse.Namespace) -> int:
        """Handle services query command."""
        try:
            env_config = self.config.load_environment(args.environment)
            services = list(env_config["service_configs"].keys())

            if args.json:
                result = {"environment": args.environment, "services": services}
                print(json.dumps(result, indent=2))
            else:
                if services:
                    print(f"Services in {args.environment}:")
                    for service in services:
                        print(f"  {service}")
                else:
                    print(f"No services found in environment {args.environment}")

            return 0

        except Exception as e:
            print(f"Error querying services: {e}", file=sys.stderr)
            return 1

    def _handle_connectivity(self, args: argparse.Namespace) -> int:
        """Handle connectivity test command."""
        result = self.network.test_service_connectivity(
            args.environment, args.service, args.container_port, args.timeout
        )

        if args.json:
            print(json.dumps(result, indent=2))
        else:
            service = result["service"]
            environment = result["environment"]
            accessible = result["accessible"]
            response_time = result.get("response_time")
            error = result.get("error")

            print(f"Connectivity test for {service} in {environment}:")

            if accessible:
                print(f"  ✓ Accessible (response time: {response_time:.3f}s)")
            else:
                print("  ✗ Not accessible")
                if error:
                    print(f"  Error: {error}")

            tested_urls = result.get("tested_urls", [])
            if tested_urls:
                print("  Tested URLs:")
                for url_test in tested_urls:
                    port = url_test["port"]
                    accessible = url_test["accessible"]
                    status = "✓" if accessible else "✗"
                    print(f"    {status} localhost:{port}")

        return 0 if result["accessible"] else 1

    def _handle_health(self, args: argparse.Namespace) -> int:
        """Handle health query command."""
        if args.service:
            # Get health for specific service
            health = self.network.get_service_health(args.environment, args.service)

            if args.json:
                print(json.dumps(health, indent=2))
            else:
                if "error" in health:
                    print(f"Error: {health['error']}", file=sys.stderr)
                    return 1

                service = health["service"]
                state = health["state"]
                health_status = health["health"]
                healthy = health["healthy"]
                uptime = health.get("uptime")

                print(f"Health for {service}:")
                print(f"  State: {state}")
                print(f"  Health: {health_status}")
                print(f"  Healthy: {'Yes' if healthy else 'No'}")

                if uptime:
                    print(f"  Uptime: {uptime:.0f} seconds")
        else:
            # Get health for all services
            health = self.network.get_environment_health(args.environment)

            if args.json:
                print(json.dumps(health, indent=2))
            else:
                if "error" in health:
                    print(f"Error: {health['error']}", file=sys.stderr)
                    return 1

                environment = health["environment"]
                healthy_services = health["healthy_services"]
                total_services = health["total_services"]
                overall_healthy = health["overall_healthy"]

                print(f"Health for {environment}:")
                print(f"  Overall: {'Healthy' if overall_healthy else 'Unhealthy'}")
                print(f"  Services: {healthy_services}/{total_services} healthy")

                print("  Service details:")
                for service_name, service_health in health["services"].items():
                    healthy = service_health.get("healthy", False)
                    state = service_health.get("state", "unknown")
                    status = "✓" if healthy else "✗"
                    print(f"    {status} {service_name} ({state})")

        return 0

    def _handle_topology(self, args: argparse.Namespace) -> int:
        """Handle topology query command."""
        topology = self.network.get_network_topology(args.environment)

        if args.json:
            print(json.dumps(topology, indent=2))
        else:
            if "error" in topology:
                print(f"Error: {topology['error']}", file=sys.stderr)
                return 1

            environment = topology["environment"]
            services = topology["services"]
            port_mappings = topology["port_mappings"]
            dependencies = topology.get("dependencies", {})

            print(f"Network topology for {environment}:")
            print(f"  Services: {len(services)}")
            print(f"  Port mappings: {len(port_mappings)}")

            print("\n  Services:")
            for service_name, service_info in services.items():
                image = service_info.get("image", "unknown")
                ports = service_info.get("ports", [])
                deps = dependencies.get(service_name, [])

                print(f"    {service_name} ({image})")
                if ports:
                    port_list = [f"{p.get('host_port', '?')}:{p.get('container_port', '?')}" for p in ports]
                    print(f"      Ports: {', '.join(port_list)}")
                if deps:
                    print(f"      Depends on: {', '.join(deps)}")

            if port_mappings:
                print("\n  Port mappings:")
                for host_port, info in sorted(port_mappings.items()):
                    service = info.get("service")
                    container_port = info.get("container_port")
                    protocol = info.get("protocol", "tcp")
                    print(f"    {host_port}:{container_port} ({protocol}) -> {service}")

        return 0

    def _handle_find_service(self, args: argparse.Namespace) -> int:
        """Handle find-service command."""
        service = self.network.find_service_by_port(args.environment, args.port)

        if args.json:
            result = {"environment": args.environment, "port": args.port, "service": service}
            print(json.dumps(result, indent=2))
        else:
            if service:
                print(f"Port {args.port} is used by service: {service}")
            else:
                print(f"No service found using port {args.port}")
                return 1

        return 0

    def _handle_config(self, args: argparse.Namespace) -> int:
        """Handle config query command."""
        try:
            env_config = self.config.load_environment(args.environment)

            if args.validate:
                validation = self.config.validate_configuration()

                if args.json:
                    print(json.dumps(validation, indent=2))
                else:
                    print(f"Configuration validation for {args.environment}:")
                    print(f"  Valid: {'Yes' if validation['valid'] else 'No'}")

                    if validation["errors"]:
                        print("  Errors:")
                        for error in validation["errors"]:
                            print(f"    ✗ {error}")

                    if validation["warnings"]:
                        print("  Warnings:")
                        for warning in validation["warnings"]:
                            print(f"    ⚠ {warning}")

                return 0 if validation["valid"] else 1
            if args.json:
                print(json.dumps(env_config, indent=2))
            else:
                print(f"Configuration for {args.environment}:")
                print(f"  Environment: {env_config['environment']}")
                print(f"  Services: {len(env_config['service_configs'])}")
                print(f"  Environment variables: {len(env_config['env_vars'])}")

                print("\n  Services:")
                for service_name in env_config["service_configs"]:
                    print(f"    {service_name}")

            return 0

        except Exception as e:
            print(f"Error querying configuration: {e}", file=sys.stderr)
            return 1

    def _handle_quick(self, args: argparse.Namespace) -> int:
        """Handle quick natural language queries."""
        query = " ".join(args.query).lower()

        # Simple pattern matching for common queries
        if "port" in query and "dns" in query:
            return self._handle_port(
                argparse.Namespace(environment=args.environment, service="dns", container_port=None, json=args.json)
            )

        if "port" in query and "mail" in query:
            return self._handle_port(
                argparse.Namespace(environment=args.environment, service="mail", container_port=None, json=args.json)
            )

        if "url" in query and "apache" in query:
            return self._handle_url(
                argparse.Namespace(
                    environment=args.environment, service="apache", protocol="http", container_port=None, json=args.json
                )
            )

        if "services" in query:
            return self._handle_services(argparse.Namespace(environment=args.environment, json=args.json))

        if "health" in query:
            return self._handle_health(argparse.Namespace(environment=args.environment, service=None, json=args.json))

        if "topology" in query:
            return self._handle_topology(argparse.Namespace(environment=args.environment, json=args.json))

        print(f"Sorry, I don't understand the query: {' '.join(args.query)}")
        print("Try using specific commands like 'port', 'url', 'services', 'health', or 'topology'")
        return 1

    def _guess_protocol(self, port: str) -> str:
        """Guess the protocol based on common port numbers."""
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

        return common_ports.get(port, "http")


def main() -> None:
    """Main entry point for the query CLI."""
    cli = QueryCLI()
    sys.exit(cli.run())
