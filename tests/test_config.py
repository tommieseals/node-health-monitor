"""Tests for configuration module."""

import tempfile
from pathlib import Path

import pytest
import yaml

from node_health_monitor.config import (
    Config,
    NodeConfig,
    SSHConfig,
    Thresholds,
    create_example_config,
)


class TestThresholds:
    """Tests for Thresholds configuration."""
    
    def test_default_values(self):
        t = Thresholds()
        assert t.memory_warning == 80.0
        assert t.memory_critical == 90.0
        assert t.disk_warning == 80.0
        assert t.disk_critical == 90.0
        assert t.load_warning == 4.0
        assert t.load_critical == 8.0
    
    def test_from_dict(self):
        data = {
            "memory_warning": 70.0,
            "memory_critical": 85.0,
            "disk_warning": 75.0,
            "disk_critical": 88.0,
        }
        t = Thresholds.from_dict(data)
        assert t.memory_warning == 70.0
        assert t.memory_critical == 85.0
        # Defaults for missing values
        assert t.load_warning == 4.0
    
    def test_to_dict(self):
        t = Thresholds()
        d = t.to_dict()
        assert "memory" in d
        assert "disk" in d
        assert "load" in d
        assert d["memory"] == (80.0, 90.0)


class TestSSHConfig:
    """Tests for SSH configuration."""
    
    def test_from_dict_minimal(self):
        data = {"username": "admin", "host": "192.168.1.10"}
        ssh = SSHConfig.from_dict(data)
        assert ssh.username == "admin"
        assert ssh.host == "192.168.1.10"
        assert ssh.port == 22  # Default
        assert ssh.key_file is None
    
    def test_from_dict_full(self):
        data = {
            "username": "root",
            "host": "10.0.0.1",
            "port": 2222,
            "key_file": "~/.ssh/custom_key",
            "timeout": 30,
        }
        ssh = SSHConfig.from_dict(data)
        assert ssh.port == 2222
        assert ssh.key_file == "~/.ssh/custom_key"
        assert ssh.timeout == 30


class TestNodeConfig:
    """Tests for node configuration."""
    
    def test_from_dict_ssh_node(self):
        data = {
            "platform": "linux",
            "ssh": {"username": "admin", "host": "192.168.1.10"},
            "services": ["nginx", "docker"],
            "tags": ["production", "web"],
        }
        node = NodeConfig.from_dict("web-server", data)
        assert node.name == "web-server"
        assert node.platform == "linux"
        assert node.ssh is not None
        assert node.ssh.host == "192.168.1.10"
        assert "nginx" in node.services
        assert "production" in node.tags
    
    def test_from_dict_local_node(self):
        data = {
            "platform": "darwin",
            "local": True,
            "services": ["ollama"],
        }
        node = NodeConfig.from_dict("localhost", data)
        assert node.local is True
        assert node.ssh is None


class TestConfig:
    """Tests for main configuration."""
    
    def test_from_dict(self):
        data = {
            "nodes": {
                "server1": {
                    "platform": "linux",
                    "ssh": {"username": "admin", "host": "192.168.1.10"},
                },
                "server2": {
                    "platform": "darwin",
                    "local": True,
                },
            },
            "thresholds": {
                "memory_warning": 75.0,
            },
            "check_interval": 120,
        }
        config = Config.from_dict(data)
        assert len(config.nodes) == 2
        assert config.thresholds.memory_warning == 75.0
        assert config.check_interval == 120
    
    def test_from_yaml(self):
        yaml_content = """
nodes:
  web-server:
    platform: linux
    ssh:
      username: admin
      host: 192.168.1.10
    services:
      - nginx
      - docker

thresholds:
  memory_warning: 80
  memory_critical: 90

check_interval: 60
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            
            config = Config.from_yaml(f.name)
            assert len(config.nodes) == 1
            assert config.nodes[0].name == "web-server"
            assert config.check_interval == 60
            
            Path(f.name).unlink()
    
    def test_get_enabled_nodes(self):
        data = {
            "nodes": {
                "enabled": {"platform": "linux", "local": True, "enabled": True},
                "disabled": {"platform": "linux", "local": True, "enabled": False},
            }
        }
        config = Config.from_dict(data)
        enabled = config.get_enabled_nodes()
        assert len(enabled) == 1
        assert enabled[0].name == "enabled"
    
    def test_get_node(self):
        data = {
            "nodes": {
                "server1": {"platform": "linux", "local": True},
                "server2": {"platform": "darwin", "local": True},
            }
        }
        config = Config.from_dict(data)
        node = config.get_node("server1")
        assert node is not None
        assert node.name == "server1"
        
        missing = config.get_node("nonexistent")
        assert missing is None
    
    def test_to_yaml(self):
        config = create_example_config()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test-config.yaml"
            config.to_yaml(path)
            
            assert path.exists()
            
            # Reload and verify
            loaded = Config.from_yaml(path)
            assert len(loaded.nodes) == len(config.nodes)


class TestExampleConfig:
    """Tests for example configuration creation."""
    
    def test_create_example_config(self):
        config = create_example_config()
        assert len(config.nodes) > 0
        assert config.thresholds is not None
        
        # Verify different platform types
        platforms = {n.platform for n in config.nodes}
        assert "linux" in platforms
        assert "darwin" in platforms
        assert "windows" in platforms
        
        # Verify local node exists
        local_nodes = [n for n in config.nodes if n.local]
        assert len(local_nodes) > 0
