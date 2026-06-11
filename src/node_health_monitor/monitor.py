"""Core health monitoring logic."""

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from node_health_monitor.collectors import LocalCollector, SSHCollector
from node_health_monitor.config import Config, NodeConfig
from node_health_monitor.models import ClusterHealth, HealthStatus, NodeHealth
from node_health_monitor.notifiers import BaseNotifier, build_notifiers
from node_health_monitor.remediation import RemediationHandler

logger = logging.getLogger(__name__)


class HealthMonitor:
    """Main health monitoring orchestrator."""

    def __init__(
        self,
        config: Config,
        on_alert: Callable[[str, str, NodeHealth], None] | None = None,
        notifiers: list[BaseNotifier] | None = None,
    ) -> None:
        """Initialize health monitor.

        Args:
            config: Configuration object.
            on_alert: Optional callback for alerts (node_name, message, health).
            notifiers: Optional explicit notifier list. By default, notifiers
                are built from the ``notifiers:`` section of the config.
        """
        self.config = config
        self.on_alert = on_alert
        self.notifiers: list[BaseNotifier] = (
            notifiers if notifiers is not None else build_notifiers(config.notifiers)
        )
        self._last_health: ClusterHealth | None = None
        self._alert_cooldown: dict[str, datetime] = {}  # Prevent alert spam
        self._node_status: dict[str, HealthStatus] = {}  # For recovery detection

    def check_node(self, node_config: NodeConfig) -> NodeHealth:
        """Check health of a single node.

        Args:
            node_config: Node configuration.

        Returns:
            NodeHealth object with collected metrics.
        """
        logger.info(f"Checking health of node: {node_config.name}")

        # Get appropriate collector
        if node_config.local:
            collector = LocalCollector(node_config)
        elif node_config.ssh:
            collector = SSHCollector(node_config)
        else:
            logger.error(f"No collector available for node: {node_config.name}")
            return NodeHealth(
                name=node_config.name,
                host="unknown",
                platform=node_config.platform,
                reachable=False,
                error_message="No collector configured (set local=True or provide SSH config)",
            )

        # Apply global thresholds if node doesn't have custom ones
        if node_config.thresholds is None:
            node_config.thresholds = self.config.thresholds

        health = collector.collect()

        # Dispatch alert/recovery notifications
        self._process_alerts(health)

        # Run auto-remediation if configured for this node
        self._run_remediation(node_config, health)

        return health

    def check_all(self) -> ClusterHealth:
        """Check health of all configured nodes.

        Returns:
            ClusterHealth object with all node health data.
        """
        enabled_nodes = self.config.get_enabled_nodes()

        if not enabled_nodes:
            logger.warning("No enabled nodes configured")
            return ClusterHealth(nodes=[], timestamp=datetime.now())

        results: list[NodeHealth] = []

        if self.config.parallel_checks and len(enabled_nodes) > 1:
            # Parallel execution
            with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
                futures = {
                    executor.submit(self.check_node, node): node.name
                    for node in enabled_nodes
                }

                for future in as_completed(futures):
                    node_name = futures[future]
                    try:
                        health = future.result(timeout=60)
                        results.append(health)
                    except Exception as e:
                        logger.error(f"Failed to check node {node_name}: {e}")
                        results.append(NodeHealth(
                            name=node_name,
                            host="unknown",
                            platform="unknown",
                            reachable=False,
                            error_message=str(e),
                        ))
        else:
            # Sequential execution
            for node in enabled_nodes:
                try:
                    health = self.check_node(node)
                    results.append(health)
                except Exception as e:
                    logger.error(f"Failed to check node {node.name}: {e}")
                    results.append(NodeHealth(
                        name=node.name,
                        host=node.ssh.host if node.ssh else "unknown",
                        platform=node.platform,
                        reachable=False,
                        error_message=str(e),
                    ))

        cluster_health = ClusterHealth(nodes=results, timestamp=datetime.now())
        self._last_health = cluster_health

        return cluster_health

    def _process_alerts(self, health: NodeHealth) -> None:
        """Dispatch alert and recovery notifications for a node health check."""
        previous_status = self._node_status.get(health.name)
        self._node_status[health.name] = health.status

        if self.on_alert is None and not self.notifiers:
            return

        for alert_msg in health.get_alerts():
            # Check cooldown (don't spam same alert within 5 minutes)
            cooldown_key = f"{health.name}:{alert_msg}"
            now = datetime.now()

            if cooldown_key in self._alert_cooldown:
                last_alert = self._alert_cooldown[cooldown_key]
                if (now - last_alert).total_seconds() < 300:
                    continue

            self._alert_cooldown[cooldown_key] = now
            self._dispatch_alert(health.name, alert_msg, health)

        # Send a recovery notification when a node returns to healthy
        unhealthy = (HealthStatus.WARNING, HealthStatus.CRITICAL, HealthStatus.UNREACHABLE)
        if previous_status in unhealthy and health.status == HealthStatus.HEALTHY:
            message = f"{health.name} has recovered (status: healthy)"
            for notifier in self.notifiers:
                try:
                    notifier.send_recovery(health.name, message)
                except Exception as e:
                    logger.error(
                        f"Recovery notification failed ({type(notifier).__name__}): {e}"
                    )

    def _dispatch_alert(self, node_name: str, message: str, health: NodeHealth) -> None:
        """Send a single alert to the callback and all configured notifiers."""
        if self.on_alert is not None:
            try:
                self.on_alert(node_name, message, health)
            except Exception as e:
                logger.error(f"Alert callback failed: {e}")

        for notifier in self.notifiers:
            try:
                notifier.send_alert(node_name, message, health)
            except Exception as e:
                logger.error(f"Alert notification failed ({type(notifier).__name__}): {e}")

    def _run_remediation(self, node_config: NodeConfig, health: NodeHealth) -> None:
        """Run the node's remediation hooks if configured and enabled.

        Remediation scripts execute on the monitoring host (the machine
        running node-health-monitor); see RemediationHandler.
        """
        remediation = node_config.remediation
        if remediation is None or not remediation.enabled:
            return

        handler = RemediationHandler(remediation, node_config)
        try:
            results = handler.handle(health)
        except Exception as e:
            logger.error(f"Remediation failed for {node_config.name}: {e}")
            return

        for action, success, message in results:
            if success:
                logger.info(f"Remediation '{action}' on {node_config.name} succeeded: {message}")
            else:
                logger.error(f"Remediation '{action}' on {node_config.name} failed: {message}")

    def get_last_health(self) -> ClusterHealth | None:
        """Get the last collected cluster health."""
        return self._last_health

    def get_summary(self) -> dict:
        """Get a summary of the current cluster health."""
        if not self._last_health:
            return {
                "status": "unknown",
                "message": "No health check has been performed yet",
            }

        health = self._last_health
        return {
            "status": health.status.value,
            "timestamp": health.timestamp.isoformat(),
            "nodes": {
                "total": len(health.nodes),
                "healthy": health.healthy_count,
                "warning": health.warning_count,
                "critical": health.critical_count,
            },
            "alerts": len(health.get_all_alerts()),
        }


class HealthChecker:
    """Simplified interface for single health checks."""

    @staticmethod
    def check_local(services: list[str] | None = None) -> NodeHealth:
        """Quick health check of the local system.

        Args:
            services: Optional list of services to check.

        Returns:
            NodeHealth for the local system.
        """
        config = NodeConfig(
            name="localhost",
            platform="auto",
            local=True,
            services=services or [],
        )
        collector = LocalCollector(config)
        return collector.collect()

    @staticmethod
    def check_remote(
        host: str,
        username: str,
        platform: str = "linux",
        services: list[str] | None = None,
        port: int = 22,
        key_file: str | None = None,
    ) -> NodeHealth:
        """Quick health check of a remote system via SSH.

        Args:
            host: Remote host address.
            username: SSH username.
            platform: Target platform (linux/darwin/windows).
            services: Optional list of services to check.
            port: SSH port (default 22).
            key_file: Optional SSH private key file path.

        Returns:
            NodeHealth for the remote system.
        """
        from node_health_monitor.config import SSHConfig

        config = NodeConfig(
            name=host,
            platform=platform,
            ssh=SSHConfig(
                username=username,
                host=host,
                port=port,
                key_file=key_file,
            ),
            services=services or [],
        )
        collector = SSHCollector(config)
        return collector.collect()
