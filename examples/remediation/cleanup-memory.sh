#!/bin/bash
# cleanup-memory.sh - Auto-remediation script for high memory usage
# Environment variables provided by NHM:
#   NHM_NODE_NAME, NHM_NODE_HOST, NHM_MEMORY_PERCENT, NHM_ACTION

set -e

echo "🧹 Running memory cleanup on ${NHM_NODE_NAME:-localhost}"
echo "   Current memory usage: ${NHM_MEMORY_PERCENT:-unknown}%"

# Clear system caches (Linux)
if [[ "$(uname)" == "Linux" ]]; then
    echo "Clearing page cache, dentries and inodes..."
    sync
    echo 3 > /proc/sys/vm/drop_caches 2>/dev/null || true
fi

# Clear macOS caches
if [[ "$(uname)" == "Darwin" ]]; then
    echo "Purging macOS memory..."
    sudo purge 2>/dev/null || true
fi

# Kill processes that commonly leak memory
echo "Checking for runaway processes..."

# Example: Restart PHP-FPM if it's using too much memory
if pgrep -x php-fpm > /dev/null; then
    PHP_MEM=$(ps -o rss= -p $(pgrep -x php-fpm | head -1) 2>/dev/null | awk '{print int($1/1024)}')
    if [[ "${PHP_MEM:-0}" -gt 2048 ]]; then
        echo "PHP-FPM using ${PHP_MEM}MB, restarting..."
        sudo systemctl restart php-fpm 2>/dev/null || true
    fi
fi

echo "✅ Memory cleanup completed"
