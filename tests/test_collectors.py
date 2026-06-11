"""Tests for health collectors."""

from unittest import mock

import paramiko
import pytest

from node_health_monitor.collectors.local import LocalCollector
from node_health_monitor.collectors.ssh import SSHCollector
from node_health_monitor.config import NodeConfig, SSHConfig, Thresholds
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
                load_warning=999.0,
                load_critical=9999.0,
            ),
        )
        collector = LocalCollector(config)
        health = collector.collect()

        # With very high thresholds, should be healthy
        assert health.status == HealthStatus.HEALTHY


class TestSSHCollector:
    """Tests for the SSH collector, with paramiko mocked."""

    # Canned outputs for the Linux command set
    LINUX_OUTPUTS = {
        "free -b | grep Mem": "Mem: 17179869184 8589934592 1073741824 0 0 7516192768",
        "df -B1 / | tail -1": "/dev/sda1 107374182400 42949672960 64424509440 40% /",
        "cat /proc/loadavg": "1.25 0.75 0.50 2/345 6789",
        "nproc": "8",
        "top -bn1 | grep 'Cpu(s)' | awk '{print $2}'": "12.5",
        "pgrep -x nginx || pgrep -f nginx": "1234",
    }

    @pytest.fixture
    def node_config(self):
        return NodeConfig(
            name="web-server",
            platform="linux",
            ssh=SSHConfig(username="admin", host="192.168.1.10"),
            services=["nginx"],
            thresholds=Thresholds(),
        )

    def test_connection_failure_marks_node_unreachable(self, node_config):
        collector = SSHCollector(node_config)

        with mock.patch(
            "node_health_monitor.collectors.ssh.paramiko.SSHClient"
        ) as client_cls:
            client_cls.return_value.connect.side_effect = paramiko.SSHException(
                "Connection refused"
            )
            health = collector.collect()

        assert health.reachable is False
        assert health.status == HealthStatus.UNREACHABLE
        assert "Connection refused" in (health.error_message or "")
        assert health.host == "192.168.1.10"

    def test_collect_parses_linux_command_output(self, node_config):
        collector = SSHCollector(node_config)

        def fake_execute(command):
            return 0, self.LINUX_OUTPUTS[command], ""

        with (
            mock.patch.object(collector, "_get_client"),
            mock.patch.object(collector, "execute_command", side_effect=fake_execute),
        ):
            health = collector.collect()

        assert health.reachable is True
        assert health.cpu_count == 8
        assert health.cpu_percent == pytest.approx(12.5)
        assert health.load_average == (1.25, 0.75, 0.50)
        # free reported 16 GiB total / 8 GiB used
        assert health.memory_total_gb == pytest.approx(16.0)
        assert health.memory_used_gb == pytest.approx(8.0)
        assert health.memory_percent == pytest.approx(50.0)
        # df reported 100 GiB total / 40 GiB used
        assert health.disk_total_gb == pytest.approx(100.0)
        assert health.disk_percent == pytest.approx(40.0)
        # pgrep found nginx with pid 1234
        assert len(health.services) == 1
        assert health.services[0].running is True
        assert health.services[0].pid == 1234

    def test_check_service_not_running(self, node_config):
        collector = SSHCollector(node_config)

        with mock.patch.object(collector, "execute_command", return_value=(1, "", "")):
            running, pid = collector.check_service("nginx")

        assert running is False
        assert pid is None

    def test_execute_command_returns_error_tuple_on_failure(self, node_config):
        collector = SSHCollector(node_config)

        with mock.patch.object(
            collector, "_get_client", side_effect=OSError("socket closed")
        ):
            exit_code, stdout, stderr = collector.execute_command("uptime")

        assert exit_code == 1
        assert stdout == ""
        assert "socket closed" in stderr

    def test_connection_is_closed_after_collect(self, node_config):
        collector = SSHCollector(node_config)

        def fake_execute(command):
            return 0, self.LINUX_OUTPUTS[command], ""

        with (
            mock.patch.object(collector, "_get_client"),
            mock.patch.object(collector, "execute_command", side_effect=fake_execute),
            mock.patch.object(collector, "close") as close,
        ):
            collector.collect()

        close.assert_called_once()
