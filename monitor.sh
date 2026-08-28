#!/bin/bash

set -e

# Load configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.sh"

RUN_MODE="${RUN_MODE:-standalone}"
RUN_COUNT="${RUN_COUNT:-1}"
CURRENT_MODE="$RUN_MODE"
MONITOR_LOG="${LOGS_DIR}/monitor.log"

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

backup_and_clear_logs() {
    mkdir -p "$LOGS_DIR"

    if [ -z "$(find "$LOGS_DIR" -mindepth 1 2>/dev/null | head -n 1)" ]; then
        log_info "No existing logs to backup in $LOGS_DIR"
        return 0
    fi

    local timestamp backup_file backup_dir
    timestamp="$(date '+%Y%m%d_%H%M%S')"
    backup_dir="$(dirname "$LOGS_DIR")"
    backup_file="${backup_dir}/backup_${timestamp}.tar.xz"

    log_info "Backing up existing logs from $LOGS_DIR to $backup_file"
    # Create the archive outside of $LOGS_DIR to avoid tar reading a file that's being written
    tar -C "$LOGS_DIR" -cJf "$backup_file" .

    # Remove everything under LOGS_DIR after backup
    find "$LOGS_DIR" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
    log_info "Cleaned existing logs from $LOGS_DIR"
}

stop_docker_runtime() {
    if [ "$CURRENT_MODE" != "standalone" ]; then
        return 0
    fi

    if ! command -v systemctl > /dev/null 2>&1; then
        return 0
    fi

    for svc in docker.service containerd.service; do
        if systemctl is-active --quiet "$svc" 2>/dev/null; then
            log_info "Stopping $svc for standalone mode..."
            systemctl stop "$svc" 2>/dev/null || true
        fi
    done
}

stop_services() {
    if [ "$CURRENT_MODE" = "container" ]; then
        if [ -f "$CLASSIFIER_PID_FILE" ] || [ -f "$CAMERA_PID_FILE" ]; then
            docker compose -f "$CONTAINER_COMPOSE_FILE" down 2>/dev/null || true
        fi
    else
        if [ -n "${CLASSIFIER_PID:-}" ] && ps -p "$CLASSIFIER_PID" > /dev/null 2>&1; then
            log_info "Stopping classifier (PID: $CLASSIFIER_PID)..."
            kill -TERM "$CLASSIFIER_PID" 2>/dev/null || true
            sleep 1
            if ps -p "$CLASSIFIER_PID" > /dev/null 2>&1; then
                kill -9 "$CLASSIFIER_PID" 2>/dev/null || true
            fi
        fi

        if [ -n "${CAMERA_PID:-}" ] && ps -p "$CAMERA_PID" > /dev/null 2>&1; then
            log_info "Stopping camera simulator (PID: $CAMERA_PID)..."
            kill -TERM "$CAMERA_PID" 2>/dev/null || true
            sleep 1
            if ps -p "$CAMERA_PID" > /dev/null 2>&1; then
                kill -9 "$CAMERA_PID" 2>/dev/null || true
            fi
        fi

        stop_docker_runtime
    fi

    for pid_var in SYSTEM_SAMPLER_PID CLS_SAMPLER_PID CAM_SAMPLER_PID CLS2_SAMPLER_PID CAM2_SAMPLER_PID DOCKERD_SAMPLER_PID CONTAINERD_SAMPLER_PID; do
        eval "pid_value=\${${pid_var}:-}"
        if [ -n "$pid_value" ] && ps -p "$pid_value" > /dev/null 2>&1; then
            kill -TERM "$pid_value" 2>/dev/null || true
            wait "$pid_value" 2>/dev/null || true
        fi
    done

    rm -f "$CLASSIFIER_PID_FILE" "$CAMERA_PID_FILE"
    unset SYSTEM_SAMPLER_PID CLASSIFIER_PID CAMERA_PID CLS_SAMPLER_PID CAM_SAMPLER_PID CLS2_SAMPLER_PID CAM2_SAMPLER_PID DOCKERD_SAMPLER_PID CONTAINERD_SAMPLER_PID
}

cleanup() {
    log_info "Cleaning up..."
    stop_services
    log_info "Cleanup complete"
}

trap cleanup EXIT INT TERM

check_prerequisites() {
    log_info "Running pre-flight checks..."

    if [ "$CURRENT_MODE" = "standalone" ]; then
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

start_services() {
    local RUN_DIR="$1"

    export HOST_LOGS_DIR="$RUN_DIR"
    export HOST_MODEL_PATH="$MODEL_PATH"
    export HOST_DATASET_PATH="$IMAGE_DATASET_PATH"
    export CONTAINER_CLASSIFIER_LOG_DIR="/var/log/"
    export CONTAINER_CAMERA_LOG_DIR="/var/log/"
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

    if [ "$CURRENT_MODE" = "standalone" ]; then
        log_info "Starting standalone services"
        stop_docker_runtime
        cd "$SCRIPT_DIR"

        "$METRICS_BIN" 0 "$SAMPLE_INTERVAL_MS" "$SYSTEM_METRICS_NAME" "$RUN_DIR" > /dev/null 2>&1 &
        SYSTEM_SAMPLER_PID=$!
        log_info "System metrics started (PID: $SYSTEM_SAMPLER_PID)"

        "$CLASSIFIER_BIN" "$RUN_DIR" "$MODEL_PATH" "$SERVER_PORT" > /dev/null 2>&1 &
        CLASSIFIER_PID=$!
        echo "$CLASSIFIER_PID" > "$CLASSIFIER_PID_FILE"
        log_info "Classifier started (PID: $CLASSIFIER_PID)"

        "$METRICS_BIN" "$CLASSIFIER_PID" "$SAMPLE_INTERVAL_MS" "$CLASSIFIER_METRICS_NAME" "$RUN_DIR" > /dev/null 2>&1 &
        CLS_SAMPLER_PID=$!
        log_info "Classifier metrics started (PID: $CLS_SAMPLER_PID)"

        "$CAMERA_BIN" "$IMAGE_DATASET_PATH" "$SERVER_URL" "$SEND_INTERVAL_MS" "$RUN_DIR" > /dev/null 2>&1 &
        CAMERA_PID=$!
        echo "$CAMERA_PID" > "$CAMERA_PID_FILE"
        log_info "Camera simulator started (PID: $CAMERA_PID)"

        "$METRICS_BIN" "$CAMERA_PID" "$SAMPLE_INTERVAL_MS" "$CAMERA_METRICS_NAME" "$RUN_DIR" > /dev/null 2>&1 &
        CAM_SAMPLER_PID=$!
        log_info "Camera metrics started (PID: $CAM_SAMPLER_PID)"

    else
        log_info "Starting containerized services"
        cd "$SCRIPT_DIR"

        "$METRICS_BIN" 0 "$SAMPLE_INTERVAL_MS" "$SYSTEM_METRICS_NAME" "$RUN_DIR" > /dev/null 2>&1 &
        SYSTEM_SAMPLER_PID=$!
        log_info "System metrics started (PID: $SYSTEM_SAMPLER_PID)"        

        docker compose -f "$CONTAINER_COMPOSE_FILE" up --build -d

        CLASSIFIER_PID=$(docker inspect --format '{{.State.Pid}}' "$CLASSIFIER_CONTAINER" 2>/dev/null || true)
        CAMERA_PID=$(docker inspect --format '{{.State.Pid}}' "$CAMERA_CONTAINER" 2>/dev/null || true)

        echo "$CLASSIFIER_PID" > "$CLASSIFIER_PID_FILE"
        echo "$CAMERA_PID" > "$CAMERA_PID_FILE"
        log_info "Classifier container PID: $CLASSIFIER_PID"
        log_info "Camera container PID: $CAMERA_PID"

        if [ -n "$CLASSIFIER_PID" ]; then
            "$METRICS_BIN" "$CLASSIFIER_PID" "$SAMPLE_INTERVAL_MS" "$CLASSIFIER_METRICS_NAME" "$RUN_DIR" > /dev/null 2>&1 &
            CLS_SAMPLER_PID=$!
            log_info "Classifier container metrics started (PID: $CLS_SAMPLER_PID)"

            CLS_SHIM_PID=$(ps -o ppid= -p "$CLASSIFIER_PID" | tr -d ' ')
            CLS_SHIM_METRICS_NAME="$CLASSIFIER_METRICS_NAME"_shim
            "$METRICS_BIN" "$CLS_SHIM_PID" "$SAMPLE_INTERVAL_MS" "$CLS_SHIM_METRICS_NAME" "$RUN_DIR" > /dev/null 2>&1 &
            CLS2_SAMPLER_PID=$!
            log_info "Classifier shim metrics started (PID: $CLS2_SAMPLER_PID)"
        fi
        if [ -n "$CAMERA_PID" ]; then
            "$METRICS_BIN" "$CAMERA_PID" "$SAMPLE_INTERVAL_MS" "$CAMERA_METRICS_NAME" "$RUN_DIR" > /dev/null 2>&1 &
            CAM_SAMPLER_PID=$!
            log_info "Camera container metrics started (PID: $CAM_SAMPLER_PID)"

            CAM_SHIM_PID=$(ps -o ppid= -p "$CAMERA_PID" | tr -d ' ')
            CAM_SHIM_METRICS_NAME="$CAMERA_METRICS_NAME"_shim
            "$METRICS_BIN" "$CAM_SHIM_PID" "$SAMPLE_INTERVAL_MS" "$CAM_SHIM_METRICS_NAME" "$RUN_DIR" > /dev/null 2>&1 &
            CAM2_SAMPLER_PID=$!
            log_info "Camera shim metrics started (PID: $CAM2_SAMPLER_PID)"
        fi

        DOCKERD_PID=$(systemctl show -p MainPID --value "docker.service")
        if [ -n "$DOCKERD_PID" ]; then
            "$METRICS_BIN" "$DOCKERD_PID" "$SAMPLE_INTERVAL_MS" "$DOCKERD_METRICS_NAME" "$RUN_DIR" > /dev/null 2>&1 &
            DOCKERD_SAMPLER_PID=$!
            log_info "Dockerd metrics started (PID: $DOCKERD_PID, Sampler: $DOCKERD_SAMPLER_PID)"
        fi

        CONTAINERD_PID=$(systemctl show -p MainPID --value "containerd.service")
        if [ -n "$CONTAINERD_PID" ]; then
            "$METRICS_BIN" "$CONTAINERD_PID" "$SAMPLE_INTERVAL_MS" "$CONTAINERD_METRICS_NAME" "$RUN_DIR" > /dev/null 2>&1 &
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
}

wait_for_camera_completion() {
    if [ "$CURRENT_MODE" = "standalone" ]; then
        if wait "$CAMERA_PID" 2>/dev/null; then
            log_info "Camera simulator completed successfully"
        else
            exit_code=$?
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
}

main() {
    if ! [[ "$RUN_COUNT" =~ ^[1-9][0-9]*$ ]]; then
        log_error "RUN_COUNT must be a positive integer; defaulting to 1"
        RUN_COUNT=1
    fi

    if [[ "$RUN_MODE" != "standalone" && "$RUN_MODE" != "container" && "$RUN_MODE" != "both" ]]; then
        log_warn "Unsupported RUN_MODE '$RUN_MODE'; defaulting to standalone"
        RUN_MODE="standalone"
    fi

    backup_and_clear_logs

    if [ "$RUN_MODE" = "both" ]; then
        TOTAL_RUNS=$((RUN_COUNT * 2))
    else
        TOTAL_RUNS=$RUN_COUNT
    fi

    for RUN_INDEX in $(seq 1 "$TOTAL_RUNS"); do
        if [ "$RUN_MODE" = "both" ]; then
            if [ "$RUN_INDEX" -le "$RUN_COUNT" ]; then
                CURRENT_MODE="standalone"
                MODE_RUN_INDEX="$RUN_INDEX"
            else
                CURRENT_MODE="container"
                MODE_RUN_INDEX="$((RUN_INDEX - RUN_COUNT))"
            fi
        else
            CURRENT_MODE="$RUN_MODE"
            MODE_RUN_INDEX="$RUN_INDEX"
        fi

        BASE_LOGS_DIR="${LOGS_DIR}/${CURRENT_MODE}"
        RUN_LOGS_DIR="${BASE_LOGS_DIR}/run_${MODE_RUN_INDEX}"
        mkdir -p "$RUN_LOGS_DIR"
        MONITOR_LOG="${RUN_LOGS_DIR}/monitor.log"
        : > "$MONITOR_LOG"

        log_info "=========================================="
        log_info "Performance Monitoring System"
        log_info "RUN_MODE=$CURRENT_MODE"
        log_info "RUN=${MODE_RUN_INDEX}/${RUN_COUNT}"
        log_info "LOG_DIR=${RUN_LOGS_DIR}"
        log_info "=========================================="

        check_prerequisites
        start_services "$RUN_LOGS_DIR"
        wait_for_camera_completion
        stop_services

        log_info "=========================================="
        log_info "Run ${MODE_RUN_INDEX}/${RUN_COUNT} complete for ${CURRENT_MODE} - logs stored in ${RUN_LOGS_DIR}"
        log_info "=========================================="

        if [ "$RUN_INDEX" -lt "$TOTAL_RUNS" ]; then
            log_info "Cleaning system caches before next run..."
            if [ -w /proc/sys/vm/drop_caches ]; then
                sync
                echo 3 > /proc/sys/vm/drop_caches
                log_info "System page cache, dentries, and inodes dropped"
            else
                log_warn "/proc/sys/vm/drop_caches is not writable; cache cleanup skipped"
            fi

            log_info "Cooling down for 5 minutes before next run..."
            sleep 300
        fi
    done

    log_info "=========================================="
    log_info "All ${RUN_COUNT} runs completed"
    log_info "Logs stored under ${BASE_LOGS_DIR}"
    log_info "=========================================="
}

main "$@"
