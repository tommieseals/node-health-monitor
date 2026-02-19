"""Generic webhook notification handler."""

import logging

import httpx

from node_health_monitor.models import NodeHealth
from node_health_monitor.notifiers.base import BaseNotifier

logger = logging.getLogger(__name__)


class WebhookNotifier(BaseNotifier):
    """Send alerts via generic HTTP webhook."""
    
    def __init__(
        self,
        url: str,
        method: str = "POST",
        headers: dict | None = None,
        auth: tuple[str, str] | None = None,
    ) -> None:
        """Initialize webhook notifier.
        
        Args:
            url: Webhook URL.
            method: HTTP method (default POST).
            headers: Optional headers to include.
            auth: Optional (username, password) tuple for basic auth.
        """
        self.url = url
        self.method = method.upper()
        self.headers = headers or {}
        self.auth = auth
    
    def send_alert(self, node_name: str, message: str, health: NodeHealth) -> bool:
        """Send alert via webhook."""
        payload = {
            "event": "alert",
            "node": node_name,
            "message": message,
            "status": health.status.value,
            "health": health.to_dict(),
        }
        return self._send_request(payload)
    
    def send_recovery(self, node_name: str, message: str) -> bool:
        """Send recovery notification via webhook."""
        payload = {
            "event": "recovery",
            "node": node_name,
            "message": message,
        }
        return self._send_request(payload)
    
    def _send_request(self, payload: dict) -> bool:
        """Send HTTP request to webhook."""
        try:
            auth = httpx.BasicAuth(*self.auth) if self.auth else None
            
            response = httpx.request(
                method=self.method,
                url=self.url,
                json=payload,
                headers=self.headers,
                auth=auth,
                timeout=10,
            )
            
            if response.status_code in (200, 201, 202, 204):
                logger.info(f"Webhook notification sent to {self.url}")
                return True
            else:
                logger.error(f"Webhook error: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send webhook notification: {e}")
            return False
