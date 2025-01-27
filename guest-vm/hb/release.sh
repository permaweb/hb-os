#!/bin/bash
set -e

# Function to build and copy /opt/hb from Docker container to host
build_and_copy_hb() {
    # Default variables
    local SCRIPT_DIR=$(realpath "$(dirname "${BASH_SOURCE[0]}")")
    local BUILD_DIR="$SCRIPT_DIR/../../build"
    local OUT_DIR="$BUILD_DIR/hb"
    local DOCKER_IMG="hb-docker"
    local DOCKER_CONTAINER="hb-container"
    local DOCKERFILE_PATH="$SCRIPT_DIR"

    # Parse arguments
    while [ $# -gt 0 ]; do
        case "$1" in
            -dockerfile-dir)
                DOCKERFILE_PATH="$2"
                shift
                ;;
            -out-dir)
                OUT_DIR="$2"
                shift
                ;;
            *)
                echo "Usage: build_and_copy_hb [-dockerfile-dir <path>] [-out-dir <path>]"
                return 1
                ;;
        esac
        shift
    done

    # Ensure Dockerfile exists
    if [ ! -f "$DOCKERFILE_PATH/Dockerfile" ]; then
        echo "Error: Dockerfile not found in $DOCKERFILE_PATH"
        return 1
    fi

    # Prepare output directory
    echo "Preparing output directory: $OUT_DIR"
    rm -rf "$OUT_DIR"
    mkdir -p "$OUT_DIR"

    # Build Docker image
    echo "Building Docker image: $DOCKER_IMG"
    docker build -t "$DOCKER_IMG" "$DOCKERFILE_PATH"

    # Run Docker container
    echo "Running Docker container: $DOCKER_CONTAINER"
    docker stop "$DOCKER_CONTAINER" > /dev/null 2>&1 || true
    docker run --rm -d --name "$DOCKER_CONTAINER" "$DOCKER_IMG" sleep 3600

    # Copy files from container
    echo "Copying /release from container to: $OUT_DIR"
    docker cp "$DOCKER_CONTAINER:/release/*" "$OUT_DIR"

    # Cleanup
    echo "Cleaning up..."
    docker stop "$DOCKER_CONTAINER" > /dev/null 2>&1 || true

    echo "Done! The /release folder has been copied to $OUT_DIR"
}
