#!/bin/bash
# install_tflite.sh - Minimal TensorFlow Lite C API install for Raspberry Pi
# Builds and installs only the runtime library and the headers needed by classifier-server/classifier.c.

set -euo pipefail

TF_VERSION="${1:-2.16.1}"
OUTPUT_DIR="$PWD/tflite-build"
mkdir -p "$OUTPUT_DIR"

echo "-------------------------------------------------------"
echo " Starting TensorFlow Lite C install: v$TF_VERSION "
echo "-------------------------------------------------------"

echo "[1/7] Installing minimal system dependencies..."
sudo apt update
sudo apt install -y cmake git build-essential python3 wget tar

WORKDIR="$(mktemp -d)"
echo "[2/7] Using temporary workspace: $WORKDIR"
cd "$WORKDIR"

echo "[3/7] Cloning TensorFlow $TF_VERSION source..."
git clone --depth 1 --branch "v$TF_VERSION" https://github.com/tensorflow/tensorflow.git tensorflow-src
LITE_SOURCE_DIR="$WORKDIR/tensorflow-src/tensorflow/lite"
cd "$LITE_SOURCE_DIR/c"

echo "[4/7] Configuring the TensorFlow Lite C build..."
rm -rf build && mkdir build && cd build
cmake .. \
  -DCMAKE_BUILD_TYPE=Release \
  -DTFLITE_ENABLE_XNNPACK=OFF \
  -DTFLITE_ENABLE_GPU=OFF \
  -DTFLITE_ENABLE_MMAP=OFF

echo "[5/7] Building TensorFlow Lite C runtime (single job for low-memory Pi)..."
cmake --build . --target tensorflowlite_c -- -j1

echo "[6/7] Installing runtime library and headers..."
sudo mkdir -p /usr/local/lib
sudo mkdir -p /usr/local/include/tensorflow/lite
sudo cp libtensorflowlite_c.so /usr/local/lib/
sudo cp -r "$LITE_SOURCE_DIR"/. /usr/local/include/tensorflow/lite/
sudo ldconfig

echo "[7/7] Packaging runtime and full headers..."
PACKAGE_DIR="$(mktemp -d)"
mkdir -p "$PACKAGE_DIR/lib"
mkdir -p "$PACKAGE_DIR/include/tensorflow/lite"
cp libtensorflowlite_c.so "$PACKAGE_DIR/lib/"
cp -r "$LITE_SOURCE_DIR"/. "$PACKAGE_DIR/include/tensorflow/lite/"

TARBALL="$OUTPUT_DIR/tflite_build_${TF_VERSION}_$(date +%Y%m%d_%H%M%S).tar.gz"
cd "$PACKAGE_DIR"
tar -czf "$TARBALL" lib include
rm -rf "$PACKAGE_DIR"
rm -rf "$WORKDIR"

echo "✓ Created package: $TARBALL"
echo "-------------------------------------------------------"
echo " TensorFlow Lite C install completed successfully. "
echo "-------------------------------------------------------"
