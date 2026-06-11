"""Tests for alert notifiers, with HTTP transport mocked."""

from unittest import mock

import pytest

from node_health_monitor.config import NotifierConfig
from node_health_monitor.models import NodeHealth, ServiceStatus
from node_health_monitor.notifiers import (
    SlackNotifier,
    TelegramNotifier,
    WebhookNotifier,
    build_notifiers,
)


def make_health(**overrides):
    defaults = {
        "name": "web-server",
        "host": "192.168.1.10",
        "platform": "linux",
        "reachable": True,
        "memory_percent": 95.0,
        "disk_percent": 40.0,
        "load_average": (1.0, 1.0, 1.0),
        "cpu_count": 4,
        "services": [ServiceStatus(name="nginx", running=True, pid=100)],
        "thresholds": {"memory": (80.0, 90.0), "disk": (80.0, 90.0), "load": (4.0, 8.0)},
    }
    defaults.update(overrides)
    return NodeHealth(**defaults)


def make_response(status_code=200, text="ok"):
    response = mock.Mock()
    response.status_code = status_code
    response.text = text
    return response


@pytest.fixture
def health():
    return make_health()


class TestTelegramNotifier:
    def test_send_alert_success(self, health):
        notifier = TelegramNotifier(bot_token="token123", chat_id=42)

        with mock.patch(
            "node_health_monitor.notifiers.telegram.httpx.post",
            return_value=make_response(200),
        ) as post:
            assert notifier.send_alert("web-server", "CRITICAL: Memory at 95.0%", health)

        post.assert_called_once()
        url = post.call_args.args[0]
        payload = post.call_args.kwargs["json"]
        assert url == "https://api.telegram.org/bottoken123/sendMessage"
        assert payload["chat_id"] == "42"
        assert "web-server" in payload["text"]
        assert "95.0" in payload["text"]

    def test_send_alert_api_error_returns_false(self, health):
        notifier = TelegramNotifier(bot_token="token123", chat_id=42)

        with mock.patch(
            "node_health_monitor.notifiers.telegram.httpx.post",
            return_value=make_response(403, "forbidden"),
        ):
            assert notifier.send_alert("web-server", "msg", health) is False

    def test_send_alert_network_error_returns_false(self, health):
        notifier = TelegramNotifier(bot_token="token123", chat_id=42)

        with mock.patch(
            "node_health_monitor.notifiers.telegram.httpx.post",
            side_effect=ConnectionError("unreachable"),
        ):
            assert notifier.send_alert("web-server", "msg", health) is False

    def test_send_recovery(self):
        notifier = TelegramNotifier(bot_token="token123", chat_id=42)

        with mock.patch(
            "node_health_monitor.notifiers.telegram.httpx.post",
            return_value=make_response(200),
        ) as post:
            assert notifier.send_recovery("web-server", "recovered") is True

        payload = post.call_args.kwargs["json"]
        assert "web-server" in payload["text"]
        assert "recovered" in payload["text"]


class TestSlackNotifier:
    def test_send_alert_success(self, health):
        notifier = SlackNotifier(webhook_url="https://hooks.example/T0/B0/x", channel="#alerts")

        with mock.patch(
            "node_health_monitor.notifiers.slack.httpx.post",
            return_value=make_response(200),
        ) as post:
            assert notifier.send_alert("web-server", "CRITICAL: Memory at 95.0%", health)

        post.assert_called_once()
        assert post.call_args.args[0] == "https://hooks.example/T0/B0/x"
        payload = post.call_args.kwargs["json"]
        assert payload["channel"] == "#alerts"
        attachment = payload["attachments"][0]
        assert attachment["color"] == "danger"
        assert attachment["text"] == "CRITICAL: Memory at 95.0%"
        field_titles = {f["title"] for f in attachment["fields"]}
        assert {"Memory", "Disk", "Load", "Platform", "Services"} <= field_titles

    def test_send_alert_error_returns_false(self, health):
        notifier = SlackNotifier(webhook_url="https://hooks.example/T0/B0/x")

        with mock.patch(
            "node_health_monitor.notifiers.slack.httpx.post",
            return_value=make_response(500),
        ):
            assert notifier.send_alert("web-server", "msg", health) is False

    def test_send_recovery(self):
        notifier = SlackNotifier(webhook_url="https://hooks.example/T0/B0/x")

        with mock.patch(
            "node_health_monitor.notifiers.slack.httpx.post",
            return_value=make_response(200),
        ) as post:
            assert notifier.send_recovery("web-server", "recovered") is True

        payload = post.call_args.kwargs["json"]
        assert "web-server" in payload["text"]
        assert payload["attachments"][0]["color"] == "good"


class TestWebhookNotifier:
    def test_send_alert_success(self, health):
        notifier = WebhookNotifier(
            url="https://example.com/hook",
            headers={"Authorization": "Bearer abc"},
        )

        with mock.patch(
            "node_health_monitor.notifiers.webhook.httpx.request",
            return_value=make_response(204),
        ) as request:
            assert notifier.send_alert("web-server", "CRITICAL: Memory at 95.0%", health)

        request.assert_called_once()
        kwargs = request.call_args.kwargs
        assert kwargs["method"] == "POST"
        assert kwargs["url"] == "https://example.com/hook"
        assert kwargs["headers"] == {"Authorization": "Bearer abc"}
        payload = kwargs["json"]
        assert payload["event"] == "alert"
        assert payload["node"] == "web-server"
        assert payload["status"] == "critical"
        assert payload["health"]["metrics"]["memory"]["percent"] == 95.0

    def test_send_alert_error_returns_false(self, health):
        notifier = WebhookNotifier(url="https://example.com/hook")

        with mock.patch(
            "node_health_monitor.notifiers.webhook.httpx.request",
            return_value=make_response(500),
        ):
            assert notifier.send_alert("web-server", "msg", health) is False

    def test_send_recovery(self):
        notifier = WebhookNotifier(url="https://example.com/hook", method="put")

        with mock.patch(
            "node_health_monitor.notifiers.webhook.httpx.request",
            return_value=make_response(200),
        ) as request:
            assert notifier.send_recovery("web-server", "recovered") is True

        kwargs = request.call_args.kwargs
        assert kwargs["method"] == "PUT"
        assert kwargs["json"]["event"] == "recovery"


class TestBuildNotifiers:
    def test_empty_config_builds_nothing(self):
        assert build_notifiers(NotifierConfig()) == []

    def test_builds_all_configured_notifiers(self):
        config = NotifierConfig(
            telegram={"enabled": True, "bot_token": "t", "chat_id": "1"},
            slack={"enabled": True, "webhook_url": "https://hooks.example/x"},
            webhook={
                "enabled": True,
                "url": "https://example.com/hook",
                "method": "PUT",
                "auth": ["user", "pass"],
            },
        )
        notifiers = build_notifiers(config)
        assert len(notifiers) == 3
        assert isinstance(notifiers[0], TelegramNotifier)
        assert isinstance(notifiers[1], SlackNotifier)
        assert isinstance(notifiers[2], WebhookNotifier)
        assert notifiers[2].method == "PUT"
        assert notifiers[2].auth == ("user", "pass")

    def test_present_section_is_enabled_by_default(self):
        config = NotifierConfig(slack={"webhook_url": "https://hooks.example/x"})
        notifiers = build_notifiers(config)
        assert len(notifiers) == 1

    def test_disabled_section_is_skipped(self):
        config = NotifierConfig(
            telegram={"enabled": False, "bot_token": "t", "chat_id": "1"},
        )
        assert build_notifiers(config) == []

    def test_section_with_missing_keys_is_skipped_without_raising(self):
        config = NotifierConfig(
            telegram={"enabled": True},  # Missing bot_token/chat_id
            slack={"enabled": True, "webhook_url": "https://hooks.example/x"},
        )
        notifiers = build_notifiers(config)
        assert len(notifiers) == 1
        assert isinstance(notifiers[0], SlackNotifier)
