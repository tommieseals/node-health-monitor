"""Telegram notification handler."""

import logging

import httpx

from node_health_monitor.models import NodeHealth
from node_health_monitor.notifiers.base import BaseNotifier

logger = logging.getLogger(__name__)


class TelegramNotifier(BaseNotifier):
    """Send alerts via Telegram bot."""
    
    def __init__(self, bot_token: str, chat_id: str | int) -> None:
        """Initialize Telegram notifier.
        
        Args:
            bot_token: Telegram bot API token.
            chat_id: Chat ID to send messages to.
        """
        self.bot_token = bot_token
        self.chat_id = str(chat_id)
        self.api_base = f"https://api.telegram.org/bot{bot_token}"
    
    def send_alert(self, node_name: str, message: str, health: NodeHealth) -> bool:
        """Send alert via Telegram."""
        text = self.format_alert(node_name, message, health)
        return self._send_message(text)
    
    def send_recovery(self, node_name: str, message: str) -> bool:
        """Send recovery notification via Telegram."""
        text = f"✅ **{node_name}** - {message}"
        return self._send_message(text)
    
    def _send_message(self, text: str) -> bool:
        """Send a message via Telegram API."""
        try:
            response = httpx.post(
                f"{self.api_base}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": "Markdown",
                },
                timeout=10,
            )
            
            if response.status_code == 200:
                logger.info(f"Telegram notification sent to {self.chat_id}")
                return True
            else:
                logger.error(f"Telegram API error: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")
            return False
    
    def format_alert(self, node_name: str, message: str, health: NodeHealth) -> str:
        """Format alert for Telegram (Markdown)."""
        status_emoji = {
            "healthy": "✅",
            "warning": "⚠️",
            "critical": "🔴",
            "unreachable": "❌",
        }
        
        emoji = status_emoji.get(health.status.value, "❓")
        
        lines = [
            f"{emoji} *{node_name}*",
            f"_{message}_",
            "",
            "📊 *Metrics:*",
            f"  • Memory: `{health.memory_percent:.1f}%`",
            f"  • Disk: `{health.disk_percent:.1f}%`",
            f"  • Load: `{health.load_average[0]:.2f}`",
        ]
        
        if health.services:
            lines.append("")
            lines.append("🔧 *Services:*")
            for svc in health.services:
                icon = "✅" if svc.running else "❌"
                lines.append(f"  • {svc.name}: {icon}")
        
        return "\n".join(lines)
