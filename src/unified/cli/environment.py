"""CLI interface for environment management.

This module provides command-line interface for managing Docker Compose environments
including creation, starting, stopping, and removal of environments.
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional

from ..environments import EnvironmentIsolation, EnvironmentManager, NetworkInfo

logger = logging.getLogger(__name__)


class EnvironmentCLI:
    """Command-line interface for environment management."""

    def __init__(self, project_dir: Optional[Path] = None):
        """Initialize the CLI.

        Args:
            project_dir: Project directory path (defaults to current directory)
        """
        self.project_dir = project_dir or Path.cwd()
        self.manager = EnvironmentManager(self.project_dir)
        self.isolation = EnvironmentIsolation(self.project_dir)
        self.network = NetworkInfo(self.project_dir)

    def create_parser(self) -> argparse.ArgumentParser:
        """Create the argument parser for environment management.

        Returns:
            Configured argument parser
        """
        parser = argparse.ArgumentParser(
            description="Manage Docker Compose environments", formatter_class=argparse.RawDescriptionHelpFormatter
        )

        # Global options
        parser.add_argument("--project-dir", type=Path, default=self.project_dir, help="Project directory path")
        parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
        parser.add_argument("--json", action="store_true", help="Output in JSON format")

        # Subcommands
        subparsers = parser.add_subparsers(dest="command", help="Available commands")

        # List environments
        list_parser = subparsers.add_parser("list", help="List all environments")
        list_parser.add_argument("--status", action="store_true", help="Include status information")

        # Create environment
        create_parser = subparsers.add_parser("create", help="Create a new environment")
        create_parser.add_argument("name", help="Environment name")
        create_parser.add_argument("--template", default="dev", help="Template environment to copy from")
        create_parser.add_argument("--var", action="append", help="Custom environment variables (KEY=VALUE)")

        # Start environment
        start_parser = subparsers.add_parser("start", help="Start an environment")
        start_parser.add_argument("name", help="Environment name")
        start_parser.add_argument("--services", nargs="+", help="Specific services to start")
        start_parser.add_argument("--no-wait", action="store_true", help="Don't wait for services to be healthy")
        start_parser.add_argument("--timeout", type=int, default=300, help="Timeout in seconds")

        # Stop environment
        stop_parser = subparsers.add_parser("stop", help="Stop an environment")
        stop_parser.add_argument("name", help="Environment name")
        stop_parser.add_argument("--remove-volumes", action="store_true", help="Remove volumes")

        # Remove environment
        remove_parser = subparsers.add_parser("remove", help="Remove an environment")
        remove_parser.add_argument("name", help="Environment name")
        remove_parser.add_argument("--force", action="store_true", help="Force removal even if running")

        # Restart environment
        restart_parser = subparsers.add_parser("restart", help="Restart an environment")
        restart_parser.add_argument("name", help="Environment name")
        restart_parser.add_argument("--services", nargs="+", help="Specific services to restart")

        # Status command
        status_parser = subparsers.add_parser("status", help="Get environment status")
        status_parser.add_argument("name", help="Environment name")

        # Logs command
        logs_parser = subparsers.add_parser("logs", help="Get service logs")
        logs_parser.add_argument("name", help="Environment name")
        logs_parser.add_argument("service", help="Service name")
        logs_parser.add_argument("--lines", type=int, default=50, help="Number of lines to show")

        # Execute command
        exec_parser = subparsers.add_parser("exec", help="Execute command in service")
        exec_parser.add_argument("name", help="Environment name")
        exec_parser.add_argument("service", help="Service name")
        exec_parser.add_argument("command", nargs="+", help="Command to execute")

        # Create isolated environment
        isolated_parser = subparsers.add_parser("create-isolated", help="Create isolated environment")
        isolated_parser.add_argument("--base", default="dev", help="Base environment to copy from")
        isolated_parser.add_argument("--prefix", default="test", help="Prefix for environment name")
        isolated_parser.add_argument("--port-offset", type=int, default=1000, help="Port offset to avoid conflicts")
        isolated_parser.add_argument("--var", action="append", help="Custom environment variables (KEY=VALUE)")

        # Create feature branch environment
        feature_parser = subparsers.add_parser("create-feature", help="Create feature branch environment")
        feature_parser.add_argument("branch", help="Feature branch name")
        feature_parser.add_argument("--base", default="dev", help="Base environment to copy from")
        feature_parser.add_argument("--no-start", action="store_true", help="Don't start the environment automatically")

        # List isolated environments
        # list_isolated_parser = subparsers.add_parser("list-isolated", help="List isolated environments")

        # Cleanup isolated environments
        cleanup_parser = subparsers.add_parser("cleanup", help="Clean up isolated environments")
        cleanup_parser.add_argument("--all", action="store_true", help="Clean up all isolated environments")
        cleanup_parser.add_argument(
            "--force", action="store_true", help="Force cleanup even if environments are running"
        )
        cleanup_parser.add_argument("names", nargs="*", help="Specific environment names to clean up")

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
            self.manager = EnvironmentManager(self.project_dir)
            self.isolation = EnvironmentIsolation(self.project_dir)
            self.network = NetworkInfo(self.project_dir)

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
            logger.error(f"Error executing command: {e}")
            if parsed_args.verbose:
                import traceback

                traceback.print_exc()
            return 1

    def _handle_list(self, args: argparse.Namespace) -> int:
        """Handle list command."""
        environments = self.manager.list_environments()

        if args.json:
            result = []
            for env in environments:
                env_info = {"name": env}
                if args.status:
                    env_info["status"] = self.manager.get_environment_status(env)
                result.append(env_info)
            print(json.dumps(result, indent=2))
        else:
            if not environments:
                print("No environments found")
                return 0

            print("Available environments:")
            for env in environments:
                if args.status:
                    status = self.manager.get_environment_status(env)
                    active = "✓" if status.get("active", False) else "✗"
                    service_count = status.get("service_count", 0)
                    healthy_count = status.get("healthy_services", 0)
                    print(f"  {env} [{active}] ({healthy_count}/{service_count} healthy)")
                else:
                    print(f"  {env}")

        return 0

    def _handle_create(self, args: argparse.Namespace) -> int:
        """Handle create command."""
        custom_vars = self._parse_variables(args.var) if args.var else None

        if self.manager.create_environment(args.name, args.template, custom_vars):
            print(f"Environment '{args.name}' created successfully")
            return 0
        print(f"Failed to create environment '{args.name}'", file=sys.stderr)
        return 1

    def _handle_start(self, args: argparse.Namespace) -> int:
        """Handle start command."""
        if self.manager.start_environment(
            args.name, args.services, wait_for_health=not args.no_wait, timeout=args.timeout
        ):
            print(f"Environment '{args.name}' started successfully")
            return 0
        print(f"Failed to start environment '{args.name}'", file=sys.stderr)
        return 1

    def _handle_stop(self, args: argparse.Namespace) -> int:
        """Handle stop command."""
        if self.manager.stop_environment(args.name, args.remove_volumes):
            print(f"Environment '{args.name}' stopped successfully")
            return 0
        print(f"Failed to stop environment '{args.name}'", file=sys.stderr)
        return 1

    def _handle_remove(self, args: argparse.Namespace) -> int:
        """Handle remove command."""
        if self.manager.remove_environment(args.name, args.force):
            print(f"Environment '{args.name}' removed successfully")
            return 0
        print(f"Failed to remove environment '{args.name}'", file=sys.stderr)
        return 1

    def _handle_restart(self, args: argparse.Namespace) -> int:
        """Handle restart command."""
        if self.manager.restart_environment(args.name, args.services):
            print(f"Environment '{args.name}' restarted successfully")
            return 0
        print(f"Failed to restart environment '{args.name}'", file=sys.stderr)
        return 1

    def _handle_status(self, args: argparse.Namespace) -> int:
        """Handle status command."""
        status = self.manager.get_environment_status(args.name)

        if args.json:
            print(json.dumps(status, indent=2))
        else:
            if "error" in status:
                print(f"Error: {status['error']}", file=sys.stderr)
                return 1

            print(f"Environment: {status['environment']}")
            print(f"Active: {'Yes' if status.get('active', False) else 'No'}")
            print(f"Services: {status.get('service_count', 0)}")
            print(f"Healthy: {status.get('healthy_services', 0)}")

            services = status.get("services", {})
            if services:
                print("\nServices:")
                for service_name, service_info in services.items():
                    state = service_info.get("state", "unknown")
                    health = service_info.get("health", "unknown")
                    print(f"  {service_name}: {state} ({health})")

        return 0

    def _handle_logs(self, args: argparse.Namespace) -> int:
        """Handle logs command."""
        logs = self.manager.get_service_logs(args.name, args.service, args.lines)
        print(logs)
        return 0

    def _handle_exec(self, args: argparse.Namespace) -> int:
        """Handle exec command."""
        result = self.manager.execute_in_service(args.name, args.service, args.command)

        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)

        return result.returncode

    def _handle_create_isolated(self, args: argparse.Namespace) -> int:
        """Handle create-isolated command."""
        custom_vars = self._parse_variables(args.var) if args.var else None

        try:
            env_name = self.isolation.create_isolated_environment(
                base_environment=args.base, prefix=args.prefix, port_offset=args.port_offset, custom_vars=custom_vars
            )

            if args.json:
                print(json.dumps({"environment": env_name}))
            else:
                print(f"Isolated environment '{env_name}' created successfully")

            return 0

        except Exception as e:
            print(f"Failed to create isolated environment: {e}", file=sys.stderr)
            return 1

    def _handle_create_feature(self, args: argparse.Namespace) -> int:
        """Handle create-feature command."""
        try:
            env_name = self.isolation.create_feature_branch_environment(
                branch_name=args.branch, base_environment=args.base, auto_start=not args.no_start
            )

            if args.json:
                print(json.dumps({"environment": env_name}))
            else:
                print(f"Feature branch environment '{env_name}' created successfully")

            return 0

        except Exception as e:
            print(f"Failed to create feature branch environment: {e}", file=sys.stderr)
            return 1

    def _handle_list_isolated(self, args: argparse.Namespace) -> int:
        """Handle list-isolated command."""
        isolated_envs = self.isolation.list_isolated_environments()

        if args.json:
            print(json.dumps(isolated_envs, indent=2))
        else:
            if not isolated_envs:
                print("No isolated environments found")
                return 0

            print("Isolated environments:")
            for env in isolated_envs:
                name = env["name"]
                env_type = env["type"]
                active = "✓" if env["active"] else "✗"
                services = f"{env['healthy_services']}/{env['service_count']}"
                ports = ", ".join(env["ports"][:3])  # Show first 3 ports
                if len(env["ports"]) > 3:
                    ports += f", ... (+{len(env['ports']) - 3} more)"

                print(f"  {name} [{active}] ({env_type}) - {services} healthy")
                if ports:
                    print(f"    Ports: {ports}")

        return 0

    def _handle_cleanup(self, args: argparse.Namespace) -> int:
        """Handle cleanup command."""
        if args.all:
            cleaned_up = self.isolation.cleanup_all_isolated_environments(args.force)
            if args.json:
                print(json.dumps({"cleaned_up": cleaned_up}))
            else:
                print(f"Cleaned up {len(cleaned_up)} isolated environments")
                for env in cleaned_up:
                    print(f"  {env}")
            return 0

        if args.names:
            cleaned_up = []
            for env_name in args.names:
                if self.isolation.cleanup_isolated_environment(env_name, args.force):
                    cleaned_up.append(env_name)

            if args.json:
                print(json.dumps({"cleaned_up": cleaned_up}))
            else:
                print(f"Cleaned up {len(cleaned_up)} environments")
                for env in cleaned_up:
                    print(f"  {env}")

            return 0 if len(cleaned_up) == len(args.names) else 1

        print("Must specify --all or environment names", file=sys.stderr)
        return 1

    def _parse_variables(self, var_list: List[str]) -> Dict[str, str]:
        """Parse variable definitions from command line.

        Args:
            var_list: List of KEY=VALUE strings

        Returns:
            Dictionary of variables
        """
        variables = {}

        for var in var_list:
            if "=" in var:
                key, value = var.split("=", 1)
                variables[key.strip()] = value.strip()
            else:
                logger.warning(f"Invalid variable format: {var}")

        return variables


def main() -> None:
    """Main entry point for the environment CLI."""
    cli = EnvironmentCLI()
    sys.exit(cli.run())
