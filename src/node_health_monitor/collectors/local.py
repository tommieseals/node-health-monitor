"""Local system health collector using psutil."""

import platform
import subprocess
from datetime import datetime

import psutil

from node_health_monitor.collectors.base import BaseCollector
from node_health_monitor.config import NodeConfig
from node_health_monitor.models import NodeHealth, ServiceStatus


class LocalCollector(BaseCollector):
    """Collect health metrics from the local system."""
    
    def __init__(self, node_config: NodeConfig) -> None:
        super().__init__(node_config)
        self.platform = platform.system().lower()
    
    def collect(self) -> NodeHealth:
        """Collect all health metrics from local system."""
        try:
            # CPU info
            cpu_percent = psutil.cpu_percent(interval=0.5)
            cpu_count = psutil.cpu_count() or 1
            load_avg = self._get_load_average()
            
            # Memory info
            mem = psutil.virtual_memory()
            
            # Disk info (root partition)
            disk = psutil.disk_usage("/")
            
            # Collect service status
            services = []
            for service_name in self.config.services:
                running, pid = self.check_service(service_name)
                services.append(ServiceStatus(
                    name=service_name,
                    running=running,
                    pid=pid,
                ))
            
            # Get thresholds
            thresholds = self.config.thresholds or self._get_default_thresholds()
            
            return NodeHealth(
                name=self.config.name,
                host="localhost",
                platform=self.platform,
                timestamp=datetime.now(),
                reachable=True,
                cpu_percent=cpu_percent,
                cpu_count=cpu_count,
                load_average=load_avg,
                memory_total_gb=mem.total / (1024**3),
                memory_used_gb=mem.used / (1024**3),
                memory_percent=mem.percent,
                disk_total_gb=disk.total / (1024**3),
                disk_used_gb=disk.used / (1024**3),
                disk_percent=disk.percent,
                services=services,
                thresholds=thresholds.to_dict(),
            )
        except Exception as e:
            return NodeHealth(
                name=self.config.name,
                host="localhost",
                platform=self.platform,
                timestamp=datetime.now(),
                reachable=False,
                error_message=str(e),
            )
    
    def _get_load_average(self) -> tuple[float, float, float]:
        """Get system load average (handles Windows which doesn't have it)."""
        if self.platform == "windows":
            # Windows doesn't have load average, approximate with CPU queue
            cpu_percent = psutil.cpu_percent()
            # Rough approximation
            return (cpu_percent / 25, cpu_percent / 25, cpu_percent / 25)
        return psutil.getloadavg()
    
    def _get_default_thresholds(self):
        """Get default thresholds if none configured."""
        from node_health_monitor.config import Thresholds
        return Thresholds()
    
    def check_service(self, service_name: str) -> tuple[bool, int | None]:
        """Check if a service/process is running."""
        service_lower = service_name.lower()
        
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                name = (proc.info.get("name") or "").lower()
                cmdline = " ".join(proc.info.get("cmdline") or []).lower()
                
                if service_lower in name or service_lower in cmdline:
                    return True, proc.info["pid"]
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        return False, None
    
    def execute_command(self, command: str) -> tuple[int, str, str]:
        """Execute a local command."""
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return 1, "", "Command timed out"
        except Exception as e:
            return 1, "", str(e)
