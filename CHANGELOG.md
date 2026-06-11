# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- Historical data storage (SQLite/InfluxDB)
- Prometheus metrics endpoint
- Docker image
- Email notifications
- Custom metric collectors

## [1.1.0] - 2026-06-11

### Added
- Notifiers are now part of the monitoring flow: `HealthMonitor` builds
  Telegram/Slack/webhook notifiers from the `notifiers:` config section and
  dispatches alerts during checks (with the existing 5-minute per-alert
  cooldown). A recovery notification is sent when a node returns to healthy.
  Previously the notifier classes were only reachable through a manually
  supplied `on_alert` callback, so `nhm check` never sent anything.
- Auto-remediation is now invoked by the monitor: nodes with an enabled
  `remediation:` section run their configured hooks when a check reports a
  critical metric or a down service. Previously the handler existed but was
  never called.
- The SSH collector marks a node unreachable when the SSH connection cannot
  be established. Previously a failed connection produced zeroed metrics on
  a node still reported as reachable.
- Tests for the notifiers (HTTP mocked), the SSH collector (paramiko
  mocked), the remediation handler (subprocess mocked), and the monitor's
  alert-dispatch and remediation paths.

### Changed
- Remediation commands run without a shell (`shell=False`). Configured
  command strings are split with `shlex`, so pipes/redirection are no longer
  interpreted; script files must be executable.
- Documentation now states explicitly that remediation runs on the
  monitoring host, not on the remote node. The previous README example
  implied remote execution.
- CHANGELOG moved from `docs/` to the repository root; added `SECURITY.md`;
  condensed `CONTRIBUTING.md`.

## [1.0.1] - 2026-06-11

Maintenance release: honest CI, bug fixes, and documentation cleanup.

### Fixed
- Load-average alerting: `NodeHealth.load_status` divided the 1-minute load
  by CPU count while every threshold, test, and doc treats load limits as
  absolute values. Load alerts now compare the absolute 1-minute load
  against the configured thresholds (warning 4.0 / critical 8.0 by default).
- `Config.from_yaml` test failed on Windows because `NamedTemporaryFile`
  cannot be reopened while the handle is open; tests now use pytest's
  `tmp_path`.
- CI previously masked all failures (`pytest ... || true`,
  `ruff check --exit-zero`) and never installed the package. The workflow
  now installs the package, lints, and runs tests with real exit codes, on
  Linux and Windows across Python 3.10-3.12.

### Changed
- SSH collector no longer auto-trusts unknown host keys
  (`paramiko.AutoAddPolicy`). Host keys are loaded from the user's
  `known_hosts` (plus an optional per-node `known_hosts` file) and unknown
  hosts are rejected. See the README section on SSH host key verification.
- Minimum supported Python is now 3.10 (the code uses PEP 604 union
  annotations evaluated at runtime, so 3.9 never actually worked).
- `requirements.txt` rebuilt to match the real imports; previously it
  listed unused packages (flask, requests, python-dotenv) and omitted
  actual dependencies (paramiko, fastapi, httpx, uvicorn, jinja2).

### Note on dates
- The 1.0.0 entry below was originally dated 2024-01-15. The project's
  first commit was 2026-02-19; the date has been corrected.

## [1.0.0] - 2026-02-19

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
