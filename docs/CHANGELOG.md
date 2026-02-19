# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2024-01-15

### Added
- Initial release
- Multi-platform support (Linux, macOS, Windows)
- SSH-based remote health collection
- Local system monitoring via psutil
- Configurable alert thresholds per node
- Telegram notifications
- Slack notifications
- Generic webhook notifications
- FastAPI web dashboard with real-time updates
- Auto-remediation hooks
- Rich CLI with colored output
- YAML configuration
- Parallel node checking
- Service status monitoring
- Comprehensive test suite

### Features
- `nhm check` - Check all configured nodes
- `nhm local` - Quick local system check
- `nhm quick` - Quick remote host check
- `nhm dashboard` - Start web dashboard
- `nhm init` - Generate example configuration

## [Unreleased]

### Planned
- Historical data storage (SQLite/InfluxDB)
- Prometheus metrics endpoint
- Docker image
- Kubernetes operator
- Email notifications
- PagerDuty integration
- Custom metric collectors
- Agent mode (push-based)
