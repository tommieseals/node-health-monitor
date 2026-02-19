"""Base collector interface."""

from abc import ABC, abstractmethod

from node_health_monitor.config import NodeConfig
from node_health_monitor.models import NodeHealth


class BaseCollector(ABC):
    """Abstract base class for health data collectors."""
    
    def __init__(self, node_config: NodeConfig) -> None:
        """Initialize collector with node configuration."""
        self.config = node_config
    
    @abstractmethod
    def collect(self) -> NodeHealth:
        """Collect health data from the node.
        
        Returns:
            NodeHealth object with collected metrics.
        """
        ...
    
    @abstractmethod
    def check_service(self, service_name: str) -> tuple[bool, int | None]:
        """Check if a service is running.
        
        Args:
            service_name: Name of the service to check.
            
        Returns:
            Tuple of (is_running, pid or None).
        """
        ...
    
    @abstractmethod
    def execute_command(self, command: str) -> tuple[int, str, str]:
        """Execute a command on the node.
        
        Args:
            command: Command to execute.
            
        Returns:
            Tuple of (exit_code, stdout, stderr).
        """
        ...
