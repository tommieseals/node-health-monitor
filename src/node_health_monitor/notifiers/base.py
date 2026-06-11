"""Base notifier interface."""

from abc import ABC, abstractmethod

from node_health_monitor.models import NodeHealth


class BaseNotifier(ABC):
    """Abstract base class for alert notifiers."""

    @abstractmethod
    def send_alert(self, node_name: str, message: str, health: NodeHealth) -> bool:
        """Send an alert notification.

        Args:
            node_name: Name of the affected node.
            message: Alert message.
            health: Full health data for context.

        Returns:
            True if notification was sent successfully.
        """
        ...

    @abstractmethod
    def send_recovery(self, node_name: str, message: str) -> bool:
        """Send a recovery notification.

        Args:
            node_name: Name of the recovered node.
            message: Recovery message.

        Returns:
            True if notification was sent successfully.
        """
        ...

    def format_alert(self, node_name: str, message: str, health: NodeHealth) -> str:
        """Format an alert message with context.

        Override this method to customize message formatting.
        """
        status_emoji = {
            "healthy": "✅",
            "warning": "⚠️",
            "critical": "🔴",
            "unreachable": "❌",
        }

        emoji = status_emoji.get(health.status.value, "❓")

        lines = [
            f"{emoji} **{node_name}** - {message}",
            "",
            "📊 **Metrics:**",
            f"  • Memory: {health.memory_percent:.1f}%",
            f"  • Disk: {health.disk_percent:.1f}%",
            f"  • Load: {health.load_average[0]:.2f}",
        ]

        if health.services:
            lines.append("")
            lines.append("🔧 **Services:**")
            for svc in health.services:
                icon = "✅" if svc.running else "❌"
                lines.append(f"  • {svc.name}: {icon}")

        return "\n".join(lines)
