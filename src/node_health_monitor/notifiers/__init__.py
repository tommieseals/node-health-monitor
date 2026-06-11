"""Alert notification handlers."""

import logging

from node_health_monitor.config import NotifierConfig
from node_health_monitor.notifiers.base import BaseNotifier
from node_health_monitor.notifiers.slack import SlackNotifier
from node_health_monitor.notifiers.telegram import TelegramNotifier
from node_health_monitor.notifiers.webhook import WebhookNotifier

logger = logging.getLogger(__name__)


def build_notifiers(config: NotifierConfig) -> list[BaseNotifier]:
    """Build notifier instances from configuration.

    A notifier section is used whenever it is present in the config, unless it
    sets ``enabled: false``. Sections missing required keys are skipped with an
    error logged, so one bad notifier does not prevent the others from working.

    Args:
        config: Parsed ``notifiers:`` section of the configuration.

    Returns:
        List of configured notifier instances (possibly empty).
    """
    notifiers: list[BaseNotifier] = []

    if config.telegram and config.telegram.get("enabled", True):
        try:
            notifiers.append(
                TelegramNotifier(
                    bot_token=config.telegram["bot_token"],
                    chat_id=config.telegram["chat_id"],
                )
            )
        except KeyError as e:
            logger.error(f"Telegram notifier config is missing required key: {e}")

    if config.slack and config.slack.get("enabled", True):
        try:
            notifiers.append(
                SlackNotifier(
                    webhook_url=config.slack["webhook_url"],
                    channel=config.slack.get("channel"),
                )
            )
        except KeyError as e:
            logger.error(f"Slack notifier config is missing required key: {e}")

    if config.webhook and config.webhook.get("enabled", True):
        try:
            auth = config.webhook.get("auth")
            notifiers.append(
                WebhookNotifier(
                    url=config.webhook["url"],
                    method=config.webhook.get("method", "POST"),
                    headers=config.webhook.get("headers"),
                    auth=tuple(auth) if auth else None,
                )
            )
        except KeyError as e:
            logger.error(f"Webhook notifier config is missing required key: {e}")

    return notifiers


__all__ = [
    "BaseNotifier",
    "SlackNotifier",
    "TelegramNotifier",
    "WebhookNotifier",
    "build_notifiers",
]
