# Security Policy

## Supported versions

Only the latest release receives security fixes.

## Reporting a vulnerability

Use GitHub's private vulnerability reporting (Security tab > "Report a
vulnerability") on this repository. Include reproduction steps and an
assessment of impact.

## Deployment notes

- The SSH collector rejects unknown host keys. Keep your `known_hosts`
  current rather than disabling verification.
- Remediation hooks run on the monitoring host with the monitor's
  privileges. Treat the config file and scripts directory as trusted input
  and restrict write access to both.
- Notifier credentials (bot tokens, webhook URLs) live in the config file;
  restrict read access accordingly.
