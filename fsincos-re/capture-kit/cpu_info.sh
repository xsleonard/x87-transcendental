#!/bin/sh
# collect CPU identification for the capture manifest
echo "=== date ==="; date -u
echo "=== uname ==="; uname -a
echo "=== cpuinfo (first cpu) ==="
awk '/^processor\s*:\s*1$/{exit} {print}' /proc/cpuinfo 2>/dev/null || sysctl -a 2>/dev/null | grep -i cpu | head -20
