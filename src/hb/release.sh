#!/bin/bash
set -e

SCRIPT_DIR=$(realpath "$(dirname "${BASH_SOURCE[0]}")")
BUILD_DIR="$SCRIPT_DIR/../../build"
OUT_DIR="$BUILD_DIR/hb"
DOCKER_IMG="hb-docker"

# Ensure Dockerfile exists
if [ ! -f "$SCRIPT_DIR/Dockerfile" ]; then
    echo "Error: Dockerfile not found in $DOCKERFILE_PATH"
    return 1
fi

# Prepare output directory
echo "Preparing output directory: $OUT_DIR"
rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR/hb"

# Build Docker image
echo "Building Docker image: $DOCKER_IMG"
docker build -t "$DOCKER_IMG" "$SCRIPT_DIR"

# Run Docker container
echo "Running Docker container: $DOCKER_IMG"
docker stop "$DOCKER_IMG" > /dev/null 2>&1 || true
docker run --rm -d --name "$DOCKER_IMG" "$DOCKER_IMG" sleep 3600

# Copy files from container
echo "Copying /release from container to: $OUT_DIR"
docker cp "$DOCKER_IMG:/release/." "$OUT_DIR/"

# Cleanup
echo "Cleaning up..."
docker stop "$DOCKER_IMG" > /dev/null 2>&1 || true

echo "Done! The /release folder has been copied to $OUT_DIR"
