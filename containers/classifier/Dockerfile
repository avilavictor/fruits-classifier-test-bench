# ==========================================
# Runtime image for classifier service
# ==========================================
FROM debian:13-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libmicrohttpd12 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY ./bin/classifier ./classifier
COPY ./bin/model.tflite ./model.tflite
COPY ./bin/libtensorflowlite_c.so /usr/local/lib/

RUN ldconfig

ENV LOG_DIR=/var/log/
ENV MODEL_PATH=/app/model.tflite
ENV SERVER_PORT=8000

RUN chmod +x /app/classifier && mkdir -p "$LOG_DIR"

COPY containers/classifier/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
