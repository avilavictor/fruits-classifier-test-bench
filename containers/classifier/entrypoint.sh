#!/bin/sh
set -e

LOG_DIR="${LOG_DIR:-/var/log/}"
MODEL_PATH="${MODEL_PATH:-/app/model.tflite}"
SERVER_PORT="${SERVER_PORT:-8000}"

mkdir -p "$LOG_DIR"

exec ./classifier "$LOG_DIR" "$MODEL_PATH" "$SERVER_PORT" > /dev/null 2>&1
