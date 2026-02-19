"""Slack notification handler."""

import logging

import httpx

from node_health_monitor.models import NodeHealth
from node_health_monitor.notifiers.base import BaseNotifier

logger = logging.getLogger(__name__)


class SlackNotifier(BaseNotifier):
    """Send alerts via Slack webhook."""
    
    def __init__(self, webhook_url: str, channel: str | None = None) -> None:
        """Initialize Slack notifier.
        
        Args:
            webhook_url: Slack incoming webhook URL.
            channel: Optional channel override.
        """
        self.webhook_url = webhook_url
        self.channel = channel
    
    def send_alert(self, node_name: str, message: str, health: NodeHealth) -> bool:
        """Send alert via Slack."""
        payload = self._build_alert_payload(node_name, message, health)
        return self._send_webhook(payload)
    
    def send_recovery(self, node_name: str, message: str) -> bool:
        """Send recovery notification via Slack."""
        payload = {
            "text": f"✅ *{node_name}* - {message}",
            "attachments": [
                {
                    "color": "good",
                    "text": "System has recovered to healthy state.",
                }
            ],
        }
        if self.channel:
            payload["channel"] = self.channel
        return self._send_webhook(payload)
    
    def _build_alert_payload(
        self, node_name: str, message: str, health: NodeHealth
    ) -> dict:
        """Build Slack message payload with blocks."""
        color_map = {
            "healthy": "good",
            "warning": "warning",
            "critical": "danger",
            "unreachable": "danger",
        }
        
        color = color_map.get(health.status.value, "#808080")
        
        fields = [
            {"title": "Memory", "value": f"{health.memory_percent:.1f}%", "short": True},
            {"title": "Disk", "value": f"{health.disk_percent:.1f}%", "short": True},
            {"title": "Load", "value": f"{health.load_average[0]:.2f}", "short": True},
            {"title": "Platform", "value": health.platform, "short": True},
        ]
        
        if health.services:
            services_text = ", ".join(
                f"{s.name} ({'✓' if s.running else '✗'})" for s in health.services
            )
            fields.append({"title": "Services", "value": services_text, "short": False})
        
        payload = {
            "text": f"🚨 Alert: {node_name}",
            "attachments": [
                {
                    "color": color,
                    "title": f"{node_name} - {health.status.value.upper()}",
                    "text": message,
                    "fields": fields,
                    "footer": "Node Health Monitor",
                    "ts": int(health.timestamp.timestamp()),
                }
            ],
        }
        
        if self.channel:
            payload["channel"] = self.channel
        
        return payload
    
    def _send_webhook(self, payload: dict) -> bool:
        """Send payload to Slack webhook."""
        try:
            response = httpx.post(
                self.webhook_url,
                json=payload,
                timeout=10,
            )
            
            if response.status_code == 200:
                logger.info("Slack notification sent")
                return True
            else:
                logger.error(f"Slack webhook error: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")
            return False
