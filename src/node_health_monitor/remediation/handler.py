"""Auto-remediation handler for executing remediation scripts."""

import logging
import os
import shlex
import subprocess
from pathlib import Path

from node_health_monitor.config import NodeConfig, RemediationConfig
from node_health_monitor.models import HealthStatus, NodeHealth

logger = logging.getLogger(__name__)


class RemediationHandler:
    """Handler for executing auto-remediation scripts.

    Remediation scripts are executed when health thresholds are exceeded.
    Scripts receive environment variables with node information.

    Scripts and commands run locally on the MONITORING host (the machine
    running node-health-monitor), not on the remote node that triggered the
    alert. The ``NHM_*`` environment variables identify the affected node so
    a local script can act on it (e.g. call an API or a runbook).

    Commands are executed without a shell: configured command strings are
    split into arguments with ``shlex.split``, so shell features such as
    pipes, redirection, and ``&&`` are not interpreted. Script files are
    executed directly and must be executable.
    """

    def __init__(
        self,
        config: RemediationConfig,
        node_config: NodeConfig,
        dry_run: bool = False,
    ) -> None:
        """Initialize remediation handler.

        Args:
            config: Remediation configuration.
            node_config: Node configuration for context.
            dry_run: If True, log actions but don't execute.
        """
        self.config = config
        self.node_config = node_config
        self.dry_run = dry_run
        self.scripts_dir = Path(config.scripts_dir).expanduser()

    def handle(self, health: NodeHealth) -> list[tuple[str, bool, str]]:
        """Handle remediation based on health status.

        Args:
            health: Current node health.

        Returns:
            List of (action, success, message) tuples.
        """
        if not self.config.enabled:
            return []

        results: list[tuple[str, bool, str]] = []

        # Check memory
        if health.memory_status == HealthStatus.CRITICAL and self.config.on_high_memory:
            result = self._execute_script(
                self.config.on_high_memory,
                "high_memory",
                health,
            )
            results.append(("high_memory", *result))

        # Check disk
        if health.disk_status == HealthStatus.CRITICAL and self.config.on_high_disk:
            result = self._execute_script(
                self.config.on_high_disk,
                "high_disk",
                health,
            )
            results.append(("high_disk", *result))

        # Check load
        if health.load_status == HealthStatus.CRITICAL and self.config.on_high_load:
            result = self._execute_script(
                self.config.on_high_load,
                "high_load",
                health,
            )
            results.append(("high_load", *result))

        # Check services
        for service in health.services:
            if not service.running and service.name in self.config.on_service_down:
                script = self.config.on_service_down[service.name]
                result = self._execute_script(
                    script,
                    f"service_down:{service.name}",
                    health,
                    extra_env={"NHM_SERVICE": service.name},
                )
                results.append((f"restart_{service.name}", *result))

        return results

    def _execute_script(
        self,
        script: str,
        action: str,
        health: NodeHealth,
        extra_env: dict | None = None,
    ) -> tuple[bool, str]:
        """Execute a remediation script.

        Args:
            script: Script path or command.
            action: Action name for logging.
            health: Current node health for environment.
            extra_env: Additional environment variables.

        Returns:
            Tuple of (success, message).
        """
        # Build environment
        env = {
            "NHM_NODE_NAME": health.name,
            "NHM_NODE_HOST": health.host,
            "NHM_NODE_PLATFORM": health.platform,
            "NHM_MEMORY_PERCENT": str(health.memory_percent),
            "NHM_DISK_PERCENT": str(health.disk_percent),
            "NHM_LOAD_1M": str(health.load_average[0]),
            "NHM_ACTION": action,
        }
        if extra_env:
            env.update(extra_env)

        # Resolve script path
        script_path = Path(script)
        if not script_path.is_absolute():
            script_path = self.scripts_dir / script

        # Run an existing script file directly; otherwise treat the configured
        # string as a command line. Either way the command runs WITHOUT a
        # shell: strings are split into an argument list with shlex, so shell
        # features (pipes, redirection, &&) are not interpreted.
        argv = [str(script_path)] if script_path.exists() else shlex.split(script)

        if self.dry_run:
            logger.info(f"[DRY RUN] Would execute: {argv} for {action}")
            return True, f"Dry run: {argv}"

        logger.info(f"Executing remediation command: {argv} for {action}")

        try:
            result = subprocess.run(
                argv,
                shell=False,
                capture_output=True,
                text=True,
                timeout=60,
                env={**os.environ, **env},
            )

            if result.returncode == 0:
                logger.info(f"Remediation succeeded: {action}")
                return True, result.stdout.strip() or "Success"
            else:
                logger.error(f"Remediation failed: {action} - {result.stderr}")
                return False, result.stderr.strip() or f"Exit code: {result.returncode}"

        except subprocess.TimeoutExpired:
            logger.error(f"Remediation timed out: {action}")
            return False, "Script timed out after 60s"
        except Exception as e:
            logger.error(f"Remediation error: {action} - {e}")
            return False, str(e)

    def execute_custom(
        self,
        script: str,
        health: NodeHealth,
    ) -> tuple[bool, str]:
        """Execute a custom remediation script.

        Args:
            script: Script path or command.
            health: Current node health for environment.

        Returns:
            Tuple of (success, message).
        """
        return self._execute_script(script, "custom", health)
