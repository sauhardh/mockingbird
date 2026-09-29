#!/usr/bin/env bash
set -e

# Change directory to project root
cd "$(dirname "$0")"

# Execute unified runner
exec python3 run.py "$@"
