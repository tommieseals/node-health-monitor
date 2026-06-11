# Node Health Monitor

[![CI](https://github.com/tommieseals/node-health-monitor/actions/workflows/ci.yml/badge.svg)](https://github.com/tommieseals/node-health-monitor/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

Multi-platform server health monitoring with a CLI, web dashboard, alerting, and optional auto-remediation hooks.

Monitor Linux, macOS, and Windows servers from a single tool: local checks via psutil, remote checks over SSH, with configurable thresholds and Telegram/Slack/webhook notifications.

Example `nhm local` output (captured on a real machine):

```text
$ nhm local
┌──────────────────────────── Local System Health ────────────────────────────┐
│ Status: HEALTHY                                                             │
│ CPU: 4.3% (28 cores)                                                        │
│ Memory: 23.7% of 63.7 GB                                                    │
│ Disk: 37.9% of 474.3 GB                                                     │
│ Load: 0.00, 0.00, 0.00                                                      │
│ Platform: windows                                                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Features

- **Multi-platform support** - monitor Linux, macOS, and Windows servers via SSH
- **Metrics** - CPU, memory, disk, load average, and service status
- **Web dashboard** - FastAPI dashboard with configurable auto-refresh
- **Alerting** - Telegram, Slack, and generic webhook notifications, with
  per-alert cooldown and recovery messages
- **Auto-remediation** - run configured scripts on the monitoring host when
  thresholds are breached
- **Parallel checks** - check many nodes concurrently
- **YAML configuration** - simple, human-readable config files
- **Python API** - use the monitor programmatically

## Architecture

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

## Quick Start

### Installation

This package is not published on PyPI. Install it from GitHub:

```bash
pip install git+https://github.com/tommieseals/node-health-monitor

# Or install from a local clone
git clone https://github.com/tommieseals/node-health-monitor.git
cd node-health-monitor
pip install -e .
```

Requires Python 3.10 or newer.

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

## Configuration

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
  load_warning: 4.0     # absolute 1-minute load average (not per-CPU)
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

## CLI Commands

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

## Web Dashboard

The built-in web dashboard provides:

- **Cluster overview** - at-a-glance status of all nodes
- **Per-node metrics** - current CPU, memory, disk, and load values
- **Service status** - which services are running or stopped
- **Active alerts** - all current issues in one place
- **Auto-refresh** - configurable refresh interval

Start the dashboard:

```bash
nhm dashboard --host 0.0.0.0 --port 8080
```

Access at: `http://localhost:8080`

## SSH host key verification

The SSH collector verifies remote host keys against your `known_hosts` and
**rejects connections to unknown hosts** (`paramiko.RejectPolicy`). It does not
auto-trust new hosts, because silently accepting an unverified key would expose
every check to man-in-the-middle attacks.

Before monitoring a new node, add its host key to your `known_hosts`:

```bash
# Easiest: connect once interactively and accept the fingerprint
ssh admin@192.168.1.10

# Or fetch the key non-interactively (verify the fingerprint out-of-band!)
ssh-keyscan -H 192.168.1.10 >> ~/.ssh/known_hosts
```

By default the user's `~/.ssh/known_hosts` is used. You can also point a node
at an extra known_hosts file:

```yaml
nodes:
  web-server:
    platform: linux
    ssh:
      username: admin
      host: 192.168.1.10
      known_hosts: ~/.config/nhm/known_hosts
```

If a connection fails with a host-key error, the host is either new (add its
key as shown above) or its key changed — investigate before trusting it again.

## Alerting

Notifiers are built from the `notifiers:` section of the config and invoked
automatically during `nhm check`, `nhm check --watch`, and dashboard-triggered
checks. When a node crosses a threshold (or a watched service stops), every
configured notifier receives the alert; the same alert is not repeated within
a 5-minute cooldown, and a recovery message is sent when the node returns to
healthy. A notifier section is active when present; set `enabled: false` to
keep the section but turn it off.

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

## Auto-Remediation

Remediation is configured **per node**. When a check finds a critical metric
or a down service, the configured hook runs automatically.

Remediation scripts execute **on the monitoring host** (the machine running
`nhm`), not on the remote node being monitored. The `NHM_*` environment
variables identify the node that triggered the action, so a hook for a remote
node should perform an action that makes sense locally — call an API, trigger
a runbook, page someone. Hooks that act on the machine itself (restart a
service, clear caches) are only meaningful on nodes with `local: true`:

```yaml
nodes:
  monitor-host:
    platform: linux
    local: true
    services:
      - nginx
    remediation:
      enabled: true
      scripts_dir: ./remediation
      on_high_memory: cleanup-memory.sh
      on_high_disk: cleanup-disk.sh
      on_service_down:
        nginx: "systemctl restart nginx"
```

Commands run without a shell: command strings are split into arguments
(`shlex`), so pipes, redirection, and `&&` are not interpreted. Script files
are executed directly and must be executable (`chmod +x`). Each hook is
limited to 60 seconds.

Environment variables passed to hooks:

| Variable | Description |
|----------|-------------|
| `NHM_NODE_NAME` | Name of the node that triggered the action |
| `NHM_NODE_HOST` | Host address of that node |
| `NHM_NODE_PLATFORM` | Platform (`linux`/`darwin`/`windows`) |
| `NHM_MEMORY_PERCENT` | Memory usage at check time |
| `NHM_DISK_PERCENT` | Disk usage at check time |
| `NHM_LOAD_1M` | 1-minute load average at check time |
| `NHM_ACTION` | Triggering action (e.g. `high_memory`, `service_down:nginx`) |
| `NHM_SERVICE` | Service name (only for `on_service_down` hooks) |

Example remediation script:

```bash
#!/bin/bash
# cleanup-memory.sh — runs on the monitoring host
echo "High memory on ${NHM_NODE_NAME} (${NHM_MEMORY_PERCENT}%)"

# Local cleanup (meaningful when the node is the monitoring host itself)
sync && echo 3 > /proc/sys/vm/drop_caches
docker system prune -f
```

## Python API

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

## Metrics Collected

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

## Contributing

See [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md).

```bash
# Clone the repo
git clone https://github.com/tommieseals/node-health-monitor.git
cd node-health-monitor

# Install dev dependencies
pip install -e ".[dev]"

# Run tests (CI gates on these)
pytest

# Run linting (CI gates on this)
ruff check .
```

## About this repo

Published as a curated snapshot of tooling I maintain; history was
consolidated for publication.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [Paramiko](https://www.paramiko.org/) - SSH connections
- [psutil](https://github.com/giampaolo/psutil) - Local system metrics
- [Rich](https://github.com/Textualize/rich) - Beautiful terminal output
- [FastAPI](https://fastapi.tiangolo.com/) - Web dashboard
- [Click](https://click.palletsprojects.com/) - CLI framework
