# Fruits Classifier Test Bench

## Repository overview

This repository contains a small test bench for building and running a fruit classifier system, plus tools for monitoring performance and running containerized modules.

Top-level folders:
- `camera-simulator/` - camera simulator module
- `classifier-server/` - classifier service module
- `classifier-training/` - model training utilities and dataset artifacts
- `metrics/` - performance monitoring utility for Linux processes
- `containers/` - Docker compose definitions and container entrypoints
- `bin/` - build output targets and generated binaries
- `dataset/` - sample training, validation, and test image datasets
- `build/` - CMake build artifacts and intermediate files

Each module has its own `README.md` with detailed usage and configuration instructions.

### General build instructions

From the repository root:

```bash
mkdir -p build
cd build
cmake -DRUNTIME_OUTPUT_DIRECTORY="${PWD}/bin" ..
cmake --build .
```

This generates binaries under `build/bin` and/or `bin`, depending on the module build configuration.

### General run guidance

- `config.sh` - configuration file with all needed paths and configurations
- `monitor.sh` - Script that runs the test bench according with configuration file.

### Notes

- The root README is intentionally high level and focuses on repository organization and main entry points.
- See each module's own README for full details on compilation, execution, and expected inputs.

## Test bench overview

### Hardware

A Raspberry Pi 4B with 2GB of RAM was used for testing

### OS

All tests were run on a customized DietPi (a Debian Trixie based) distro. UART and wifi options were disabled in DietPi installation process. All other OS configurations: packages removal, dependencies installations, etc. were done by `iso_config.sh`.