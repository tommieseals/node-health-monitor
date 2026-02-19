"""Data models for health monitoring."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class HealthStatus(str, Enum):
    """Health status levels."""
    
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNREACHABLE = "unreachable"
    UNKNOWN = "unknown"


@dataclass
class ServiceStatus:
    """Status of a monitored service."""
    
    name: str
    running: bool
    pid: int | None = None
    memory_mb: float | None = None
    cpu_percent: float | None = None
    uptime_seconds: int | None = None
    
    @property
    def status(self) -> HealthStatus:
        """Get health status based on running state."""
        return HealthStatus.HEALTHY if self.running else HealthStatus.CRITICAL


@dataclass
class MetricValue:
    """A metric with its value and status."""
    
    name: str
    value: float
    unit: str
    threshold_warning: float
    threshold_critical: float
    
    @property
    def status(self) -> HealthStatus:
        """Determine status based on thresholds."""
        if self.value >= self.threshold_critical:
            return HealthStatus.CRITICAL
        elif self.value >= self.threshold_warning:
            return HealthStatus.WARNING
        return HealthStatus.HEALTHY
    
    @property
    def percent_of_critical(self) -> float:
        """How close to critical threshold (0-100+)."""
        if self.threshold_critical == 0:
            return 0.0
        return (self.value / self.threshold_critical) * 100


@dataclass
class NodeHealth:
    """Complete health information for a single node."""
    
    name: str
    host: str
    platform: str  # "linux", "darwin", "windows"
    timestamp: datetime = field(default_factory=datetime.now)
    reachable: bool = True
    error_message: str | None = None
    
    # Resource metrics
    cpu_percent: float = 0.0
    cpu_count: int = 1
    load_average: tuple[float, float, float] = (0.0, 0.0, 0.0)
    
    memory_total_gb: float = 0.0
    memory_used_gb: float = 0.0
    memory_percent: float = 0.0
    
    disk_total_gb: float = 0.0
    disk_used_gb: float = 0.0
    disk_percent: float = 0.0
    
    # Services
    services: list[ServiceStatus] = field(default_factory=list)
    
    # Thresholds (set from config)
    thresholds: dict[str, tuple[float, float]] = field(default_factory=dict)
    
    @property
    def status(self) -> HealthStatus:
        """Overall node health status."""
        if not self.reachable:
            return HealthStatus.UNREACHABLE
        
        # Check all metrics against thresholds
        statuses = [
            self.memory_status,
            self.disk_status,
            self.load_status,
        ]
        
        # Add service statuses
        for svc in self.services:
            statuses.append(svc.status)
        
        if HealthStatus.CRITICAL in statuses:
            return HealthStatus.CRITICAL
        elif HealthStatus.WARNING in statuses:
            return HealthStatus.WARNING
        return HealthStatus.HEALTHY
    
    def _get_status(self, value: float, metric: str) -> HealthStatus:
        """Get status for a metric based on thresholds."""
        if metric not in self.thresholds:
            return HealthStatus.UNKNOWN
        warning, critical = self.thresholds[metric]
        if value >= critical:
            return HealthStatus.CRITICAL
        elif value >= warning:
            return HealthStatus.WARNING
        return HealthStatus.HEALTHY
    
    @property
    def memory_status(self) -> HealthStatus:
        return self._get_status(self.memory_percent, "memory")
    
    @property
    def disk_status(self) -> HealthStatus:
        return self._get_status(self.disk_percent, "disk")
    
    @property
    def load_status(self) -> HealthStatus:
        # Use 1-minute load average, normalized by CPU count
        normalized_load = self.load_average[0] / max(self.cpu_count, 1)
        return self._get_status(normalized_load, "load")
    
    def get_alerts(self) -> list[str]:
        """Get list of alert messages for this node."""
        alerts = []
        
        if not self.reachable:
            alerts.append(f"Node unreachable: {self.error_message or 'Connection failed'}")
            return alerts
        
        if self.memory_status == HealthStatus.CRITICAL:
            alerts.append(f"CRITICAL: Memory at {self.memory_percent:.1f}%")
        elif self.memory_status == HealthStatus.WARNING:
            alerts.append(f"WARNING: Memory at {self.memory_percent:.1f}%")
        
        if self.disk_status == HealthStatus.CRITICAL:
            alerts.append(f"CRITICAL: Disk at {self.disk_percent:.1f}%")
        elif self.disk_status == HealthStatus.WARNING:
            alerts.append(f"WARNING: Disk at {self.disk_percent:.1f}%")
        
        if self.load_status == HealthStatus.CRITICAL:
            alerts.append(f"CRITICAL: Load average {self.load_average[0]:.2f}")
        elif self.load_status == HealthStatus.WARNING:
            alerts.append(f"WARNING: Load average {self.load_average[0]:.2f}")
        
        for svc in self.services:
            if not svc.running:
                alerts.append(f"CRITICAL: Service '{svc.name}' is not running")
        
        return alerts
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "host": self.host,
            "platform": self.platform,
            "timestamp": self.timestamp.isoformat(),
            "reachable": self.reachable,
            "status": self.status.value,
            "error_message": self.error_message,
            "metrics": {
                "cpu": {
                    "percent": self.cpu_percent,
                    "count": self.cpu_count,
                    "load_average": list(self.load_average),
                },
                "memory": {
                    "total_gb": self.memory_total_gb,
                    "used_gb": self.memory_used_gb,
                    "percent": self.memory_percent,
                    "status": self.memory_status.value,
                },
                "disk": {
                    "total_gb": self.disk_total_gb,
                    "used_gb": self.disk_used_gb,
                    "percent": self.disk_percent,
                    "status": self.disk_status.value,
                },
            },
            "services": [
                {
                    "name": s.name,
                    "running": s.running,
                    "pid": s.pid,
                    "status": s.status.value,
                }
                for s in self.services
            ],
            "alerts": self.get_alerts(),
        }


@dataclass
class ClusterHealth:
    """Health status for the entire cluster."""
    
    nodes: list[NodeHealth] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    
    @property
    def status(self) -> HealthStatus:
        """Overall cluster health."""
        if not self.nodes:
            return HealthStatus.UNKNOWN
        
        statuses = [n.status for n in self.nodes]
        
        if HealthStatus.UNREACHABLE in statuses or HealthStatus.CRITICAL in statuses:
            return HealthStatus.CRITICAL
        elif HealthStatus.WARNING in statuses:
            return HealthStatus.WARNING
        return HealthStatus.HEALTHY
    
    @property
    def healthy_count(self) -> int:
        return sum(1 for n in self.nodes if n.status == HealthStatus.HEALTHY)
    
    @property
    def warning_count(self) -> int:
        return sum(1 for n in self.nodes if n.status == HealthStatus.WARNING)
    
    @property
    def critical_count(self) -> int:
        return sum(1 for n in self.nodes if n.status in (HealthStatus.CRITICAL, HealthStatus.UNREACHABLE))
    
    def get_all_alerts(self) -> list[tuple[str, str]]:
        """Get all alerts as (node_name, message) tuples."""
        alerts = []
        for node in self.nodes:
            for alert in node.get_alerts():
                alerts.append((node.name, alert))
        return alerts
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "status": self.status.value,
            "summary": {
                "total": len(self.nodes),
                "healthy": self.healthy_count,
                "warning": self.warning_count,
                "critical": self.critical_count,
            },
            "nodes": [n.to_dict() for n in self.nodes],
            "alerts": [{"node": n, "message": m} for n, m in self.get_all_alerts()],
        }
