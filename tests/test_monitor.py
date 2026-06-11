"""Tests for the monitoring flow: alert dispatch and remediation triggering."""

from unittest import mock

import pytest

from node_health_monitor.config import (
    Config,
    NodeConfig,
    NotifierConfig,
    RemediationConfig,
    Thresholds,
)
from node_health_monitor.models import NodeHealth
from node_health_monitor.monitor import HealthMonitor
from node_health_monitor.notifiers import (
    BaseNotifier,
    SlackNotifier,
    TelegramNotifier,
    WebhookNotifier,
)

THRESHOLDS = {"memory": (80.0, 90.0), "disk": (80.0, 90.0), "load": (4.0, 8.0)}


def make_health(name="local-node", memory_percent=50.0, **overrides):
    defaults = {
        "name": name,
        "host": "localhost",
        "platform": "linux",
        "reachable": True,
        "memory_percent": memory_percent,
        "disk_percent": 40.0,
        "load_average": (1.0, 1.0, 1.0),
        "cpu_count": 4,
        "thresholds": THRESHOLDS,
    }
    defaults.update(overrides)
    return NodeHealth(**defaults)


def make_local_node(name="local-node", remediation=None):
    return NodeConfig(
        name=name,
        platform="linux",
        local=True,
        thresholds=Thresholds(),
        remediation=remediation,
    )


@pytest.fixture
def mock_notifier():
    return mock.Mock(spec=BaseNotifier)


class TestNotifierWiring:
    """The monitor must build notifiers from config and dispatch alerts."""

    def test_notifiers_built_from_config(self):
        config = Config(
            notifiers=NotifierConfig(
                telegram={"enabled": True, "bot_token": "t", "chat_id": "1"},
                slack={"enabled": True, "webhook_url": "https://hooks.example/x"},
                webhook={"enabled": True, "url": "https://example.com/hook"},
            )
        )
        monitor = HealthMonitor(config)
        types = {type(n) for n in monitor.notifiers}
        assert types == {TelegramNotifier, SlackNotifier, WebhookNotifier}

    def test_no_notifiers_by_default(self):
        monitor = HealthMonitor(Config())
        assert monitor.notifiers == []

    def test_alert_dispatched_to_notifier_on_check(self, mock_notifier):
        """Critical health during check_node -> notifier.send_alert called."""
        config = Config(nodes=[make_local_node()])
        monitor = HealthMonitor(config, notifiers=[mock_notifier])
        critical = make_health(memory_percent=95.0)

        with mock.patch("node_health_monitor.monitor.LocalCollector") as collector_cls:
            collector_cls.return_value.collect.return_value = critical
            result = monitor.check_node(config.nodes[0])

        assert result is critical
        mock_notifier.send_alert.assert_called_once_with(
            "local-node", "CRITICAL: Memory at 95.0%", critical
        )

    def test_healthy_node_sends_nothing(self, mock_notifier):
        config = Config(nodes=[make_local_node()])
        monitor = HealthMonitor(config, notifiers=[mock_notifier])

        with mock.patch("node_health_monitor.monitor.LocalCollector") as collector_cls:
            collector_cls.return_value.collect.return_value = make_health()
            monitor.check_node(config.nodes[0])

        mock_notifier.send_alert.assert_not_called()
        mock_notifier.send_recovery.assert_not_called()

    def test_cooldown_suppresses_repeat_alerts(self, mock_notifier):
        monitor = HealthMonitor(Config(), notifiers=[mock_notifier])
        critical = make_health(memory_percent=95.0)

        monitor._process_alerts(critical)
        monitor._process_alerts(critical)  # Within the 5-minute cooldown

        assert mock_notifier.send_alert.call_count == 1

    def test_on_alert_callback_invoked_alongside_notifiers(self, mock_notifier):
        callback = mock.Mock()
        monitor = HealthMonitor(Config(), on_alert=callback, notifiers=[mock_notifier])
        critical = make_health(memory_percent=95.0)

        monitor._process_alerts(critical)

        callback.assert_called_once_with("local-node", "CRITICAL: Memory at 95.0%", critical)
        mock_notifier.send_alert.assert_called_once()

    def test_recovery_sent_when_node_returns_to_healthy(self, mock_notifier):
        monitor = HealthMonitor(Config(), notifiers=[mock_notifier])

        monitor._process_alerts(make_health(memory_percent=95.0))
        monitor._process_alerts(make_health(memory_percent=50.0))

        mock_notifier.send_recovery.assert_called_once()
        assert mock_notifier.send_recovery.call_args.args[0] == "local-node"

    def test_no_recovery_without_prior_unhealthy_state(self, mock_notifier):
        monitor = HealthMonitor(Config(), notifiers=[mock_notifier])

        monitor._process_alerts(make_health())
        monitor._process_alerts(make_health())

        mock_notifier.send_recovery.assert_not_called()

    def test_notifier_exception_does_not_break_check(self, mock_notifier):
        mock_notifier.send_alert.side_effect = RuntimeError("network down")
        config = Config(nodes=[make_local_node()])
        monitor = HealthMonitor(config, notifiers=[mock_notifier])

        with mock.patch("node_health_monitor.monitor.LocalCollector") as collector_cls:
            collector_cls.return_value.collect.return_value = make_health(memory_percent=95.0)
            health = monitor.check_node(config.nodes[0])

        assert health.name == "local-node"
        mock_notifier.send_alert.assert_called_once()


class TestRemediationWiring:
    """The monitor must invoke the RemediationHandler when configured."""

    def test_remediation_invoked_when_configured(self):
        remediation = RemediationConfig(enabled=True, on_high_memory="cleanup-memory.sh")
        node = make_local_node(remediation=remediation)
        config = Config(nodes=[node])
        monitor = HealthMonitor(config)
        critical = make_health(memory_percent=95.0)

        with (
            mock.patch("node_health_monitor.monitor.LocalCollector") as collector_cls,
            mock.patch("node_health_monitor.monitor.RemediationHandler") as handler_cls,
        ):
            collector_cls.return_value.collect.return_value = critical
            handler_cls.return_value.handle.return_value = [("high_memory", True, "ok")]
            monitor.check_node(node)

        handler_cls.assert_called_once_with(remediation, node)
        handler_cls.return_value.handle.assert_called_once_with(critical)

    def test_remediation_skipped_when_disabled(self):
        remediation = RemediationConfig(enabled=False, on_high_memory="cleanup-memory.sh")
        node = make_local_node(remediation=remediation)
        config = Config(nodes=[node])
        monitor = HealthMonitor(config)

        with (
            mock.patch("node_health_monitor.monitor.LocalCollector") as collector_cls,
            mock.patch("node_health_monitor.monitor.RemediationHandler") as handler_cls,
        ):
            collector_cls.return_value.collect.return_value = make_health(memory_percent=95.0)
            monitor.check_node(node)

        handler_cls.assert_not_called()

    def test_remediation_skipped_when_not_configured(self):
        node = make_local_node()
        config = Config(nodes=[node])
        monitor = HealthMonitor(config)

        with (
            mock.patch("node_health_monitor.monitor.LocalCollector") as collector_cls,
            mock.patch("node_health_monitor.monitor.RemediationHandler") as handler_cls,
        ):
            collector_cls.return_value.collect.return_value = make_health()
            monitor.check_node(node)

        handler_cls.assert_not_called()

    def test_remediation_error_does_not_break_check(self):
        remediation = RemediationConfig(enabled=True, on_high_memory="cleanup-memory.sh")
        node = make_local_node(remediation=remediation)
        config = Config(nodes=[node])
        monitor = HealthMonitor(config)
        critical = make_health(memory_percent=95.0)

        with (
            mock.patch("node_health_monitor.monitor.LocalCollector") as collector_cls,
            mock.patch("node_health_monitor.monitor.RemediationHandler") as handler_cls,
        ):
            collector_cls.return_value.collect.return_value = critical
            handler_cls.return_value.handle.side_effect = RuntimeError("boom")
            health = monitor.check_node(node)

        assert health is critical
