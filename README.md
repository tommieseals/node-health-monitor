# 🖥️ Node Health Monitor

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

A powerful, multi-platform server health monitoring solution with CLI, web dashboard, alerting, and auto-remediation capabilities.

Monitor your entire infrastructure—Linux, macOS, and Windows servers—from a single tool. Get real-time health metrics, automated alerts, and optional self-healing capabilities.

![Dashboard Screenshot](docs/images/dashboard-preview.png)

## ✨ Features

- **🌐 Multi-Platform Support** - Monitor Linux, macOS, and Windows servers via SSH
- **📊 Comprehensive Metrics** - CPU, RAM, Disk, Load Average, Service Status
- **🎨 Beautiful Web Dashboard** - Real-time monitoring with auto-refresh
- **🔔 Smart Alerting** - Telegram, Slack, and webhook notifications
- **🔧 Auto-Remediation** - Execute custom scripts when thresholds are breached
- **⚡ Parallel Checks** - Monitor dozens of nodes simultaneously
- **📝 YAML Configuration** - Simple, human-readable config files
- **🐍 Pure Python** - Easy to install, extend, and integrate

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Node Health Monitor                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐        │
│  │   CLI       │    │  Dashboard  │    │  Scheduler  │        │
│  │   (Rich)    │    │  (FastAPI)  │    │  (Optional) │        │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘        │
│         │                  │                  │                │
│         └──────────────────┼──────────────────┘                │
│                            │                                    │
│                    ┌───────▼───────┐                           │
│                    │ Health Monitor│                           │
│                    │    (Core)     │                           │
│                    └───────┬───────┘                           │
│                            │                                    │
│         ┌──────────────────┼──────────────────┐                │
│         │                  │                  │                │
│  ┌──────▼──────┐   ┌──────▼──────┐   ┌──────▼──────┐         │
│  │   Local     │   │    SSH      │   │ Notifiers   │         │
│  │  Collector  │   │  Collector  │   │ (Telegram,  │         │
│  │  (psutil)   │   │ (paramiko)  │   │  Slack...)  │         │
│  └──────┬──────┘   └──────┬──────┘   └─────────────┘         │
│         │                  │                                    │
└─────────┼──────────────────┼────────────────────────────────────┘
          │                  │
          ▼                  ▼
    ┌──────────┐    ┌──────────────────────────────────────┐
    │ localhost│    │           Remote Nodes               │
    └──────────┘    │  ┌────────┐ ┌────────┐ ┌────────┐  │
                    │  │ Linux  │ │ macOS  │ │Windows │  │
                    │  │ Server │ │ Server │ │ Server │  │
                    │  └────────┘ └────────┘ └────────┘  │
                    └──────────────────────────────────────┘
```

## 🚀 Quick Start

### Installation

```bash
# Install from PyPI (recommended)
pip install node-health-monitor

# Or install from source
git clone https://github.com/tommieseals/node-health-monitor.git
cd node-health-monitor
pip install -e .
```

### Basic Usage

```bash
# Check local system health
nhm local

# Create a configuration file
nhm init

# Edit nhm.yaml with your nodes, then:
nhm check

# Start the web dashboard
nhm dashboard

# Quick check a remote host
nhm quick 192.168.1.10 -u admin -s nginx -s docker
```

## 📖 Configuration

Create `nhm.yaml` in your working directory:

```yaml
nodes:
  web-server:
    platform: linux
    ssh:
      username: admin
      host: 192.168.1.10
    services:
      - nginx
      - docker

  database:
    platform: linux
    ssh:
      username: postgres
      host: 192.168.1.20
    services:
      - postgresql
    thresholds:
      memory_warning: 85
      memory_critical: 95

  mac-workstation:
    platform: darwin
    ssh:
      username: user
      host: 192.168.1.30
    services:
      - ollama

  localhost:
    platform: linux
    local: true

thresholds:
  memory_warning: 80
  memory_critical: 90
  disk_warning: 80
  disk_critical: 90
  load_warning: 4.0
  load_critical: 8.0

notifiers:
  telegram:
    enabled: true
    bot_token: "YOUR_BOT_TOKEN"
    chat_id: "YOUR_CHAT_ID"

dashboard:
  port: 8080
  refresh_interval: 30
```

## 💻 CLI Commands

```bash
# Check all configured nodes
nhm check

# Check with JSON output
nhm check --json

# Watch mode (continuous monitoring)
nhm check --watch --interval 60

# Check single remote host
nhm quick 192.168.1.10 -u admin -p linux -s nginx

# Check local system only
nhm local

# Start web dashboard
nhm dashboard --port 8080

# Create example config
nhm init -o myconfig.yaml
```

## 🌐 Web Dashboard

The built-in web dashboard provides real-time monitoring:

- **Cluster Overview** - At-a-glance status of all nodes
- **Per-Node Metrics** - Detailed CPU, memory, disk, and load graphs
- **Service Status** - See which services are running/stopped
- **Active Alerts** - All current issues in one place
- **Auto-Refresh** - Configurable refresh interval

Start the dashboard:

```bash
nhm dashboard --host 0.0.0.0 --port 8080
```

Access at: `http://localhost:8080`

## 🔔 Alerting

### Telegram

```yaml
notifiers:
  telegram:
    enabled: true
    bot_token: "123456:ABC-DEF..."
    chat_id: "-1001234567890"
```

### Slack

```yaml
notifiers:
  slack:
    enabled: true
    webhook_url: "https://hooks.slack.com/services/T00/B00/XXX"
    channel: "#alerts"
```

### Generic Webhook

```yaml
notifiers:
  webhook:
    enabled: true
    url: "https://your-endpoint.com/alerts"
    method: POST
    headers:
      Authorization: "Bearer token123"
```

## 🔧 Auto-Remediation

Enable automatic remediation scripts when thresholds are exceeded:

```yaml
remediation:
  enabled: true
  scripts_dir: ./remediation
  on_high_memory: cleanup-memory.sh
  on_high_disk: cleanup-disk.sh
  on_service_down:
    nginx: "sudo systemctl restart nginx"
    docker: "sudo systemctl restart docker"
```

Example remediation script:

```bash
#!/bin/bash
# cleanup-memory.sh
echo "Cleaning memory on ${NHM_NODE_NAME}"
echo "Current usage: ${NHM_MEMORY_PERCENT}%"

# Clear caches
sync && echo 3 > /proc/sys/vm/drop_caches

# Docker cleanup
docker system prune -f
```

## 🐍 Python API

Use Node Health Monitor programmatically:

```python
from node_health_monitor import Config, HealthMonitor, HealthChecker

# Quick local check
health = HealthChecker.check_local(services=["docker", "nginx"])
print(f"Status: {health.status}")
print(f"Memory: {health.memory_percent}%")

# Quick remote check
health = HealthChecker.check_remote(
    host="192.168.1.10",
    username="admin",
    platform="linux",
    services=["nginx"],
)

# Full monitoring with config
config = Config.from_yaml("nhm.yaml")
monitor = HealthMonitor(config)

# Check all nodes
cluster = monitor.check_all()
print(f"Cluster status: {cluster.status}")
for node in cluster.nodes:
    print(f"  {node.name}: {node.status}")
```

## 📊 Metrics Collected

| Metric | Description | Platforms |
|--------|-------------|-----------|
| CPU % | Current CPU utilization | All |
| CPU Count | Number of logical cores | All |
| Load Average | 1/5/15 minute load | Linux, macOS |
| Memory Total | Total RAM in GB | All |
| Memory Used | Used RAM in GB and % | All |
| Disk Total | Root partition size | All |
| Disk Used | Disk usage in GB and % | All |
| Services | Running status of configured services | All |

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

```bash
# Clone the repo
git clone https://github.com/tommieseals/node-health-monitor.git
cd node-health-monitor

# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linting
ruff check .
black --check .

# Run type checking
mypy src
```

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Paramiko](https://www.paramiko.org/) - SSH connections
- [psutil](https://github.com/giampaolo/psutil) - Local system metrics
- [Rich](https://github.com/Textualize/rich) - Beautiful terminal output
- [FastAPI](https://fastapi.tiangolo.com/) - Web dashboard
- [Click](https://click.palletsprojects.com/) - CLI framework

---

**Made with ❤️ for infrastructure nerds everywhere**
