"""Unified environment lifecycle management.

This module provides functionality to create, start, stop, and remove
Docker Compose environments for development, testing, and deployment.
Supports both production and test environment directory structures.
"""

import logging
import subprocess
import time
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
            return {
                "env_file": None,
                "compose_file": None,
                "env_dir": env_dir
            }
        
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
        
        return {
            "env_file": env_file,
            "compose_file": compose_file,
            "env_dir": env_dir
        }

    def create_environment(self, environment: str, template: str = "dev", custom_vars: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
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
                return {
                    "success": False,
                    "message": f"Template environment '{template}' not found"
                }
            
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
            return {
                "success": True,
                "message": f"Environment '{environment}' created successfully"
            }
            
        except Exception as e:
            logger.error(f"Failed to create environment '{environment}': {e}")
            return {
                "success": False,
                "message": f"Failed to create environment '{environment}': {e}"
            }

    def start_environment(self, environment: str, services: Optional[List[str]] = None, 
                         wait_for_health: bool = True, timeout: int = 300) -> Dict[str, Any]:
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
            return {
                "success": False,
                "message": f"Environment '{environment}' files not found"
            }
        
        try:
            # Build the docker-compose command
            cmd = ["docker", "compose"]
            
            # Add env file
            cmd.extend(["--env-file", str(files["env_file"].resolve())])
            
            # Add compose file
            if files["compose_file"]:
                cmd.extend(["-f", str(files["compose_file"].resolve())])
            else:
                # Use default compose file in project root
                default_compose = self.project_dir / "docker-compose.yml"
                if default_compose.exists():
                    cmd.extend(["-f", str(default_compose.resolve())])
            
            # Add services
            cmd.extend(["up", "-d"])
            if services:
                cmd.extend(services)
            
            # Execute command from environment directory
            result = subprocess.run(
                cmd, 
                cwd=str(files["env_dir"].resolve()),
                capture_output=True, 
                text=True, 
                timeout=timeout
            )
            
            if result.returncode == 0:
                logger.info(f"Environment '{environment}' started successfully")
                return {
                    "success": True,
                    "message": f"Environment '{environment}' started successfully"
                }
            else:
                logger.error(f"Failed to start environment '{environment}': {result.stderr}")
                return {
                    "success": False,
                    "message": f"Failed to start environment '{environment}': {result.stderr}"
                }
                
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "message": f"Timeout starting environment '{environment}' after {timeout} seconds"
            }
        except Exception as e:
            logger.error(f"Error starting environment '{environment}': {e}")
            return {
                "success": False,
                "message": f"Error starting environment '{environment}': {e}"
            }

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
            return {
                "success": False,
                "message": f"Environment '{environment}' files not found"
            }
        
        try:
            # Build the docker-compose command
            cmd = ["docker", "compose"]
            
            # Add env file
            cmd.extend(["--env-file", str(files["env_file"].resolve())])
            
            # Add compose file
            if files["compose_file"]:
                cmd.extend(["-f", str(files["compose_file"].resolve())])
            
            # Add down command
            cmd.append("down")
            if remove_volumes:
                cmd.append("-v")
            
            # Execute command from environment directory
            result = subprocess.run(
                cmd,
                cwd=str(files["env_dir"].resolve()),
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                logger.info(f"Environment '{environment}' stopped successfully")
                return {
                    "success": True,
                    "message": f"Environment '{environment}' stopped successfully"
                }
            else:
                logger.error(f"Failed to stop environment '{environment}': {result.stderr}")
                return {
                    "success": False,
                    "message": f"Failed to stop environment '{environment}': {result.stderr}"
                }
                
        except Exception as e:
            logger.error(f"Error stopping environment '{environment}': {e}")
            return {
                "success": False,
                "message": f"Error stopping environment '{environment}': {e}"
            }

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
        
        return {
            "success": True,
            "message": f"Environment '{environment}' cleaned up successfully"
        }

    def get_environment_status(self, environment: str) -> Dict[str, Any]:
        """Get the status of an environment.

        Args:
            environment: Name of the environment

        Returns:
            Dictionary with environment status information
        """
        files = self.get_environment_files(environment)
        
        if not files["env_file"]:
            return {
                "error": f"Environment '{environment}' not found",
                "environment": environment,
                "active": False
            }
        
        try:
            # Build the docker-compose command
            cmd = ["docker", "compose"]
            
            # Add env file
            cmd.extend(["--env-file", str(files["env_file"].resolve())])
            
            # Add compose file
            if files["compose_file"]:
                cmd.extend(["-f", str(files["compose_file"].resolve())])
            
            # Get status
            cmd.extend(["ps", "--format", "json"])
            
            # Execute command from environment directory
            result = subprocess.run(
                cmd,
                cwd=str(files["env_dir"].resolve()),
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                import json
                services = []
                if result.stdout.strip():
                    for line in result.stdout.strip().split('\n'):
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
                    "services": {s["Name"]: {"state": s["State"], "health": s.get("Health", "unknown")} for s in services}
                }
            else:
                return {
                    "environment": environment,
                    "active": False,
                    "service_count": 0,
                    "healthy_services": 0,
                    "services": {}
                }
                
        except Exception as e:
            logger.error(f"Error getting status for environment '{environment}': {e}")
            return {
                "error": f"Error getting status: {e}",
                "environment": environment,
                "active": False
            }


# Maintain backward compatibility
EnvironmentManager = UnifiedEnvironmentManager