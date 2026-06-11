#!/bin/bash
# cleanup-disk.sh - Auto-remediation script for high disk usage
# Environment variables provided by NHM:
#   NHM_NODE_NAME, NHM_NODE_HOST, NHM_DISK_PERCENT, NHM_ACTION

set -e

echo "🗑️ Running disk cleanup on ${NHM_NODE_NAME:-localhost}"
echo "   Current disk usage: ${NHM_DISK_PERCENT:-unknown}%"

# Clean package manager caches
if command -v apt-get &> /dev/null; then
    echo "Cleaning apt cache..."
    sudo apt-get clean
    sudo apt-get autoremove -y
fi

if command -v yum &> /dev/null; then
    echo "Cleaning yum cache..."
    sudo yum clean all
fi

if command -v brew &> /dev/null; then
    echo "Cleaning Homebrew cache..."
    brew cleanup -s
fi

# Clean old log files
echo "Removing old log files..."
find /var/log -type f -name "*.gz" -mtime +7 -delete 2>/dev/null || true
find /var/log -type f -name "*.old" -delete 2>/dev/null || true

# Clean journal logs (systemd)
if command -v journalctl &> /dev/null; then
    echo "Vacuuming journal..."
    sudo journalctl --vacuum-time=7d 2>/dev/null || true
fi

# Clean Docker (if running)
if command -v docker &> /dev/null && docker info &> /dev/null; then
    echo "Pruning Docker..."
    docker system prune -f --volumes 2>/dev/null || true
fi

# Clean temp files
echo "Cleaning temp files..."
find /tmp -type f -mtime +7 -delete 2>/dev/null || true
find /var/tmp -type f -mtime +7 -delete 2>/dev/null || true

# Report results
DISK_AFTER=$(df / | tail -1 | awk '{print $5}' | tr -d '%')
echo "✅ Disk cleanup completed"
echo "   Disk usage now: ${DISK_AFTER}%"
