#!/bin/sh
set -e

LOG_DIR="${LOG_DIR:-/var/log/}"
IMAGE_DATASET_PATH="${IMAGE_DATASET_PATH:-/data/test_mixed}"
SERVER_URL="${SERVER_URL:-http://classifier:8000/upload}"
SEND_INTERVAL_MS="${SEND_INTERVAL_MS:-200}"

mkdir -p "$LOG_DIR"
exec ./camera_simulator "$IMAGE_DATASET_PATH" "$SERVER_URL" "$SEND_INTERVAL_MS" "$LOG_DIR" > /dev/null 2>&1
