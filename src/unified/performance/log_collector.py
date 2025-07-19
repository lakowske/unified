"""Container log collection for performance testing.

This module provides functionality to collect logs from Docker containers
during performance testing for comprehensive debugging and analysis.
"""

import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ContainerLogCollector:
    """Collects logs from Docker containers for performance analysis."""

    def __init__(self, output_dir: Path):
        """Initialize container log collector.

        Args:
            output_dir: Directory to save container logs
        """
        self.output_dir = Path(output_dir)
        self.logs_dir = self.output_dir / "container-logs"
        self.server_logs_dir = self.output_dir / "server-logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.server_logs_dir.mkdir(parents=True, exist_ok=True)

    def collect_container_logs(self, container_names: List[str]) -> Dict[str, Dict[str, str]]:
        """Collect logs from specified containers.

        Args:
            container_names: List of container names to collect logs from

        Returns:
            Dictionary mapping container names to log collection results
        """
        results = {}

        logger.info(f"Collecting logs from {len(container_names)} containers")

        for container_name in container_names:
            try:
                log_result = self._collect_single_container_log(container_name)
                results[container_name] = log_result

                if log_result["success"]:
                    logger.info(f"Successfully collected logs for {container_name}")
                else:
                    logger.warning(f"Failed to collect logs for {container_name}: {log_result['error']}")

            except Exception as e:
                logger.error(f"Error collecting logs for {container_name}: {e}")
                results[container_name] = {"success": False, "error": str(e), "log_file": None, "log_size": 0}

        return results

    def _collect_single_container_log(self, container_name: str) -> Dict[str, str]:
        """Collect logs from a single container.

        Args:
            container_name: Name of the container

        Returns:
            Dictionary with collection results
        """
        log_file = self.logs_dir / f"{container_name}.log"

        try:
            # Check if container exists
            check_cmd = ["docker", "inspect", container_name]
            check_result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=10)

            if check_result.returncode != 0:
                return {
                    "success": False,
                    "error": f"Container {container_name} not found",
                    "log_file": None,
                    "log_size": 0,
                }

            # Collect logs with timestamps
            logs_cmd = ["docker", "logs", "--timestamps", "--details", container_name]

            logs_result = subprocess.run(logs_cmd, capture_output=True, text=True, timeout=30)

            # Create log content with header
            timestamp = datetime.now().isoformat()
            log_content = f"""# Container Log Collection
# Container: {container_name}
# Collection Time: {timestamp}
# Command: {' '.join(logs_cmd)}
# Exit Code: {logs_result.returncode}
# ================================================================================

"""

            # Add stdout if available
            if logs_result.stdout:
                log_content += "# STDOUT:\n"
                log_content += logs_result.stdout
                log_content += "\n\n"

            # Add stderr if available
            if logs_result.stderr:
                log_content += "# STDERR:\n"
                log_content += logs_result.stderr
                log_content += "\n\n"

            # If no output, note that
            if not logs_result.stdout and not logs_result.stderr:
                log_content += "# No log output captured\n"

            # Write log file
            with open(log_file, "w", encoding="utf-8") as f:
                f.write(log_content)

            log_size = log_file.stat().st_size

            return {
                "success": True,
                "error": None,
                "log_file": str(log_file),
                "log_size": log_size,
                "exit_code": logs_result.returncode,
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": f"Timeout collecting logs for {container_name}",
                "log_file": None,
                "log_size": 0,
            }
        except Exception as e:
            return {"success": False, "error": f"Error collecting logs: {str(e)}", "log_file": None, "log_size": 0}

    def collect_system_info(self) -> Dict[str, str]:
        """Collect system information for debugging context.

        Returns:
            Dictionary with system information
        """
        info = {}

        try:
            # Docker version
            docker_version = subprocess.run(["docker", "--version"], capture_output=True, text=True, timeout=10)
            info["docker_version"] = docker_version.stdout.strip() if docker_version.returncode == 0 else "Unknown"

            # Docker compose version
            compose_version = subprocess.run(
                ["docker", "compose", "version"], capture_output=True, text=True, timeout=10
            )
            info["compose_version"] = compose_version.stdout.strip() if compose_version.returncode == 0 else "Unknown"

            # System info
            info["collection_time"] = datetime.now().isoformat()

        except Exception as e:
            logger.warning(f"Could not collect system info: {e}")
            info["error"] = str(e)

        return info

    def collect_server_logs(self, environment_name: str) -> Dict[str, str]:
        """Collect server logs from /data/logs volume.

        Args:
            environment_name: Name of the environment to collect logs from

        Returns:
            Dictionary with server log collection results
        """
        logger.info(f"Collecting server logs from /data/logs volume for {environment_name}")

        try:
            # Use docker run to access the logs volume and copy contents
            volume_name = f"logs-{environment_name}"

            # Create a timestamp for this collection
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            collection_dir = self.server_logs_dir / f"{environment_name}-{timestamp}"
            collection_dir.mkdir(parents=True, exist_ok=True)

            # Use docker run with the logs volume to copy all log files
            copy_cmd = [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{volume_name}:/source:ro",
                "-v",
                f"{collection_dir.absolute()}:/dest",
                "alpine:latest",
                "sh",
                "-c",
                "cp -r /source/* /dest/ 2>/dev/null || echo 'No logs found'",
            ]

            logger.debug(f"Running command: {' '.join(copy_cmd)}")

            copy_result = subprocess.run(copy_cmd, capture_output=True, text=True, timeout=60)

            if copy_result.returncode == 0:
                # Count files and calculate total size
                log_files = list(collection_dir.rglob("*"))
                log_files = [f for f in log_files if f.is_file()]
                total_size = sum(f.stat().st_size for f in log_files)

                # Create a summary of what was collected
                summary_file = collection_dir / "collection-summary.txt"
                with open(summary_file, "w") as f:
                    f.write("Server Log Collection Summary\n")
                    f.write(f"Environment: {environment_name}\n")
                    f.write(f"Collection Time: {datetime.now().isoformat()}\n")
                    f.write(f"Volume: {volume_name}\n")
                    f.write(f"Files Collected: {len(log_files)}\n")
                    f.write(f"Total Size: {total_size} bytes\n")
                    f.write(f"Collection Directory: {collection_dir}\n\n")

                    f.write("Files:\n")
                    for log_file in sorted(log_files):
                        rel_path = log_file.relative_to(collection_dir)
                        file_size = log_file.stat().st_size
                        f.write(f"  {rel_path} ({file_size} bytes)\n")

                logger.info(f"Successfully collected {len(log_files)} server log files ({total_size} bytes)")

                return {
                    "success": True,
                    "error": None,
                    "collection_dir": str(collection_dir),
                    "files_collected": len(log_files),
                    "total_size": total_size,
                    "volume_name": volume_name,
                }
            error_msg = f"Failed to copy logs: {copy_result.stderr}"
            logger.warning(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "collection_dir": None,
                "files_collected": 0,
                "total_size": 0,
                "volume_name": volume_name,
            }

        except subprocess.TimeoutExpired:
            error_msg = f"Timeout copying server logs for {environment_name}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "collection_dir": None,
                "files_collected": 0,
                "total_size": 0,
                "volume_name": f"logs-{environment_name}",
            }
        except Exception as e:
            error_msg = f"Error collecting server logs: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "collection_dir": None,
                "files_collected": 0,
                "total_size": 0,
                "volume_name": f"logs-{environment_name}",
            }

    def save_collection_summary(
        self,
        collection_results: Dict[str, Dict[str, str]],
        system_info: Dict[str, str],
        server_logs_result: Optional[Dict[str, str]] = None,
    ) -> Path:
        """Save a summary of log collection results.

        Args:
            collection_results: Results from container log collection
            system_info: System information
            server_logs_result: Results from server logs collection

        Returns:
            Path to summary file
        """
        summary_file = self.output_dir / "log-collection-summary.json"

        # Calculate total container log size
        container_log_size = sum(r.get("log_size", 0) for r in collection_results.values())

        summary = {
            "collection_timestamp": datetime.now().isoformat(),
            "system_info": system_info,
            "containers_processed": len(collection_results),
            "successful_collections": sum(1 for r in collection_results.values() if r["success"]),
            "failed_collections": sum(1 for r in collection_results.values() if not r["success"]),
            "total_container_log_size_bytes": container_log_size,
            "collection_results": collection_results,
        }

        # Add server logs information if available
        if server_logs_result:
            summary["server_logs"] = server_logs_result
            summary["total_server_log_size_bytes"] = server_logs_result.get("total_size", 0)
            summary["total_combined_log_size_bytes"] = container_log_size + server_logs_result.get("total_size", 0)
        else:
            summary["server_logs"] = None
            summary["total_server_log_size_bytes"] = 0
            summary["total_combined_log_size_bytes"] = container_log_size

        import json

        with open(summary_file, "w") as f:
            json.dump(summary, f, indent=2)

        logger.info(f"Log collection summary saved to {summary_file}")
        return summary_file
