"""Tests for data models."""

from datetime import datetime

import pytest

from node_health_monitor.models import (
    ClusterHealth,
    HealthStatus,
    NodeHealth,
    ServiceStatus,
)


class TestHealthStatus:
    """Tests for HealthStatus enum."""
    
    def test_status_values(self):
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.WARNING.value == "warning"
        assert HealthStatus.CRITICAL.value == "critical"
        assert HealthStatus.UNREACHABLE.value == "unreachable"


class TestServiceStatus:
    """Tests for ServiceStatus model."""
    
    def test_running_service(self):
        service = ServiceStatus(name="nginx", running=True, pid=1234)
        assert service.status == HealthStatus.HEALTHY
        assert service.name == "nginx"
        assert service.pid == 1234
    
    def test_stopped_service(self):
        service = ServiceStatus(name="nginx", running=False)
        assert service.status == HealthStatus.CRITICAL


class TestNodeHealth:
    """Tests for NodeHealth model."""
    
    @pytest.fixture
    def healthy_node(self):
        return NodeHealth(
            name="test-node",
            host="192.168.1.10",
            platform="linux",
            reachable=True,
            memory_percent=50.0,
            disk_percent=40.0,
            load_average=(1.0, 1.5, 2.0),
            cpu_count=4,
            thresholds={
                "memory": (80.0, 90.0),
                "disk": (80.0, 90.0),
                "load": (4.0, 8.0),
            },
        )
    
    @pytest.fixture
    def warning_node(self):
        return NodeHealth(
            name="warning-node",
            host="192.168.1.11",
            platform="linux",
            reachable=True,
            memory_percent=85.0,  # Warning level
            disk_percent=40.0,
            load_average=(1.0, 1.5, 2.0),
            cpu_count=4,
            thresholds={
                "memory": (80.0, 90.0),
                "disk": (80.0, 90.0),
                "load": (4.0, 8.0),
            },
        )
    
    @pytest.fixture
    def critical_node(self):
        return NodeHealth(
            name="critical-node",
            host="192.168.1.12",
            platform="linux",
            reachable=True,
            memory_percent=95.0,  # Critical level
            disk_percent=92.0,  # Critical level
            load_average=(10.0, 8.0, 6.0),  # Critical load
            cpu_count=4,
            thresholds={
                "memory": (80.0, 90.0),
                "disk": (80.0, 90.0),
                "load": (4.0, 8.0),
            },
        )
    
    def test_healthy_status(self, healthy_node):
        assert healthy_node.status == HealthStatus.HEALTHY
        assert healthy_node.memory_status == HealthStatus.HEALTHY
        assert healthy_node.disk_status == HealthStatus.HEALTHY
        assert healthy_node.load_status == HealthStatus.HEALTHY
    
    def test_warning_status(self, warning_node):
        assert warning_node.status == HealthStatus.WARNING
        assert warning_node.memory_status == HealthStatus.WARNING
    
    def test_critical_status(self, critical_node):
        assert critical_node.status == HealthStatus.CRITICAL
        assert critical_node.memory_status == HealthStatus.CRITICAL
        assert critical_node.disk_status == HealthStatus.CRITICAL
    
    def test_unreachable_node(self):
        node = NodeHealth(
            name="unreachable",
            host="192.168.1.99",
            platform="linux",
            reachable=False,
            error_message="Connection timeout",
        )
        assert node.status == HealthStatus.UNREACHABLE
    
    def test_get_alerts_healthy(self, healthy_node):
        alerts = healthy_node.get_alerts()
        assert len(alerts) == 0
    
    def test_get_alerts_critical(self, critical_node):
        alerts = critical_node.get_alerts()
        assert len(alerts) == 3  # Memory, Disk, Load
        assert any("Memory" in a for a in alerts)
        assert any("Disk" in a for a in alerts)
        assert any("Load" in a for a in alerts)
    
    def test_service_alerts(self):
        node = NodeHealth(
            name="service-test",
            host="localhost",
            platform="linux",
            reachable=True,
            memory_percent=50.0,
            disk_percent=40.0,
            load_average=(1.0, 1.5, 2.0),
            cpu_count=4,
            services=[
                ServiceStatus(name="nginx", running=True),
                ServiceStatus(name="mysql", running=False),
            ],
            thresholds={
                "memory": (80.0, 90.0),
                "disk": (80.0, 90.0),
                "load": (4.0, 8.0),
            },
        )
        alerts = node.get_alerts()
        assert len(alerts) == 1
        assert "mysql" in alerts[0]
    
    def test_to_dict(self, healthy_node):
        data = healthy_node.to_dict()
        assert data["name"] == "test-node"
        assert data["host"] == "192.168.1.10"
        assert data["status"] == "healthy"
        assert "metrics" in data
        assert "memory" in data["metrics"]


class TestClusterHealth:
    """Tests for ClusterHealth model."""
    
    def test_empty_cluster(self):
        cluster = ClusterHealth(nodes=[])
        assert cluster.status == HealthStatus.UNKNOWN
        assert cluster.healthy_count == 0
    
    def test_all_healthy(self):
        nodes = [
            NodeHealth(
                name=f"node-{i}",
                host=f"192.168.1.{i}",
                platform="linux",
                reachable=True,
                memory_percent=50.0,
                disk_percent=40.0,
                load_average=(1.0, 1.0, 1.0),
                cpu_count=4,
                thresholds={"memory": (80, 90), "disk": (80, 90), "load": (4, 8)},
            )
            for i in range(3)
        ]
        cluster = ClusterHealth(nodes=nodes)
        assert cluster.status == HealthStatus.HEALTHY
        assert cluster.healthy_count == 3
        assert cluster.warning_count == 0
        assert cluster.critical_count == 0
    
    def test_mixed_status(self):
        healthy = NodeHealth(
            name="healthy",
            host="1.1.1.1",
            platform="linux",
            reachable=True,
            memory_percent=50.0,
            disk_percent=40.0,
            load_average=(1.0, 1.0, 1.0),
            cpu_count=4,
            thresholds={"memory": (80, 90), "disk": (80, 90), "load": (4, 8)},
        )
        critical = NodeHealth(
            name="critical",
            host="1.1.1.2",
            platform="linux",
            reachable=True,
            memory_percent=95.0,
            disk_percent=40.0,
            load_average=(1.0, 1.0, 1.0),
            cpu_count=4,
            thresholds={"memory": (80, 90), "disk": (80, 90), "load": (4, 8)},
        )
        cluster = ClusterHealth(nodes=[healthy, critical])
        assert cluster.status == HealthStatus.CRITICAL
        assert cluster.healthy_count == 1
        assert cluster.critical_count == 1
    
    def test_get_all_alerts(self):
        node1 = NodeHealth(
            name="node1",
            host="1.1.1.1",
            platform="linux",
            reachable=True,
            memory_percent=95.0,
            disk_percent=40.0,
            load_average=(1.0, 1.0, 1.0),
            cpu_count=4,
            thresholds={"memory": (80, 90), "disk": (80, 90), "load": (4, 8)},
        )
        node2 = NodeHealth(
            name="node2",
            host="1.1.1.2",
            platform="linux",
            reachable=False,
            error_message="Connection refused",
        )
        cluster = ClusterHealth(nodes=[node1, node2])
        alerts = cluster.get_all_alerts()
        assert len(alerts) == 2
        assert ("node1", "CRITICAL: Memory at 95.0%") in alerts
    
    def test_to_dict(self):
        node = NodeHealth(
            name="test",
            host="localhost",
            platform="linux",
            reachable=True,
            memory_percent=50.0,
            disk_percent=40.0,
            load_average=(1.0, 1.0, 1.0),
            cpu_count=4,
            thresholds={"memory": (80, 90), "disk": (80, 90), "load": (4, 8)},
        )
        cluster = ClusterHealth(nodes=[node])
        data = cluster.to_dict()
        assert "timestamp" in data
        assert "status" in data
        assert "summary" in data
        assert "nodes" in data
        assert len(data["nodes"]) == 1
