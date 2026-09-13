#!/usr/bin/env bash
# Poll a health endpoint until it responds or a timeout elapses.
# Usage: wait_for_health.sh <url> [timeout_seconds]
set -euo pipefail

url="${1:?usage: wait_for_health.sh <url> [timeout_seconds]}"
timeout_seconds="${2:-30}"

elapsed=0
until curl -fsS "$url" >/dev/null 2>&1; do
  if [ "$elapsed" -ge "$timeout_seconds" ]; then
    echo "Timed out waiting for $url after ${timeout_seconds}s" >&2
    exit 1
  fi
  sleep 1
  elapsed=$((elapsed + 1))
done

echo "$url is healthy"
