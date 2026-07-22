# ==========================================
# Runtime image for camera simulator service
# ==========================================
FROM debian:13-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libcurl4 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY ./bin/camera_simulator ./camera_simulator

ENV LOG_DIR=/var/log/
ENV IMAGE_DATASET_PATH=/data/test_mixed
ENV SERVER_URL=http://classifier:8000/upload
ENV SEND_INTERVAL_MS=200

RUN chmod +x /app/camera_simulator && mkdir -p "$LOG_DIR"

COPY containers/camera/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
