#!/bin/bash
# install_tflite.sh - Automação de Instalação TensorFlow Lite C API
# Criado para: Victor Avila (Debian / Raspberry Pi 4)

set -e

echo "-------------------------------------------------------"
echo " Iniciando Instalação do TensorFlow Lite C (v2.16.1) "
echo "-------------------------------------------------------"

# Diretório para armazenar o arquivo tar.gz
OUTPUT_DIR="$PWD/tflite-build"
mkdir -p "$OUTPUT_DIR"

# 1. Dependências
echo "[1/7] Instalando dependências do sistema..."
sudo apt update
sudo apt install -y cmake git build-essential python3-numpy python3-pip

# 2. Download e Checkout Estável
echo "[2/7] Preparando repositório TensorFlow..."
cd ~
if [ ! -d "tensorflow" ]; then
    git clone https://github.com/tensorflow/tensorflow.git
fi
cd tensorflow
git fetch --all --tags
git checkout v2.16.1
git submodule update --init --recursive

# 3. Configuração CMake
echo "[3/7] Configurando o CMake (Desativando XNNPACK/GPU)..."
cd tensorflow/lite/c
rm -rf build && mkdir build && cd build

# Desativamos MMAP e XNNPACK para evitar erros de declaração no Debian/ARM
cmake .. \
  -DTFLITE_ENABLE_XNNPACK=OFF \
  -DTFLITE_ENABLE_GPU=OFF \
  -DTFLITE_ENABLE_MMAP=OFF

# 4. Compilação
echo "[4/7] Compilando a biblioteca compartilhada..."
# Limitando a 2 núcleos para preservar a RAM de 2GB do RPi4
cmake --build . -j2

# 5. Instalação da Lib
echo "[5/7] Instalando libtensorflowlite_c.so em /usr/local/lib..."
sudo cp libtensorflowlite_c.so /usr/local/lib/
sudo ldconfig

# 6. Instalação dos Headers
echo "[6/7] Organizando cabeçalhos (.h) em /usr/local/include..."
sudo mkdir -p /usr/local/include/tensorflow/lite
cd ~/tensorflow
sudo cp tensorflow/lite/*.h /usr/local/include/tensorflow/lite/
sudo cp -r tensorflow/lite/c /usr/local/include/tensorflow/lite/
sudo cp -r tensorflow/lite/core /usr/local/include/tensorflow/lite/

# 7. Criando arquivo tar.gz com .so e headers
echo "[7/7] Criando arquivo tar.gz com a biblioteca e cabeçalhos..."
PACKAGE_DIR=$(mktemp -d)
mkdir -p "$PACKAGE_DIR/lib"
mkdir -p "$PACKAGE_DIR/include"

# Copiar a biblioteca compartilhada
cp ~/tensorflow/lite/c/build/libtensorflowlite_c.so "$PACKAGE_DIR/lib/"

# Copiar headers
cp -r /usr/local/include/tensorflow/lite "$PACKAGE_DIR/include/"

# Criar tar.gz
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
TARBALL="$OUTPUT_DIR/tflite_build_${TIMESTAMP}.tar.gz"
cd "$PACKAGE_DIR"
tar -czf "$TARBALL" lib/ include/

# Limpeza
rm -rf "$PACKAGE_DIR"

echo "✓ Arquivo tar.gz criado: $TARBALL"

echo "-------------------------------------------------------"
echo " INSTALAÇÃO CONCLUÍDA COM SUCESSO! "
echo "-------------------------------------------------------"