#!/bin/bash

set -e

# Load configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.sh"

log_info() {
    local msg="$1"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] $msg" >> "$MONITOR_LOG"
}

log_warn() {
    local msg="$1"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [WARN] $msg" >> "$MONITOR_LOG"
}

log_error() {
    local msg="$1"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] $msg" | tee -a "$MONITOR_LOG" >&2
}

cleanup() {
    log_info "Cleaning up..."

    if [ "$RUN_MODE" = "container" ]; then
        if [ -f "$CLASSIFIER_PID_FILE" ] || [ -f "$CAMERA_PID_FILE" ]; then
            docker compose -f "$CONTAINER_COMPOSE_FILE" down 2>/dev/null || true
        fi
    else
        if [ -f "$CLASSIFIER_PID_FILE" ]; then
            CLASSIFIER_PID=$(cat "$CLASSIFIER_PID_FILE")
            if ps -p "$CLASSIFIER_PID" > /dev/null 2>&1; then
                log_info "Stopping classifier (PID: $CLASSIFIER_PID)..."
                kill -TERM "$CLASSIFIER_PID" 2>/dev/null || true
                sleep 1
                if ps -p "$CLASSIFIER_PID" > /dev/null 2>&1; then
                    kill -9 "$CLASSIFIER_PID" 2>/dev/null || true
                fi
            fi
            rm -f "$CLASSIFIER_PID_FILE"
        fi

        if [ -f "$CAMERA_PID_FILE" ]; then
            CAMERA_PID=$(cat "$CAMERA_PID_FILE")
            if ps -p "$CAMERA_PID" > /dev/null 2>&1; then
                log_info "Stopping camera simulator (PID: $CAMERA_PID)..."
                kill -TERM "$CAMERA_PID" 2>/dev/null || true
                sleep 1
                if ps -p "$CAMERA_PID" > /dev/null 2>&1; then
                    kill -9 "$CAMERA_PID" 2>/dev/null || true
                fi
            fi
            rm -f "$CAMERA_PID_FILE"
        fi
    fi

    if [ -n "$CLS_SAMPLER_PID" ] && ps -p "$CLS_SAMPLER_PID" > /dev/null 2>&1; then
        kill -TERM "$CLS_SAMPLER_PID" 2>/dev/null || true
    fi
    if [ -n "$CAM_SAMPLER_PID" ] && ps -p "$CAM_SAMPLER_PID" > /dev/null 2>&1; then
        kill -TERM "$CAM_SAMPLER_PID" 2>/dev/null || true
    fi

    log_info "Cleanup complete"
}

trap cleanup EXIT INT TERM

check_prerequisites() {
    log_info "Running pre-flight checks..."

    if [ "$RUN_MODE" = "standalone" ]; then
        if [ ! -f "$CLASSIFIER_BIN" ]; then
            log_error "Classifier binary not found: $CLASSIFIER_BIN"
            exit 1
        fi
        if [ ! -f "$CAMERA_BIN" ]; then
            log_error "Camera simulator binary not found: $CAMERA_BIN"
            exit 1
        fi
        if [ ! -d "$IMAGE_DATASET_PATH" ]; then
            log_error "Image dataset directory not found: $IMAGE_DATASET_PATH"
            exit 1
        fi
    else
        if [ ! -f "$CONTAINER_COMPOSE_FILE" ]; then
            log_error "Container compose file not found: $CONTAINER_COMPOSE_FILE"
            exit 1
        fi
        if ! command -v docker &> /dev/null; then
            log_error "Docker is required for container mode"
            exit 1
        fi
        if ! docker compose version > /dev/null 2>&1; then
            log_error "Docker Compose plugin is required for container mode"
            exit 1
        fi
    fi

    for cmd in ps awk grep sed wc; do
        if ! command -v "$cmd" &> /dev/null; then
            log_error "Required command not found: $cmd"
            exit 1
        fi
    done

    log_info "Pre-flight checks passed"
}

main() {
    mkdir -p "$LOGS_DIR"

    log_info "=========================================="
    log_info "Performance Monitoring System"
    log_info "RUN_MODE=$RUN_MODE"
    log_info "=========================================="

    > "$MONITOR_LOG"
    check_prerequisites

    export HOST_LOGS_DIR="$LOGS_DIR"
    export HOST_MODEL_PATH="$MODEL_PATH"
    export HOST_DATASET_PATH="$IMAGE_DATASET_PATH"
    export CONTAINER_CLASSIFIER_LOG_DIR="$CONTAINER_CLASSIFIER_LOG_DIR"
    export CONTAINER_CAMERA_LOG_DIR="$CONTAINER_CAMERA_LOG_DIR"
    export CONTAINER_MODEL_PATH="$CONTAINER_MODEL_PATH"
    export CONTAINER_DATASET_PATH="$CONTAINER_DATASET_PATH"
    export CONTAINER_SERVER_URL="$CONTAINER_SERVER_URL"
    export SERVER_PORT="$SERVER_PORT"
    export SEND_INTERVAL_MS="$SEND_INTERVAL_MS"

    log_info "Configuration loaded:"
    log_info "  - Classifier: $CLASSIFIER_BIN"
    log_info "  - Camera Simulator: $CAMERA_BIN"
    log_info "  - Image Dataset: $IMAGE_DATASET_PATH"
    log_info "  - Sample Interval: ${SAMPLE_INTERVAL_MS}ms"
    log_info "  - Camera Stats: $CAMERA_METRICS_NAME"
    log_info "  - Classifier Stats: $CLASSIFIER_METRICS_NAME"

    if [ "$RUN_MODE" = "standalone" ]; then
        log_info "Starting standalone services"
        cd "$SCRIPT_DIR"

        "$CLASSIFIER_BIN" "$LOGS_DIR" "$MODEL_PATH" "$SERVER_PORT" > /dev/null 2>&1 &
        CLASSIFIER_PID=$!
        echo "$CLASSIFIER_PID" > "$CLASSIFIER_PID_FILE"
        log_info "Classifier started (PID: $CLASSIFIER_PID)"

        "$METRICS_BIN" "$CLASSIFIER_PID" "$SAMPLE_INTERVAL_MS" "$CLASSIFIER_METRICS_NAME" "$LOGS_DIR" > /dev/null 2>&1 &
        CLS_SAMPLER_PID=$!
        log_info "Classifier metrics started (PID: $CLS_SAMPLER_PID)"

        "$CAMERA_BIN" "$IMAGE_DATASET_PATH" "$SERVER_URL" "$SEND_INTERVAL_MS" "$LOGS_DIR" > /dev/null 2>&1 &
        CAMERA_PID=$!
        echo "$CAMERA_PID" > "$CAMERA_PID_FILE"
        log_info "Camera simulator started (PID: $CAMERA_PID)"

        "$METRICS_BIN" "$CAMERA_PID" "$SAMPLE_INTERVAL_MS" "$CAMERA_METRICS_NAME" "$LOGS_DIR" > /dev/null 2>&1 &
        CAM_SAMPLER_PID=$!
        log_info "Camera metrics started (PID: $CAM_SAMPLER_PID)"
    else
        log_info "Starting containerized services"
        cd "$SCRIPT_DIR"

        docker compose -f "$CONTAINER_COMPOSE_FILE" up --build -d

        CLASSIFIER_PID=$(docker inspect --format '{{.State.Pid}}' "$CLASSIFIER_CONTAINER" 2>/dev/null || true)
        CAMERA_PID=$(docker inspect --format '{{.State.Pid}}' "$CAMERA_CONTAINER" 2>/dev/null || true)

        echo "$CLASSIFIER_PID" > "$CLASSIFIER_PID_FILE"
        echo "$CAMERA_PID" > "$CAMERA_PID_FILE"
        log_info "Classifier container PID: $CLASSIFIER_PID"
        log_info "Camera container PID: $CAMERA_PID"

        if [ -n "$CLASSIFIER_PID" ]; then
            "$METRICS_BIN" "$CLASSIFIER_PID" "$SAMPLE_INTERVAL_MS" "$CLASSIFIER_METRICS_NAME" "$LOGS_DIR" > /dev/null 2>&1 &
            CLS_SAMPLER_PID=$!
            log_info "Classifier container metrics started (PID: $CLS_SAMPLER_PID)"

            CLS_SHIM_PID=$(ps -o ppid= -p "$CLASSIFIER_PID" | tr -d ' ')
            CLS_SHIM_METRICS_NAME="$CLASSIFIER_METRICS_NAME"_shim
            "$METRICS_BIN" "$CLS_SHIM_PID" "$SAMPLE_INTERVAL_MS" "$CLS_SHIM_METRICS_NAME" "$LOGS_DIR" > /dev/null 2>&1 &
            CLS2_SAMPLER_PID=$!
            log_info "Classifier shim metrics started (PID: $CLS2_SAMPLER_PID)"
        fi
        if [ -n "$CAMERA_PID" ]; then
            "$METRICS_BIN" "$CAMERA_PID" "$SAMPLE_INTERVAL_MS" "$CAMERA_METRICS_NAME" "$LOGS_DIR" > /dev/null 2>&1 &
            CAM_SAMPLER_PID=$!
            log_info "Camera container metrics started (PID: $CAM_SAMPLER_PID)"

            CAM_SHIM_PID=$(ps -o ppid= -p "$CAMERA_PID" | tr -d ' ')
            CAM_SHIM_METRICS_NAME="$CAMERA_METRICS_NAME"_shim
            "$METRICS_BIN" "$CAM_SHIM_PID" "$SAMPLE_INTERVAL_MS" "$CAM_SHIM_METRICS_NAME" "$LOGS_DIR" > /dev/null 2>&1 &
            CAM2_SAMPLER_PID=$!
            log_info "Camera shim metrics started (PID: $CAM2_SAMPLER_PID)"
        fi

        DOCKERD_PID=$(systemctl show -p MainPID --value "docker.service")
        if [ -n "$DOCKERD_PID" ]; then
            "$METRICS_BIN" "$DOCKERD_PID" "$SAMPLE_INTERVAL_MS" "$DOCKERD_METRICS_NAME" "$LOGS_DIR" > /dev/null 2>&1 &
            DOCKERD_SAMPLER_PID=$!
            log_info "Dockerd metrics started (PID: $DOCKERD_PID, Sampler: $DOCKERD_SAMPLER_PID)"
        fi

        CONTAINERD_PID=$(systemctl show -p MainPID --value "containerd.service")
        if [ -n "$CONTAINERD_PID" ]; then
            "$METRICS_BIN" "$CONTAINERD_PID" "$SAMPLE_INTERVAL_MS" "$CONTAINERD_METRICS_NAME" "$LOGS_DIR" > /dev/null 2>&1 &
            CONTAINERD_SAMPLER_PID=$!
            log_info "Containerd metrics started (PID: $CONTAINERD_PID, Sampler: $CONTAINERD_SAMPLER_PID)"
        fi
    fi

    log_info "=========================================="
    log_info "System running - monitoring in progress"
    log_info "Classifier PID: $CLASSIFIER_PID"
    log_info "Classifier Metrics PID: $CLS_SAMPLER_PID"
    log_info "Camera PID: $CAMERA_PID"
    log_info "Camera Metrics PID: $CAM_SAMPLER_PID"
    log_info "=========================================="

    if [ "$RUN_MODE" = "standalone" ]; then
        if wait "$CAMERA_PID" 2>/dev/null; then
            log_info "Camera simulator completed successfully"
        else
            local exit_code=$?
            log_warn "Camera simulator exited with code: $exit_code"
        fi
    else
        while [ "$(docker inspect -f '{{.State.Running}}' "$CAMERA_CONTAINER" 2>/dev/null)" = "true" ]; do
            sleep 1
        done
        CAMERA_EXIT_CODE=$(docker inspect -f '{{.State.ExitCode}}' "$CAMERA_CONTAINER" 2>/dev/null || true)
        if [ "$CAMERA_EXIT_CODE" = "0" ]; then
            log_info "Camera container completed successfully"
        else
            log_warn "Camera container exited with code: $CAMERA_EXIT_CODE"
        fi
    fi

    log_info "Waiting 5s for classifier to finish processing..."
    sleep 5

    if [ -n "$CLS_SAMPLER_PID" ] && ps -p "$CLS_SAMPLER_PID" > /dev/null 2>&1; then
        kill -TERM "$CLS_SAMPLER_PID" 2>/dev/null || true
        wait "$CLS_SAMPLER_PID" 2>/dev/null || true
    fi
    if [ -n "$CAM_SAMPLER_PID" ] && ps -p "$CAM_SAMPLER_PID" > /dev/null 2>&1; then
        kill -TERM "$CAM_SAMPLER_PID" 2>/dev/null || true
        wait "$CAM_SAMPLER_PID" 2>/dev/null || true
    fi

    if [ "$RUN_MODE" = "standalone" ]; then
        if [ -f "$CLASSIFIER_PID_FILE" ]; then
            CLASSIFIER_PID=$(cat "$CLASSIFIER_PID_FILE")
            if ps -p "$CLASSIFIER_PID" > /dev/null 2>&1; then
                log_info "Stopping classifier (PID: $CLASSIFIER_PID)..."
                kill -TERM "$CLASSIFIER_PID" 2>/dev/null || true
                sleep 2
                if ps -p "$CLASSIFIER_PID" > /dev/null 2>&1; then
                    kill -9 "$CLASSIFIER_PID" 2>/dev/null || true
                fi
            fi
        fi
    else
        docker compose -f "$CONTAINER_COMPOSE_FILE" down 2>/dev/null || true
    fi

    log_info "=========================================="
    log_info "Test complete - Processing logs..."
    log_info "=========================================="
}

main "$@"
