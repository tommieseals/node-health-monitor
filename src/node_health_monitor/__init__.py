"""
Node Health Monitor - Multi-platform server health monitoring with alerts and auto-remediation.

A Python CLI + web dashboard that monitors multiple servers (Mac, Linux, Windows)
via SSH/API with configurable alert thresholds and auto-remediation hooks.
"""

__version__ = "1.0.0"
__author__ = "Tommie Seals"

from node_health_monitor.config import Config, NodeConfig, Thresholds
from node_health_monitor.monitor import HealthMonitor
from node_health_monitor.models import HealthStatus, NodeHealth, ServiceStatus

__all__ = [
    "Config",
    "NodeConfig", 
    "Thresholds",
    "HealthMonitor",
    "HealthStatus",
    "NodeHealth",
    "ServiceStatus",
]
