"""Configuration management for Node Health Monitor."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class Thresholds:
    """Alert thresholds for health metrics."""
    
    memory_warning: float = 80.0
    memory_critical: float = 90.0
    disk_warning: float = 80.0
    disk_critical: float = 90.0
    load_warning: float = 4.0  # Normalized by CPU count
    load_critical: float = 8.0
    
    def to_dict(self) -> dict[str, tuple[float, float]]:
        """Convert to threshold dict for NodeHealth."""
        return {
            "memory": (self.memory_warning, self.memory_critical),
            "disk": (self.disk_warning, self.disk_critical),
            "load": (self.load_warning, self.load_critical),
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Thresholds":
        """Create from dictionary."""
        return cls(
            memory_warning=data.get("memory_warning", 80.0),
            memory_critical=data.get("memory_critical", 90.0),
            disk_warning=data.get("disk_warning", 80.0),
            disk_critical=data.get("disk_critical", 90.0),
            load_warning=data.get("load_warning", 4.0),
            load_critical=data.get("load_critical", 8.0),
        )


@dataclass
class SSHConfig:
    """SSH connection configuration."""
    
    username: str
    host: str
    port: int = 22
    key_file: str | None = None
    password: str | None = None
    timeout: int = 10
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SSHConfig":
        return cls(
            username=data["username"],
            host=data["host"],
            port=data.get("port", 22),
            key_file=data.get("key_file"),
            password=data.get("password"),
            timeout=data.get("timeout", 10),
        )


@dataclass
class RemediationConfig:
    """Auto-remediation configuration."""
    
    enabled: bool = False
    scripts_dir: str = "./remediation"
    on_high_memory: str | None = None
    on_high_disk: str | None = None
    on_high_load: str | None = None
    on_service_down: dict[str, str] = field(default_factory=dict)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RemediationConfig":
        return cls(
            enabled=data.get("enabled", False),
            scripts_dir=data.get("scripts_dir", "./remediation"),
            on_high_memory=data.get("on_high_memory"),
            on_high_disk=data.get("on_high_disk"),
            on_high_load=data.get("on_high_load"),
            on_service_down=data.get("on_service_down", {}),
        )


@dataclass
class NodeConfig:
    """Configuration for a single monitored node."""
    
    name: str
    platform: str  # "linux", "darwin", "windows"
    enabled: bool = True
    local: bool = False  # If true, monitor localhost
    ssh: SSHConfig | None = None
    services: list[str] = field(default_factory=list)
    thresholds: Thresholds | None = None  # Override global thresholds
    remediation: RemediationConfig | None = None
    tags: list[str] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> "NodeConfig":
        ssh = SSHConfig.from_dict(data["ssh"]) if "ssh" in data else None
        thresholds = Thresholds.from_dict(data["thresholds"]) if "thresholds" in data else None
        remediation = RemediationConfig.from_dict(data["remediation"]) if "remediation" in data else None
        
        return cls(
            name=name,
            platform=data.get("platform", "linux"),
            enabled=data.get("enabled", True),
            local=data.get("local", False),
            ssh=ssh,
            services=data.get("services", []),
            thresholds=thresholds,
            remediation=remediation,
            tags=data.get("tags", []),
        )


@dataclass
class NotifierConfig:
    """Configuration for alert notifiers."""
    
    telegram: dict[str, Any] | None = None
    slack: dict[str, Any] | None = None
    webhook: dict[str, Any] | None = None
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NotifierConfig":
        return cls(
            telegram=data.get("telegram"),
            slack=data.get("slack"),
            webhook=data.get("webhook"),
        )


@dataclass
class DashboardConfig:
    """Web dashboard configuration."""
    
    enabled: bool = True
    host: str = "0.0.0.0"
    port: int = 8080
    refresh_interval: int = 30  # seconds
    auth_enabled: bool = False
    username: str | None = None
    password: str | None = None
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DashboardConfig":
        return cls(
            enabled=data.get("enabled", True),
            host=data.get("host", "0.0.0.0"),
            port=data.get("port", 8080),
            refresh_interval=data.get("refresh_interval", 30),
            auth_enabled=data.get("auth_enabled", False),
            username=data.get("username"),
            password=data.get("password"),
        )


@dataclass
class Config:
    """Main configuration for Node Health Monitor."""
    
    nodes: list[NodeConfig] = field(default_factory=list)
    thresholds: Thresholds = field(default_factory=Thresholds)
    notifiers: NotifierConfig = field(default_factory=NotifierConfig)
    dashboard: DashboardConfig = field(default_factory=DashboardConfig)
    check_interval: int = 60  # seconds
    parallel_checks: bool = True
    max_workers: int = 10
    log_level: str = "INFO"
    history_retention_days: int = 7
    
    @classmethod
    def from_yaml(cls, path: str | Path) -> "Config":
        """Load configuration from YAML file."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        
        with open(path) as f:
            data = yaml.safe_load(f)
        
        return cls.from_dict(data)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Config":
        """Create configuration from dictionary."""
        nodes = []
        for name, node_data in data.get("nodes", {}).items():
            nodes.append(NodeConfig.from_dict(name, node_data))
        
        return cls(
            nodes=nodes,
            thresholds=Thresholds.from_dict(data.get("thresholds", {})),
            notifiers=NotifierConfig.from_dict(data.get("notifiers", {})),
            dashboard=DashboardConfig.from_dict(data.get("dashboard", {})),
            check_interval=data.get("check_interval", 60),
            parallel_checks=data.get("parallel_checks", True),
            max_workers=data.get("max_workers", 10),
            log_level=data.get("log_level", "INFO"),
            history_retention_days=data.get("history_retention_days", 7),
        )
    
    def get_enabled_nodes(self) -> list[NodeConfig]:
        """Get list of enabled nodes."""
        return [n for n in self.nodes if n.enabled]
    
    def get_node(self, name: str) -> NodeConfig | None:
        """Get node by name."""
        for node in self.nodes:
            if node.name == name:
                return node
        return None
    
    def to_yaml(self, path: str | Path) -> None:
        """Save configuration to YAML file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        data = self._to_dict()
        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    
    def _to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        nodes_dict = {}
        for node in self.nodes:
            node_data: dict[str, Any] = {
                "platform": node.platform,
                "enabled": node.enabled,
            }
            if node.local:
                node_data["local"] = True
            if node.ssh:
                node_data["ssh"] = {
                    "username": node.ssh.username,
                    "host": node.ssh.host,
                    "port": node.ssh.port,
                }
                if node.ssh.key_file:
                    node_data["ssh"]["key_file"] = node.ssh.key_file
            if node.services:
                node_data["services"] = node.services
            if node.tags:
                node_data["tags"] = node.tags
            nodes_dict[node.name] = node_data
        
        return {
            "nodes": nodes_dict,
            "thresholds": {
                "memory_warning": self.thresholds.memory_warning,
                "memory_critical": self.thresholds.memory_critical,
                "disk_warning": self.thresholds.disk_warning,
                "disk_critical": self.thresholds.disk_critical,
                "load_warning": self.thresholds.load_warning,
                "load_critical": self.thresholds.load_critical,
            },
            "check_interval": self.check_interval,
            "parallel_checks": self.parallel_checks,
            "log_level": self.log_level,
        }


def create_example_config() -> Config:
    """Create an example configuration for documentation."""
    return Config(
        nodes=[
            NodeConfig(
                name="web-server-1",
                platform="linux",
                ssh=SSHConfig(username="admin", host="192.168.1.10"),
                services=["nginx", "docker"],
                tags=["production", "web"],
            ),
            NodeConfig(
                name="db-server-1",
                platform="linux",
                ssh=SSHConfig(username="admin", host="192.168.1.20"),
                services=["postgresql", "redis"],
                tags=["production", "database"],
            ),
            NodeConfig(
                name="mac-workstation",
                platform="darwin",
                ssh=SSHConfig(username="user", host="192.168.1.30"),
                services=["ollama"],
                tags=["development"],
            ),
            NodeConfig(
                name="windows-server",
                platform="windows",
                ssh=SSHConfig(username="administrator", host="192.168.1.40"),
                services=["docker"],
                tags=["staging"],
            ),
            NodeConfig(
                name="localhost",
                platform="linux",
                local=True,
                services=["docker"],
                tags=["monitoring"],
            ),
        ],
        thresholds=Thresholds(
            memory_warning=80.0,
            memory_critical=90.0,
            disk_warning=80.0,
            disk_critical=90.0,
            load_warning=4.0,
            load_critical=8.0,
        ),
    )
