"""Auto-remediation handler for executing remediation scripts."""

import logging
import subprocess
from pathlib import Path
from typing import Optional

from node_health_monitor.config import NodeConfig, RemediationConfig
from node_health_monitor.models import NodeHealth, HealthStatus

logger = logging.getLogger(__name__)


class RemediationHandler:
    """Handler for executing auto-remediation scripts.
    
    Remediation scripts are executed when health thresholds are exceeded.
    Scripts receive environment variables with node information.
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
        extra_env: Optional[dict] = None,
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
        
        if self.dry_run:
            logger.info(f"[DRY RUN] Would execute: {script_path} for {action}")
            return True, f"Dry run: {script_path}"
        
        logger.info(f"Executing remediation script: {script_path} for {action}")
        
        try:
            # Check if it's a script file or command
            if script_path.exists():
                cmd = str(script_path)
            else:
                # Treat as shell command
                cmd = script
            
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=60,
                env={**subprocess.os.environ, **env},  # type: ignore
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
