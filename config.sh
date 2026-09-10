#!/bin/bash

# Configuration for performance monitoring system
# Adjust these values as needed for your testing environment

# ============================================================================
# EXECUTION MODE
# ============================================================================
# Supported values: standalone, container, both
RUN_MODE="${RUN_MODE:-both}" 
COOLDOWN_TIME="${COOLDOWN_TIME:-300}"  # Cooldown time in seconds between runs

# ============================================================================
# DIRECTORIES & PATHS
# ============================================================================
# Resolve paths from the repository root so the monitor works regardless of
# the current working directory when it is launched.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

CLASSIFIER_BIN="${SCRIPT_DIR}/bin/classifier"
CAMERA_BIN="${SCRIPT_DIR}/bin/camera_simulator"
METRICS_BIN="${SCRIPT_DIR}/bin/metrics"
IMAGE_DATASET_PATH="${SCRIPT_DIR}/bin/dataset/test_mixed"  # Directory containing test images
LOGS_DIR="${SCRIPT_DIR}/logs"
CAMERA_METRICS_NAME="camera"
CLASSIFIER_METRICS_NAME="classifier"
DOCKERD_METRICS_NAME="dockerd"
CONTAINERD_METRICS_NAME="containerd"
SYSTEM_METRICS_NAME="system"
MONITOR_LOG="${LOGS_DIR}/monitor.log"
MODEL_PATH="${SCRIPT_DIR}/bin/model.tflite"

HOST_LOGS_DIR="${LOGS_DIR}"
HOST_MODEL_PATH="${MODEL_PATH}"
HOST_DATASET_PATH="${IMAGE_DATASET_PATH}"
CONTAINER_CLASSIFIER_LOG_DIR="/var/log/"
CONTAINER_CAMERA_LOG_DIR="/var/log/"
CONTAINER_MODEL_PATH="/app/model.tflite"
CONTAINER_DATASET_PATH="/data/test_mixed"

CONTAINER_COMPOSE_FILE="${SCRIPT_DIR}/containers/docker-compose.yaml"
CLASSIFIER_CONTAINER="tf_classifier"
CAMERA_CONTAINER="tf_camera"

# ============================================================================
# MONITORING PARAMETERS
# ============================================================================
RUN_COUNT="${RUN_COUNT:-10}"
SAMPLE_INTERVAL_MS=1000

# ============================================================================
# SERVER CONFIGURATION
# ============================================================================
SERVER_PORT=8000

# ============================================================================
# CAMERA CONFIGURATION
# ============================================================================
SEND_INTERVAL_MS=300  # Interval between sending images (in milliseconds)
SERVER_URL="http://localhost:${SERVER_PORT}/upload"
CONTAINER_SERVER_URL="http://classifier:${SERVER_PORT}/upload"

# ============================================================================
# PROCESS TRACKING
# ============================================================================
# PID files for process management
CLASSIFIER_PID_FILE="/tmp/classifier_${SERVER_PORT}.pid"
CAMERA_PID_FILE="/tmp/camera_simulator.pid"
