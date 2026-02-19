"""Tests for health collectors."""

import pytest

from node_health_monitor.collectors.local import LocalCollector
from node_health_monitor.config import NodeConfig, Thresholds
from node_health_monitor.models import HealthStatus


class TestLocalCollector:
    """Tests for local system collector."""
    
    @pytest.fixture
    def local_config(self):
        return NodeConfig(
            name="localhost",
            platform="auto",
            local=True,
            services=[],
            thresholds=Thresholds(),
        )
    
    def test_collect_health(self, local_config):
        """Test collecting health from local system."""
        collector = LocalCollector(local_config)
        health = collector.collect()
        
        # Basic assertions
        assert health.name == "localhost"
        assert health.reachable is True
        
        # Verify metrics are populated
        assert health.memory_total_gb > 0
        assert 0 <= health.memory_percent <= 100
        assert health.disk_total_gb > 0
        assert 0 <= health.disk_percent <= 100
        assert health.cpu_count >= 1
        
        # Load average should be a tuple
        assert len(health.load_average) == 3
        assert all(isinstance(v, float) for v in health.load_average)
    
    def test_collect_with_services(self):
        """Test collecting health with service checks."""
        config = NodeConfig(
            name="localhost",
            platform="auto",
            local=True,
            # Use a process that should exist on any system
            services=["python"],
            thresholds=Thresholds(),
        )
        collector = LocalCollector(config)
        health = collector.collect()
        
        assert len(health.services) == 1
        # Python should be running (we're running this test!)
        assert health.services[0].name == "python"
        assert health.services[0].running is True
    
    def test_check_service_running(self, local_config):
        """Test checking a running service."""
        collector = LocalCollector(local_config)
        # Python is definitely running
        running, pid = collector.check_service("python")
        assert running is True
        assert pid is not None
        assert pid > 0
    
    def test_check_service_not_running(self, local_config):
        """Test checking a non-existent service."""
        collector = LocalCollector(local_config)
        running, pid = collector.check_service("definitely_not_a_real_process_12345")
        assert running is False
        assert pid is None
    
    def test_execute_command(self, local_config):
        """Test executing a local command."""
        collector = LocalCollector(local_config)
        exit_code, stdout, stderr = collector.execute_command("echo hello")
        assert exit_code == 0
        assert "hello" in stdout.strip()
    
    def test_health_status_calculation(self):
        """Test that health status is calculated correctly."""
        config = NodeConfig(
            name="test",
            platform="auto",
            local=True,
            thresholds=Thresholds(
                memory_warning=99.0,  # High thresholds
                memory_critical=99.9,
                disk_warning=99.0,
                disk_critical=99.9,
            ),
        )
        collector = LocalCollector(config)
        health = collector.collect()
        
        # With very high thresholds, should be healthy
        assert health.status == HealthStatus.HEALTHY
