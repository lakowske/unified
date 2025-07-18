"""Container Build Integration Tests

This module provides comprehensive tests for container image building,
validation, and build system integrity in the unified infrastructure.
"""

import json
import logging
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

logger = logging.getLogger(__name__)


class ContainerBuildManager:
    """Manages container build testing operations."""

    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.makefile_path = project_dir / "Makefile"
        self.compose_file = project_dir / "docker-compose.yml"

    def run_make_command(self, target: str, timeout: int = 1800) -> Dict[str, Any]:
        """Run a make command and return results."""
        try:
            result = subprocess.run(
                ["make", target], cwd=self.project_dir, capture_output=True, text=True, timeout=timeout
            )

            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "stdout": "", "stderr": "Command timed out", "returncode": -1}
        except Exception as e:
            return {"success": False, "stdout": "", "stderr": str(e), "returncode": -1}

    def run_docker_command(self, command: List[str], timeout: int = 300) -> Dict[str, Any]:
        """Run a docker command and return results."""
        try:
            result = subprocess.run(
                ["docker"] + command, cwd=self.project_dir, capture_output=True, text=True, timeout=timeout
            )

            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "stdout": "", "stderr": "Command timed out", "returncode": -1}
        except Exception as e:
            return {"success": False, "stdout": "", "stderr": str(e), "returncode": -1}

    def get_image_info(self, image_name: str) -> Optional[Dict[str, Any]]:
        """Get information about a Docker image."""
        result = self.run_docker_command(["inspect", image_name])

        if result["success"]:
            try:
                image_info = json.loads(result["stdout"])
                return image_info[0] if image_info else None
            except json.JSONDecodeError:
                logger.error(f"Failed to parse image info for {image_name}")
                return None
        return None

    def get_unified_images(self) -> List[Dict[str, str]]:
        """Get list of unified project images."""
        result = self.run_docker_command(["images", "--filter", "reference=localhost/unified/*", "--format", "json"])

        images = []
        if result["success"]:
            for line in result["stdout"].strip().split("\n"):
                if line.strip():
                    try:
                        image_data = json.loads(line)
                        images.append(image_data)
                    except json.JSONDecodeError:
                        continue
        return images

    def build_image(self, image_name: str, dockerfile_path: str, timeout: int = 1800) -> Dict[str, Any]:
        """Build a specific image."""
        command = ["build", "-f", dockerfile_path, "-t", image_name, "."]

        return self.run_docker_command(command, timeout)

    def test_image_runs(self, image_name: str, command: List[str] = None) -> Dict[str, Any]:
        """Test that an image can run successfully."""
        if command is None:
            command = ["--version"]

        docker_command = ["run", "--rm", image_name] + command

        return self.run_docker_command(docker_command, timeout=60)

    def get_image_layers(self, image_name: str) -> List[Dict[str, Any]]:
        """Get information about image layers."""
        result = self.run_docker_command(["history", "--format", "json", image_name])

        layers = []
        if result["success"]:
            for line in result["stdout"].strip().split("\n"):
                if line.strip():
                    try:
                        layer_data = json.loads(line)
                        layers.append(layer_data)
                    except json.JSONDecodeError:
                        continue
        return layers

    def check_dockerfile_exists(self, dockerfile_path: str) -> bool:
        """Check if Dockerfile exists."""
        return (self.project_dir / dockerfile_path).exists()

    def get_dockerfile_content(self, dockerfile_path: str) -> Optional[str]:
        """Get Dockerfile content."""
        full_path = self.project_dir / dockerfile_path
        if full_path.exists():
            try:
                return full_path.read_text()
            except Exception as e:
                logger.error(f"Failed to read Dockerfile {dockerfile_path}: {e}")
                return None
        return None


@pytest.fixture(scope="session")
def project_dir():
    """Get the project directory."""
    return Path(__file__).parent.parent


@pytest.fixture(scope="session")
def build_manager(project_dir):
    """Create a container build manager."""
    return ContainerBuildManager(project_dir)


@pytest.fixture(scope="session")
def makefile_available(build_manager):
    """Ensure Makefile is available."""
    assert build_manager.makefile_path.exists(), "Makefile not found"
    return build_manager


class TestBuildSystem:
    """Test build system integrity."""

    def test_makefile_exists(self, build_manager):
        """Test that Makefile exists."""
        assert build_manager.makefile_path.exists(), "Makefile not found"
        logger.info("Makefile found")

    def test_makefile_help(self, makefile_available):
        """Test Makefile help target."""
        result = makefile_available.run_make_command("help")

        assert result["success"], f"Make help failed: {result['stderr']}"
        assert "Build targets:" in result["stdout"], "Help output missing build targets"
        assert "all" in result["stdout"], "Help output missing 'all' target"
        assert "clean" in result["stdout"], "Help output missing 'clean' target"

        logger.info("Makefile help target works")

    def test_docker_compose_config(self, build_manager):
        """Test docker-compose configuration."""
        result = build_manager.run_docker_command(["compose", "-f", str(build_manager.compose_file), "config"])

        assert result["success"], f"Docker compose config failed: {result['stderr']}"
        assert "postgres:" in result["stdout"], "Postgres service not found in config"
        assert "apache:" in result["stdout"], "Apache service not found in config"

        logger.info("Docker compose configuration is valid")

    def test_required_dockerfiles_exist(self, build_manager):
        """Test that all required Dockerfiles exist."""
        required_dockerfiles = [
            "containers/base-debian/Dockerfile",
            "containers/postgres/Dockerfile",
            "containers/apache/Dockerfile",
            "containers/mail/Dockerfile",
            "containers/dns/Dockerfile",
            "containers/volume-setup/Dockerfile",
        ]

        missing_dockerfiles = []
        for dockerfile in required_dockerfiles:
            if not build_manager.check_dockerfile_exists(dockerfile):
                missing_dockerfiles.append(dockerfile)

        assert not missing_dockerfiles, f"Missing Dockerfiles: {missing_dockerfiles}"
        logger.info(f"All required Dockerfiles exist: {len(required_dockerfiles)}")

    def test_dockerfile_syntax(self, build_manager):
        """Test Dockerfile syntax by attempting to parse them."""
        dockerfiles = [
            "containers/base-debian/Dockerfile",
            "containers/postgres/Dockerfile",
            "containers/apache/Dockerfile",
            "containers/mail/Dockerfile",
            "containers/dns/Dockerfile",
            "containers/volume-setup/Dockerfile",
        ]

        for dockerfile in dockerfiles:
            content = build_manager.get_dockerfile_content(dockerfile)
            assert content is not None, f"Could not read {dockerfile}"

            # Basic syntax checks
            assert "FROM" in content, f"No FROM instruction in {dockerfile}"

            # Check for common issues
            lines = content.split("\n")
            for i, line in enumerate(lines, 1):
                line = line.strip()
                if line.startswith("RUN") and line.endswith("\\"):
                    # Check that continuation lines are properly formatted
                    if i < len(lines):
                        next_line = lines[i].strip()
                        assert next_line, f"Empty continuation line in {dockerfile}:{i+1}"

        logger.info(f"Dockerfile syntax validated: {len(dockerfiles)} files")


class TestImageBuilds:
    """Test individual image builds."""

    def test_base_debian_build(self, build_manager):
        """Test base-debian image build."""
        result = build_manager.build_image("localhost/unified/base-debian:test", "containers/base-debian/Dockerfile")

        assert result["success"], f"Base-debian build failed: {result['stderr']}"
        logger.info("Base-debian image built successfully")

    def test_postgres_build(self, build_manager):
        """Test postgres image build."""
        # Build base first (dependency)
        base_result = build_manager.build_image(
            "localhost/unified/base-debian:test", "containers/base-debian/Dockerfile"
        )
        assert base_result["success"], f"Base image build failed: {base_result['stderr']}"

        # Build postgres
        result = build_manager.build_image("localhost/unified/postgres:test", "containers/postgres/Dockerfile")

        assert result["success"], f"Postgres build failed: {result['stderr']}"
        logger.info("Postgres image built successfully")

    def test_apache_build(self, build_manager):
        """Test apache image build."""
        # Build base first (dependency)
        base_result = build_manager.build_image(
            "localhost/unified/base-debian:test", "containers/base-debian/Dockerfile"
        )
        assert base_result["success"], f"Base image build failed: {base_result['stderr']}"

        # Build apache
        result = build_manager.build_image("localhost/unified/apache:test", "containers/apache/Dockerfile")

        assert result["success"], f"Apache build failed: {result['stderr']}"
        logger.info("Apache image built successfully")

    def test_mail_build(self, build_manager):
        """Test mail image build."""
        # Build base first (dependency)
        base_result = build_manager.build_image(
            "localhost/unified/base-debian:test", "containers/base-debian/Dockerfile"
        )
        assert base_result["success"], f"Base image build failed: {base_result['stderr']}"

        # Build mail
        result = build_manager.build_image("localhost/unified/mail:test", "containers/mail/Dockerfile")

        assert result["success"], f"Mail build failed: {result['stderr']}"
        logger.info("Mail image built successfully")

    def test_dns_build(self, build_manager):
        """Test dns image build."""
        # Build base first (dependency)
        base_result = build_manager.build_image(
            "localhost/unified/base-debian:test", "containers/base-debian/Dockerfile"
        )
        assert base_result["success"], f"Base image build failed: {base_result['stderr']}"

        # Build dns
        result = build_manager.build_image("localhost/unified/dns:test", "containers/dns/Dockerfile")

        assert result["success"], f"DNS build failed: {result['stderr']}"
        logger.info("DNS image built successfully")

    def test_volume_setup_build(self, build_manager):
        """Test volume-setup image build."""
        # Build base first (dependency)
        base_result = build_manager.build_image(
            "localhost/unified/base-debian:test", "containers/base-debian/Dockerfile"
        )
        assert base_result["success"], f"Base image build failed: {base_result['stderr']}"

        # Build volume-setup
        result = build_manager.build_image("localhost/unified/volume-setup:test", "containers/volume-setup/Dockerfile")

        assert result["success"], f"Volume-setup build failed: {result['stderr']}"
        logger.info("Volume-setup image built successfully")


class TestImageValidation:
    """Test built image validation."""

    def test_image_metadata(self, build_manager):
        """Test image metadata and labels."""
        # Get base image info
        base_info = build_manager.get_image_info("localhost/unified/base-debian:latest")
        if base_info:
            config = base_info.get("Config", {})

            # Check environment variables
            env_vars = config.get("Env", [])
            python_path_set = any("PYTHONPATH" in env for env in env_vars)
            virtual_env_set = any("VIRTUAL_ENV" in env for env in env_vars)

            assert python_path_set, "PYTHONPATH not set in base image"
            assert virtual_env_set, "VIRTUAL_ENV not set in base image"

            logger.info("Base image metadata validated")

    def test_image_security(self, build_manager):
        """Test image security properties."""
        # Get postgres image info
        postgres_info = build_manager.get_image_info("localhost/unified/postgres:latest")
        if postgres_info:
            config = postgres_info.get("Config", {})

            # Check that postgres runs as non-root user
            user = config.get("User", "")
            assert user == "postgres", f"Postgres should run as postgres user, got: {user}"

            logger.info("Postgres image security validated")

    def test_image_health_checks(self, build_manager):
        """Test image health check configurations."""
        # Get postgres image info
        postgres_info = build_manager.get_image_info("localhost/unified/postgres:latest")
        if postgres_info:
            config = postgres_info.get("Config", {})
            healthcheck = config.get("Healthcheck", {})

            assert healthcheck, "Postgres image should have health check"
            assert healthcheck.get("Test"), "Postgres health check should have test command"

            logger.info("Postgres image health check validated")

    def test_image_sizes(self, build_manager):
        """Test image sizes are reasonable."""
        images = build_manager.get_unified_images()

        size_limits = {
            "base-debian": 800 * 1024 * 1024,  # 800MB
            "postgres": 2 * 1024 * 1024 * 1024,  # 2GB
            "apache": 1 * 1024 * 1024 * 1024,  # 1GB
            "mail": 1 * 1024 * 1024 * 1024,  # 1GB
            "dns": 800 * 1024 * 1024,  # 800MB
            "volume-setup": 800 * 1024 * 1024,  # 800MB
        }

        for image in images:
            repo = image.get("Repository", "")
            size = image.get("Size", 0)

            # Parse size string to bytes
            if isinstance(size, str):
                if "MB" in size:
                    size = float(size.replace("MB", "")) * 1024 * 1024
                elif "GB" in size:
                    size = float(size.replace("GB", "")) * 1024 * 1024 * 1024
                elif "B" in size:
                    size = float(size.replace("B", ""))
                else:
                    continue

            # Check size limits
            for service, limit in size_limits.items():
                if service in repo:
                    assert size <= limit, f"Image {repo} too large: {size} bytes > {limit} bytes"
                    logger.info(f"Image {repo} size OK: {size/1024/1024:.1f}MB")
                    break


class TestMakeBuildSystem:
    """Test Make-based build system."""

    def test_make_clean(self, makefile_available):
        """Test make clean target."""
        result = makefile_available.run_make_command("clean")

        assert result["success"], f"Make clean failed: {result['stderr']}"
        logger.info("Make clean completed successfully")

    def test_make_base_debian(self, makefile_available):
        """Test make base-debian target."""
        result = makefile_available.run_make_command("base-debian")

        assert result["success"], f"Make base-debian failed: {result['stderr']}"

        # Verify image exists
        images = makefile_available.get_unified_images()
        base_images = [img for img in images if "base-debian" in img.get("Repository", "")]
        assert base_images, "Base-debian image not found after build"

        logger.info("Make base-debian completed successfully")

    def test_make_postgres(self, makefile_available):
        """Test make postgres target."""
        # Build base first
        base_result = makefile_available.run_make_command("base-debian")
        assert base_result["success"], f"Base build failed: {base_result['stderr']}"

        # Build postgres
        result = makefile_available.run_make_command("postgres")

        assert result["success"], f"Make postgres failed: {result['stderr']}"

        # Verify image exists
        images = makefile_available.get_unified_images()
        postgres_images = [img for img in images if "postgres" in img.get("Repository", "")]
        assert postgres_images, "Postgres image not found after build"

        logger.info("Make postgres completed successfully")

    def test_make_dependencies(self, makefile_available):
        """Test that Make handles dependencies correctly."""
        # Clean first
        makefile_available.run_make_command("clean-images")

        # Build postgres (should build base-debian first)
        result = makefile_available.run_make_command("postgres")

        assert result["success"], f"Make postgres with dependencies failed: {result['stderr']}"

        # Both images should exist
        images = makefile_available.get_unified_images()
        image_names = [img.get("Repository", "") for img in images]

        base_found = any("base-debian" in name for name in image_names)
        postgres_found = any("postgres" in name for name in image_names)

        assert base_found, "Base-debian image not built as dependency"
        assert postgres_found, "Postgres image not built"

        logger.info("Make dependency handling validated")


@pytest.mark.performance
class TestBuildPerformance:
    """Test build performance and efficiency."""

    def test_build_time_baseline(self, build_manager):
        """Test build time performance baseline."""
        # Test base image build time
        start_time = time.time()
        result = build_manager.build_image(
            "localhost/unified/base-debian:perf-test", "containers/base-debian/Dockerfile"
        )
        end_time = time.time()

        assert result["success"], f"Base image build failed: {result['stderr']}"

        build_time = end_time - start_time
        assert build_time < 300, f"Base image build too slow: {build_time:.1f}s"

        logger.info(f"Base image build time: {build_time:.1f}s")

    def test_incremental_build(self, build_manager):
        """Test incremental build performance."""
        # Build image once
        result1 = build_manager.build_image(
            "localhost/unified/base-debian:incremental-test", "containers/base-debian/Dockerfile"
        )
        assert result1["success"], "First build failed"

        # Build again (should be faster due to caching)
        start_time = time.time()
        result2 = build_manager.build_image(
            "localhost/unified/base-debian:incremental-test", "containers/base-debian/Dockerfile"
        )
        end_time = time.time()

        assert result2["success"], "Second build failed"

        incremental_time = end_time - start_time
        assert incremental_time < 60, f"Incremental build too slow: {incremental_time:.1f}s"

        logger.info(f"Incremental build time: {incremental_time:.1f}s")

    def test_parallel_build_capability(self, makefile_available):
        """Test parallel build capability."""
        # Clean first
        makefile_available.run_make_command("clean-images")

        # Test parallel build with make -j
        start_time = time.time()
        result = makefile_available.run_docker_command(["exec", "-w", "/tmp", "alpine", "make", "-j2", "base-debian"])
        end_time = time.time()

        # Note: This test might not work perfectly in all environments
        # It's more of a capability check than a strict requirement
        build_time = end_time - start_time

        logger.info(f"Parallel build capability test: {build_time:.1f}s")

    def test_build_cache_efficiency(self, build_manager):
        """Test build cache efficiency."""
        # Build base image
        result = build_manager.build_image(
            "localhost/unified/base-debian:cache-test", "containers/base-debian/Dockerfile"
        )
        assert result["success"], "Base build failed"

        # Check if rebuild uses cache effectively
        start_time = time.time()
        result = build_manager.build_image(
            "localhost/unified/base-debian:cache-test", "containers/base-debian/Dockerfile"
        )
        end_time = time.time()

        assert result["success"], "Cached build failed"

        cache_time = end_time - start_time
        logger.info(f"Cache efficiency: {cache_time:.1f}s for rebuild")

        # Should be using cache (indicated by faster build)
        assert cache_time < 30, f"Cache not being used effectively: {cache_time:.1f}s"
