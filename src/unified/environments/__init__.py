"""Environment management for unified infrastructure.

This package provides comprehensive environment management capabilities including:
- Environment configuration parsing and validation
- Environment lifecycle management (create, start, stop, remove)
- Network information queries (ports, URLs, health checks)
- Environment isolation utilities for testing and development
"""

from .config import EnvironmentConfig
from .isolation import EnvironmentIsolation
from .manager import EnvironmentManager, UnifiedEnvironmentManager
from .network import NetworkInfo

__all__ = [
    "EnvironmentConfig",
    "EnvironmentManager",
    "UnifiedEnvironmentManager",
    "NetworkInfo",
    "EnvironmentIsolation",
]
