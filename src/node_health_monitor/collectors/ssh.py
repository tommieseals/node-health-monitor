"""SSH-based remote health collector."""

import logging
import re
from datetime import datetime
from pathlib import Path

import paramiko

from node_health_monitor.collectors.base import BaseCollector
from node_health_monitor.config import NodeConfig
from node_health_monitor.models import NodeHealth, ServiceStatus

logger = logging.getLogger(__name__)


class SSHCollector(BaseCollector):
    """Collect health metrics from remote systems via SSH."""
    
    # Platform-specific commands
    COMMANDS = {
        "linux": {
            "memory": "free -b | grep Mem",
            "disk": "df -B1 / | tail -1",
            "load": "cat /proc/loadavg",
            "cpu_count": "nproc",
            "cpu_percent": "top -bn1 | grep 'Cpu(s)' | awk '{print $2}'",
            "service_check": "pgrep -x {service} || pgrep -f {service}",
        },
        "darwin": {
            "memory": "vm_stat && sysctl -n hw.memsize",
            "disk": "df -b / | tail -1",
            "load": "sysctl -n vm.loadavg",
            "cpu_count": "sysctl -n hw.ncpu",
            "cpu_percent": "ps -A -o %cpu | awk '{s+=$1} END {print s}'",
            "service_check": "pgrep -x {service} || pgrep -f {service}",
        },
        "windows": {
            "memory": "wmic OS get FreePhysicalMemory,TotalVisibleMemorySize /Value",
            "disk": "wmic logicaldisk where DeviceID='C:' get Size,FreeSpace /Value",
            "load": "wmic cpu get LoadPercentage /Value",
            "cpu_count": "wmic cpu get NumberOfLogicalProcessors /Value",
            "cpu_percent": "wmic cpu get LoadPercentage /Value",
            "service_check": "tasklist /FI \"IMAGENAME eq {service}*\" /NH",
        },
    }
    
    def __init__(self, node_config: NodeConfig) -> None:
        super().__init__(node_config)
        self._client: paramiko.SSHClient | None = None
    
    def _get_client(self) -> paramiko.SSHClient:
        """Get or create SSH client connection."""
        if self._client is not None:
            try:
                # Test if connection is still alive
                self._client.get_transport()
                if self._client.get_transport() and self._client.get_transport().is_active():
                    return self._client
            except Exception:
                pass
        
        ssh_config = self.config.ssh
        if not ssh_config:
            raise ValueError(f"No SSH configuration for node: {self.config.name}")
        
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        connect_kwargs = {
            "hostname": ssh_config.host,
            "port": ssh_config.port,
            "username": ssh_config.username,
            "timeout": ssh_config.timeout,
        }
        
        if ssh_config.key_file:
            key_path = Path(ssh_config.key_file).expanduser()
            connect_kwargs["key_filename"] = str(key_path)
        elif ssh_config.password:
            connect_kwargs["password"] = ssh_config.password
        else:
            # Try to use default SSH agent
            connect_kwargs["allow_agent"] = True
            connect_kwargs["look_for_keys"] = True
        
        client.connect(**connect_kwargs)
        self._client = client
        return client
    
    def close(self) -> None:
        """Close SSH connection."""
        if self._client:
            self._client.close()
            self._client = None
    
    def execute_command(self, command: str) -> tuple[int, str, str]:
        """Execute command on remote system."""
        try:
            client = self._get_client()
            stdin, stdout, stderr = client.exec_command(command, timeout=30)
            exit_code = stdout.channel.recv_exit_status()
            return exit_code, stdout.read().decode(), stderr.read().decode()
        except Exception as e:
            logger.error(f"SSH command failed on {self.config.name}: {e}")
            return 1, "", str(e)
    
    def collect(self) -> NodeHealth:
        """Collect all health metrics from remote system."""
        platform = self.config.platform
        ssh_config = self.config.ssh
        
        if not ssh_config:
            return NodeHealth(
                name=self.config.name,
                host="unknown",
                platform=platform,
                reachable=False,
                error_message="No SSH configuration",
            )
        
        try:
            # Collect all metrics
            cpu_percent, cpu_count = self._collect_cpu(platform)
            load_avg = self._collect_load(platform)
            mem_total, mem_used, mem_percent = self._collect_memory(platform)
            disk_total, disk_used, disk_percent = self._collect_disk(platform)
            
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
                host=ssh_config.host,
                platform=platform,
                timestamp=datetime.now(),
                reachable=True,
                cpu_percent=cpu_percent,
                cpu_count=cpu_count,
                load_average=load_avg,
                memory_total_gb=mem_total,
                memory_used_gb=mem_used,
                memory_percent=mem_percent,
                disk_total_gb=disk_total,
                disk_used_gb=disk_used,
                disk_percent=disk_percent,
                services=services,
                thresholds=thresholds.to_dict(),
            )
        except Exception as e:
            logger.exception(f"Failed to collect metrics from {self.config.name}")
            return NodeHealth(
                name=self.config.name,
                host=ssh_config.host,
                platform=platform,
                timestamp=datetime.now(),
                reachable=False,
                error_message=str(e),
            )
        finally:
            self.close()
    
    def _get_default_thresholds(self):
        """Get default thresholds."""
        from node_health_monitor.config import Thresholds
        return Thresholds()
    
    def _collect_cpu(self, platform: str) -> tuple[float, int]:
        """Collect CPU metrics."""
        commands = self.COMMANDS.get(platform, self.COMMANDS["linux"])
        
        # Get CPU count
        _, stdout, _ = self.execute_command(commands["cpu_count"])
        cpu_count = int(stdout.strip().split("=")[-1]) if stdout.strip() else 1
        
        # Get CPU percent
        _, stdout, _ = self.execute_command(commands["cpu_percent"])
        try:
            cpu_percent = float(stdout.strip().split("=")[-1].replace(",", "."))
        except ValueError:
            cpu_percent = 0.0
        
        return cpu_percent, cpu_count
    
    def _collect_load(self, platform: str) -> tuple[float, float, float]:
        """Collect load average."""
        commands = self.COMMANDS.get(platform, self.COMMANDS["linux"])
        _, stdout, _ = self.execute_command(commands["load"])
        
        if platform == "darwin":
            # macOS: { 1.23 1.45 1.67 }
            match = re.search(r"\{\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)", stdout)
            if match:
                return float(match.group(1)), float(match.group(2)), float(match.group(3))
        elif platform == "linux":
            # Linux: 1.23 1.45 1.67 1/234 5678
            parts = stdout.strip().split()
            if len(parts) >= 3:
                return float(parts[0]), float(parts[1]), float(parts[2])
        elif platform == "windows":
            # Windows: Approximate from CPU load
            match = re.search(r"LoadPercentage=(\d+)", stdout)
            if match:
                load = float(match.group(1)) / 25  # Rough approximation
                return load, load, load
        
        return (0.0, 0.0, 0.0)
    
    def _collect_memory(self, platform: str) -> tuple[float, float, float]:
        """Collect memory metrics. Returns (total_gb, used_gb, percent)."""
        commands = self.COMMANDS.get(platform, self.COMMANDS["linux"])
        _, stdout, _ = self.execute_command(commands["memory"])
        
        if platform == "linux":
            # free -b output: Mem: total used free shared buff/cache available
            parts = stdout.strip().split()
            if len(parts) >= 3:
                total = int(parts[1]) / (1024**3)
                used = int(parts[2]) / (1024**3)
                percent = (used / total) * 100 if total > 0 else 0
                return total, used, percent
        
        elif platform == "darwin":
            # Parse vm_stat and hw.memsize
            lines = stdout.strip().split("\n")
            page_size = 4096
            total_bytes = 0
            free_pages = 0
            
            for line in lines:
                if "hw.memsize" in line or line.strip().isdigit():
                    try:
                        total_bytes = int(line.strip().split(":")[-1].strip())
                    except ValueError:
                        pass
                elif "Pages free:" in line:
                    match = re.search(r"(\d+)", line)
                    if match:
                        free_pages += int(match.group(1))
                elif "Pages inactive:" in line:
                    match = re.search(r"(\d+)", line)
                    if match:
                        free_pages += int(match.group(1))
            
            total = total_bytes / (1024**3)
            free = (free_pages * page_size) / (1024**3)
            used = total - free
            percent = (used / total) * 100 if total > 0 else 0
            return total, used, percent
        
        elif platform == "windows":
            # wmic output
            total = 0
            free = 0
            for line in stdout.strip().split("\n"):
                if "TotalVisibleMemorySize" in line:
                    match = re.search(r"(\d+)", line)
                    if match:
                        total = int(match.group(1)) * 1024 / (1024**3)  # KB to GB
                elif "FreePhysicalMemory" in line:
                    match = re.search(r"(\d+)", line)
                    if match:
                        free = int(match.group(1)) * 1024 / (1024**3)
            
            used = total - free
            percent = (used / total) * 100 if total > 0 else 0
            return total, used, percent
        
        return (0.0, 0.0, 0.0)
    
    def _collect_disk(self, platform: str) -> tuple[float, float, float]:
        """Collect disk metrics. Returns (total_gb, used_gb, percent)."""
        commands = self.COMMANDS.get(platform, self.COMMANDS["linux"])
        _, stdout, _ = self.execute_command(commands["disk"])
        
        if platform in ("linux", "darwin"):
            # df output: Filesystem 1B-blocks Used Available Capacity Mounted
            parts = stdout.strip().split()
            if len(parts) >= 4:
                total = int(parts[1]) / (1024**3)
                used = int(parts[2]) / (1024**3)
                percent = (used / total) * 100 if total > 0 else 0
                return total, used, percent
        
        elif platform == "windows":
            total = 0
            free = 0
            for line in stdout.strip().split("\n"):
                if "Size=" in line:
                    match = re.search(r"(\d+)", line)
                    if match:
                        total = int(match.group(1)) / (1024**3)
                elif "FreeSpace=" in line:
                    match = re.search(r"(\d+)", line)
                    if match:
                        free = int(match.group(1)) / (1024**3)
            
            used = total - free
            percent = (used / total) * 100 if total > 0 else 0
            return total, used, percent
        
        return (0.0, 0.0, 0.0)
    
    def check_service(self, service_name: str) -> tuple[bool, int | None]:
        """Check if a service is running on remote system."""
        platform = self.config.platform
        commands = self.COMMANDS.get(platform, self.COMMANDS["linux"])
        
        cmd = commands["service_check"].format(service=service_name)
        exit_code, stdout, _ = self.execute_command(cmd)
        
        if platform == "windows":
            # Windows tasklist returns process info or "INFO: No tasks"
            running = service_name.lower() in stdout.lower() and "no tasks" not in stdout.lower()
            pid = None
            if running:
                # Try to extract PID from tasklist output
                match = re.search(rf"{service_name}\S*\s+(\d+)", stdout, re.IGNORECASE)
                if match:
                    pid = int(match.group(1))
            return running, pid
        else:
            # Unix-like: pgrep returns PID(s) if found
            if exit_code == 0 and stdout.strip():
                try:
                    pid = int(stdout.strip().split()[0])
                    return True, pid
                except ValueError:
                    return True, None
            return False, None
