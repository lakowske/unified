#!/usr/bin/env python3
"""Parallel Container Build System for Unified Infrastructure

Builds container images in parallel while respecting build dependencies.
Logs all build output to the logs/ directory for tracking and debugging.

Features:
- Dependency-aware parallel building
- Build timing and performance metrics
- Comprehensive logging with timestamps
- Shared base image efficiency
- Build status tracking and error handling
"""

import asyncio
import json
import logging
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

# Configure logging
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

# Set up detailed logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
    handlers=[
        logging.FileHandler(log_dir / f"container-build-{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


@dataclass
class ContainerConfig:
    """Configuration for a container build"""

    name: str
    dockerfile_path: str
    build_context: str
    image_tag: str
    dependencies: List[str]
    description: str
    build_args: Optional[Dict[str, str]] = None


@dataclass
class BuildResult:
    """Result of a container build operation"""

    name: str
    success: bool
    build_time: float
    image_size: Optional[str]
    error_message: Optional[str]
    start_time: datetime
    end_time: datetime
    log_file: str


class ContainerBuilder:
    """Manages parallel container builds with dependency resolution"""

    def __init__(self):
        self.containers = self._define_containers()
        self.build_results: Dict[str, BuildResult] = {}
        self.build_start_time = datetime.now(timezone.utc)

    def _define_containers(self) -> Dict[str, ContainerConfig]:
        """Define all container configurations with dependencies"""
        return {
            "base-debian": ContainerConfig(
                name="base-debian",
                dockerfile_path="/home/seth/Software/dev/unified/containers/base-debian/Dockerfile",
                build_context="/home/seth/Software/dev/unified/containers/base-debian",
                image_tag="localhost/unified/base-debian:latest",
                dependencies=[],
                description="Shared base image with Python, tools, and certificate management",
            ),
            "postgres": ContainerConfig(
                name="postgres",
                dockerfile_path="/home/seth/Software/dev/unified/containers/postgres/Dockerfile",
                build_context="/home/seth/Software/dev/unified",
                image_tag="localhost/unified/postgres:latest",
                dependencies=["base-debian"],
                description="PostgreSQL server with unified tools",
            ),
            "volume-setup": ContainerConfig(
                name="volume-setup",
                dockerfile_path="/home/seth/Software/dev/unified/containers/volume-setup/Dockerfile",
                build_context="/home/seth/Software/dev/unified",
                image_tag="localhost/unified/volume-setup:latest",
                dependencies=["base-debian"],
                description="Volume initialization and permission setup",
            ),
            "apache": ContainerConfig(
                name="apache",
                dockerfile_path="/home/seth/Software/dev/unified/containers/apache/Dockerfile",
                build_context="/home/seth/Software/dev/unified",
                image_tag="localhost/unified/apache:latest",
                dependencies=["base-debian"],
                description="Apache web server with PHP and SSL support",
            ),
            "mail": ContainerConfig(
                name="mail",
                dockerfile_path="/home/seth/Software/dev/unified/containers/mail/Dockerfile",
                build_context="/home/seth/Software/dev/unified",
                image_tag="localhost/unified/mail:latest",
                dependencies=["base-debian"],
                description="Mail server with Postfix, Dovecot, and OpenDKIM",
            ),
            "dns": ContainerConfig(
                name="dns",
                dockerfile_path="/home/seth/Software/dev/unified/containers/dns/Dockerfile",
                build_context="/home/seth/Software/dev/unified",
                image_tag="localhost/unified/dns:latest",
                dependencies=["base-debian"],
                description="BIND DNS server with dynamic zone management",
            ),
        }

    def _get_build_order(self) -> List[List[str]]:
        """Calculate build order respecting dependencies using topological sort"""
        # Build dependency graph
        graph = {name: set(config.dependencies) for name, config in self.containers.items()}

        # Calculate levels for parallel building
        levels = []
        remaining = set(graph.keys())

        while remaining:
            # Find containers with no unbuilt dependencies
            ready = {name for name in remaining if not (graph[name] & remaining)}

            if not ready:
                raise ValueError(f"Circular dependency detected in: {remaining}")

            levels.append(sorted(ready))
            remaining -= ready

        logger.info(f"Build order calculated: {levels}")
        return levels

    async def _build_container(self, container_name: str) -> BuildResult:
        """Build a single container with comprehensive logging"""
        config = self.containers[container_name]
        start_time = datetime.now(timezone.utc)

        # Create container-specific log file
        log_file = log_dir / f"build-{container_name}-{start_time.strftime('%Y%m%d-%H%M%S')}.log"

        logger.info(f"Starting build: {container_name} - {config.description}")
        logger.info(f"Build context: {config.build_context}")
        logger.info(f"Dockerfile: {config.dockerfile_path}")
        logger.info(f"Target image: {config.image_tag}")
        logger.info(f"Build log: {log_file}")

        # Check if image already exists
        try:
            check_cmd = ["docker", "images", config.image_tag, "--format", "{{.Tag}}"]
            check_result = subprocess.run(check_cmd, capture_output=True, text=True)
            if check_result.returncode == 0 and check_result.stdout.strip():
                logger.info(f"✅ Image already exists: {container_name} - skipping build")

                # Get existing image info
                size_cmd = ["docker", "images", config.image_tag, "--format", "{{.Size}}"]
                size_result = subprocess.run(size_cmd, capture_output=True, text=True)
                image_size = size_result.stdout.strip() if size_result.returncode == 0 else "Unknown"

                # Log skip to file
                with open(log_file, "w") as log_handle:
                    log_handle.write(f"Container Build Log: {container_name}\n")
                    log_handle.write(f"Started: {start_time.isoformat()}\n")
                    log_handle.write("Status: SKIPPED - Image already exists\n")
                    log_handle.write(f"Target image: {config.image_tag}\n")
                    log_handle.write(f"Image size: {image_size}\n")

                return BuildResult(
                    name=container_name,
                    success=True,
                    build_time=0.0,
                    image_size=image_size,
                    error_message=None,
                    start_time=start_time,
                    end_time=start_time,
                    log_file=str(log_file),
                )
        except Exception as e:
            logger.warning(f"Could not check if image exists: {e}")

        try:
            # Build the container
            cmd = ["docker", "build", "-f", config.dockerfile_path, config.build_context, "-t", config.image_tag]

            # Add build args if specified
            if config.build_args:
                for key, value in config.build_args.items():
                    cmd.extend(["--build-arg", f"{key}={value}"])

            logger.info(f"Executing: {' '.join(cmd)}")

            # Run build with output capture
            with open(log_file, "w") as log_handle:
                log_handle.write(f"Container Build Log: {container_name}\n")
                log_handle.write(f"Started: {start_time.isoformat()}\n")
                log_handle.write(f"Command: {' '.join(cmd)}\n")
                log_handle.write("=" * 80 + "\n\n")

                process = await asyncio.create_subprocess_exec(
                    *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, cwd=Path.cwd()
                )

                # Stream output to log file and capture for analysis
                output_lines = []
                while True:
                    line = await process.stdout.readline()
                    if not line:
                        break

                    line_str = line.decode("utf-8", errors="replace")
                    output_lines.append(line_str)
                    log_handle.write(line_str)
                    log_handle.flush()

                await process.wait()

                end_time = datetime.now(timezone.utc)
                build_time = (end_time - start_time).total_seconds()

                log_handle.write("\n" + "=" * 80 + "\n")
                log_handle.write(f"Build completed: {end_time.isoformat()}\n")
                log_handle.write(f"Build time: {build_time:.2f} seconds\n")
                log_handle.write(f"Exit code: {process.returncode}\n")

                if process.returncode == 0:
                    # Get image size
                    try:
                        size_cmd = ["docker", "images", config.image_tag, "--format", "{{.Size}}"]
                        size_result = subprocess.run(size_cmd, capture_output=True, text=True)
                        image_size = size_result.stdout.strip() if size_result.returncode == 0 else "Unknown"
                    except Exception as e:
                        image_size = f"Error: {e}"

                    logger.info(f"✅ Build successful: {container_name} ({build_time:.2f}s, {image_size})")

                    return BuildResult(
                        name=container_name,
                        success=True,
                        build_time=build_time,
                        image_size=image_size,
                        error_message=None,
                        start_time=start_time,
                        end_time=end_time,
                        log_file=str(log_file),
                    )
                error_msg = f"Build failed with exit code {process.returncode}"
                logger.error(f"❌ Build failed: {container_name} - {error_msg}")

                return BuildResult(
                    name=container_name,
                    success=False,
                    build_time=build_time,
                    image_size=None,
                    error_message=error_msg,
                    start_time=start_time,
                    end_time=end_time,
                    log_file=str(log_file),
                )

        except Exception as e:
            end_time = datetime.now(timezone.utc)
            build_time = (end_time - start_time).total_seconds()
            error_msg = f"Build exception: {str(e)}"

            logger.error(f"❌ Build error: {container_name} - {error_msg}")

            # Log the error
            with open(log_file, "a") as log_handle:
                log_handle.write(f"\n\nBUILD ERROR:\n{error_msg}\n")

            return BuildResult(
                name=container_name,
                success=False,
                build_time=build_time,
                image_size=None,
                error_message=error_msg,
                start_time=start_time,
                end_time=end_time,
                log_file=str(log_file),
            )

    async def build_all(self) -> Dict[str, BuildResult]:
        """Build all containers in parallel respecting dependencies"""
        logger.info("🏗️  Starting parallel container build system")
        logger.info(f"Build start time: {self.build_start_time.isoformat()}")
        logger.info(f"Total containers to build: {len(self.containers)}")

        build_levels = self._get_build_order()

        for level_num, level_containers in enumerate(build_levels, 1):
            logger.info(f"📦 Building level {level_num}: {level_containers}")

            # Build all containers in this level in parallel
            tasks = [self._build_container(container_name) for container_name in level_containers]

            level_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results and check for failures
            level_success = True
            for result in level_results:
                if isinstance(result, Exception):
                    logger.error(f"❌ Unexpected error in level {level_num}: {result}")
                    level_success = False
                else:
                    self.build_results[result.name] = result
                    if not result.success:
                        level_success = False

            # Stop if any container in this level failed
            if not level_success:
                logger.error(f"❌ Level {level_num} failed, stopping build process")
                break

            logger.info(f"✅ Level {level_num} completed successfully")

        # Generate build summary
        self._generate_build_summary()

        return self.build_results

    def _generate_build_summary(self):
        """Generate comprehensive build summary and save to logs"""
        end_time = datetime.now(timezone.utc)
        total_time = (end_time - self.build_start_time).total_seconds()

        successful_builds = [r for r in self.build_results.values() if r.success]
        failed_builds = [r for r in self.build_results.values() if not r.success]

        summary = {
            "build_session": {
                "start_time": self.build_start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "total_time_seconds": total_time,
                "total_containers": len(self.containers),
                "successful_builds": len(successful_builds),
                "failed_builds": len(failed_builds),
            },
            "build_results": {name: asdict(result) for name, result in self.build_results.items()},
            "performance_metrics": {
                "fastest_build": min(successful_builds, key=lambda x: x.build_time).name if successful_builds else None,
                "slowest_build": max(successful_builds, key=lambda x: x.build_time).name if successful_builds else None,
                "average_build_time": sum(r.build_time for r in successful_builds) / len(successful_builds)
                if successful_builds
                else 0,
                "total_build_time": sum(r.build_time for r in self.build_results.values()),
            },
        }

        # Save summary to JSON
        summary_file = log_dir / f"build-summary-{self.build_start_time.strftime('%Y%m%d-%H%M%S')}.json"
        with open(summary_file, "w") as f:
            json.dump(summary, f, indent=2, default=str)

        # Log summary
        logger.info("=" * 80)
        logger.info("🎯 BUILD SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total build time: {total_time:.2f} seconds")
        logger.info(f"Successful builds: {len(successful_builds)}/{len(self.containers)}")
        logger.info(f"Failed builds: {len(failed_builds)}")

        if successful_builds:
            logger.info(f"Average build time: {summary['performance_metrics']['average_build_time']:.2f}s")
            logger.info(f"Fastest build: {summary['performance_metrics']['fastest_build']}")
            logger.info(f"Slowest build: {summary['performance_metrics']['slowest_build']}")

        if failed_builds:
            logger.error("❌ Failed builds:")
            for result in failed_builds:
                logger.error(f"  - {result.name}: {result.error_message}")

        logger.info(f"📊 Build summary saved: {summary_file}")
        logger.info("=" * 80)


async def main():
    """Main entry point for the build system"""
    builder = ContainerBuilder()

    try:
        results = await builder.build_all()

        # Exit with error code if any builds failed
        failed_count = sum(1 for r in results.values() if not r.success)
        if failed_count > 0:
            logger.error(f"❌ Build process completed with {failed_count} failures")
            sys.exit(1)
        else:
            logger.info("✅ All container builds completed successfully!")
            sys.exit(0)

    except KeyboardInterrupt:
        logger.warning("🛑 Build process interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"💥 Fatal error in build system: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
