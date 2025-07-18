#!/usr/bin/env python3
"""Demo script for the unified environment management system.

This script demonstrates how to use the environment management system to:
1. Query network information about services
2. Create and manage isolated environments
3. Use the CLI interfaces programmatically

Usage:
    python examples/environment_demo.py
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from unified.cli import EnvironmentCLI, QueryCLI
from unified.environments import EnvironmentConfig, EnvironmentIsolation, EnvironmentManager, NetworkInfo


def demo_network_queries():
    """Demo network information queries."""
    print("=== Network Information Queries Demo ===")

    # Initialize network info
    project_dir = Path(__file__).parent.parent
    network = NetworkInfo(project_dir)

    try:
        # Query DNS service port - answering the user's specific question
        print("1. What port is the DNS container bound to?")
        dns_port = network.get_service_port("dev", "dns")
        if dns_port:
            print(f"   DNS service is bound to port: {dns_port}")
        else:
            print("   DNS service port not found (may need to load environment)")

        # Query mail service ports
        print("\n2. What ports does the mail service use?")
        mail_ports = network.get_service_ports("dev", "mail")
        if mail_ports:
            print("   Mail service ports:")
            for port_mapping in mail_ports:
                host_port = port_mapping.get("host_port")
                container_port = port_mapping.get("container_port")
                protocol = port_mapping.get("protocol", "tcp")
                print(f"   - {host_port}:{container_port} ({protocol})")
        else:
            print("   Mail service ports not found")

        # Query all service URLs
        print("\n3. What are all the service URLs?")
        service_urls = network.get_all_service_urls("dev")
        if service_urls:
            print("   Service URLs:")
            for service, urls in service_urls.items():
                print(f"   - {service}:")
                for url in urls:
                    print(f"     {url}")
        else:
            print("   No service URLs found")

        # Query network topology
        print("\n4. What's the network topology?")
        topology = network.get_network_topology("dev")
        if "error" not in topology:
            print(f"   Environment: {topology['environment']}")
            print(f"   Services: {len(topology['services'])}")
            print(f"   Port mappings: {len(topology['port_mappings'])}")

            if topology["port_mappings"]:
                print("   Port mappings:")
                for host_port, info in sorted(topology["port_mappings"].items()):
                    service = info.get("service")
                    container_port = info.get("container_port")
                    print(f"   - {host_port}:{container_port} -> {service}")
        else:
            print(f"   Error: {topology['error']}")

    except Exception as e:
        print(f"   Error during network queries: {e}")
        print("   (This is expected if the dev environment is not set up)")


def demo_environment_management():
    """Demo environment management."""
    print("\n=== Environment Management Demo ===")

    project_dir = Path(__file__).parent.parent
    manager = EnvironmentManager(project_dir)

    try:
        # List existing environments
        print("1. Available environments:")
        environments = manager.list_environments()
        for env in environments:
            print(f"   - {env}")

        # Create a test environment
        print("\n2. Creating a test environment...")
        success = manager.create_environment("demo_test", "dev", {"DEMO_VAR": "demo_value", "TEST_MODE": "true"})
        if success:
            print("   ✓ Test environment created successfully")
        else:
            print("   ✗ Failed to create test environment")

        # List environments again to show the new one
        print("\n3. Available environments (after creation):")
        environments = manager.list_environments()
        for env in environments:
            print(f"   - {env}")

        # Clean up the test environment
        print("\n4. Cleaning up test environment...")
        success = manager.remove_environment("demo_test", force=True)
        if success:
            print("   ✓ Test environment removed successfully")
        else:
            print("   ✗ Failed to remove test environment")

    except Exception as e:
        print(f"   Error during environment management: {e}")


def demo_environment_isolation():
    """Demo environment isolation features."""
    print("\n=== Environment Isolation Demo ===")

    project_dir = Path(__file__).parent.parent
    isolation = EnvironmentIsolation(project_dir)

    try:
        # List existing isolated environments
        print("1. Existing isolated environments:")
        isolated_envs = isolation.list_isolated_environments()
        if isolated_envs:
            for env in isolated_envs:
                print(f"   - {env['name']} ({env['type']}) - {env['healthy_services']}/{env['service_count']} healthy")
        else:
            print("   No isolated environments found")

        # Create a feature branch environment
        print("\n2. Creating feature branch environment...")
        try:
            feature_env = isolation.create_feature_branch_environment("demo/user-authentication", auto_start=False)
            print(f"   ✓ Feature branch environment created: {feature_env}")

            # List isolated environments again
            print("\n3. Isolated environments (after creation):")
            isolated_envs = isolation.list_isolated_environments()
            for env in isolated_envs:
                print(f"   - {env['name']} ({env['type']}) - Created: {env['created']}")

            # Clean up
            print("\n4. Cleaning up feature branch environment...")
            success = isolation.cleanup_isolated_environment(feature_env)
            if success:
                print("   ✓ Feature branch environment cleaned up")
            else:
                print("   ✗ Failed to clean up feature branch environment")

        except Exception as e:
            print(f"   Error creating feature branch environment: {e}")

        # Demo finding available ports
        print("\n5. Finding available ports...")
        available_ports = isolation.find_available_ports(3, 8000)
        print(f"   Available ports starting from 8000: {available_ports}")

    except Exception as e:
        print(f"   Error during isolation demo: {e}")


def demo_cli_usage():
    """Demo CLI usage programmatically."""
    print("\n=== CLI Usage Demo ===")

    project_dir = Path(__file__).parent.parent

    # Demo Environment CLI
    print("1. Environment CLI commands:")
    env_cli = EnvironmentCLI(project_dir)

    # List environments
    print("   Listing environments:")
    try:
        # Simulate CLI args
        import argparse

        args = argparse.Namespace(command="list", project_dir=project_dir, verbose=False, json=False, status=False)
        result = env_cli._handle_list(args)
        print(f"   Command result: {result}")
    except Exception as e:
        print(f"   Error: {e}")

    # Demo Query CLI
    print("\n2. Query CLI commands:")
    query_cli = QueryCLI(project_dir)

    # Query services
    print("   Querying services:")
    try:
        args = argparse.Namespace(
            command="services", environment="dev", project_dir=project_dir, verbose=False, json=False
        )
        result = query_cli._handle_services(args)
        print(f"   Command result: {result}")
    except Exception as e:
        print(f"   Error: {e}")


def demo_practical_examples():
    """Demo practical examples that answer the user's questions."""
    print("\n=== Practical Examples ===")

    project_dir = Path(__file__).parent.parent

    # Example 1: Answering "What port is the DNS container bound to?"
    print("1. Answering: 'What port is the DNS container bound to?'")
    try:
        network = NetworkInfo(project_dir)
        dns_port = network.get_service_port("dev", "dns")
        if dns_port:
            print(f"   Answer: The DNS container is bound to port {dns_port}")
        else:
            print("   Answer: DNS service not found or not configured")
    except Exception as e:
        print(f"   Error: {e}")

    # Example 2: Creating an isolated test environment
    print("\n2. Creating isolated test environment that doesn't interfere:")
    try:
        isolation = EnvironmentIsolation(project_dir)

        # Create isolated environment
        isolated_env = isolation.create_isolated_environment(
            base_environment="dev", prefix="isolated_test", port_offset=2000, custom_vars={"TEST_ISOLATION": "true"}
        )
        print(f"   ✓ Created isolated environment: {isolated_env}")

        # Show that it has different ports
        config = EnvironmentConfig(project_dir)
        try:
            env_config = config.load_environment(isolated_env)
            print("   Port mappings in isolated environment:")
            for service, service_config in env_config["service_configs"].items():
                for port_mapping in service_config.get("ports", []):
                    host_port = port_mapping.get("host_port")
                    container_port = port_mapping.get("container_port")
                    print(f"   - {service}: {host_port}:{container_port}")
        except Exception as e:
            print(f"   Could not load isolated environment config: {e}")

        # Clean up
        print("   Cleaning up isolated environment...")
        isolation.cleanup_isolated_environment(isolated_env)
        print("   ✓ Cleaned up")

    except Exception as e:
        print(f"   Error: {e}")

    # Example 3: Feature branch environment
    print("\n3. Creating feature branch environment:")
    try:
        isolation = EnvironmentIsolation(project_dir)

        # Create feature branch environment
        feature_env = isolation.create_feature_branch_environment("feature/new-api-endpoints", auto_start=False)
        print(f"   ✓ Created feature branch environment: {feature_env}")

        # Show environment details
        isolated_envs = isolation.list_isolated_environments()
        for env in isolated_envs:
            if env["name"] == feature_env:
                print(f"   Environment type: {env['type']}")
                print(f"   Ports: {env['ports']}")
                break

        # Clean up
        print("   Cleaning up feature branch environment...")
        isolation.cleanup_isolated_environment(feature_env)
        print("   ✓ Cleaned up")

    except Exception as e:
        print(f"   Error: {e}")


def main():
    """Main demo function."""
    print("Unified Environment Management System Demo")
    print("=" * 50)

    # Check if we're in the right directory
    project_dir = Path(__file__).parent.parent
    if not (project_dir / "docker-compose.yml").exists():
        print("Warning: docker-compose.yml not found. Some demos may not work.")
        print(f"Expected location: {project_dir / 'docker-compose.yml'}")

    # Run demos
    demo_network_queries()
    demo_environment_management()
    demo_environment_isolation()
    demo_cli_usage()
    demo_practical_examples()

    print("\n" + "=" * 50)
    print("Demo completed!")
    print("\nTo use the CLI tools directly:")
    print("  python -m unified.cli.environment --help")
    print("  python -m unified.cli.query --help")
    print("\nOr use the specific commands:")
    print("  python -m unified.cli.query port dev dns")
    print("  python -m unified.cli.environment create-feature my-feature")


if __name__ == "__main__":
    main()
