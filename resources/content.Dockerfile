# Use Ubuntu 22.04 as the base image
FROM --platform=linux/amd64 ubuntu:22.04

# Set environment variables to avoid interactive prompts during installations
ENV DEBIAN_FRONTEND=noninteractive \
    PATH="/root/.cargo/bin:$PATH"

# Install necessary dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    pkg-config \
    ncurses-dev \
    libssl-dev \
    sudo \
    curl \
    ca-certificates \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Build and Install Erlang/OTP
RUN git clone --depth=1 --branch maint-27 https://github.com/erlang/otp.git && \
    cd otp && \
    ./configure --without-wx --without-debugger --without-observer --without-et && \
    make -j$(nproc) && \
    sudo make install && \
    cd .. && rm -rf otp

# Build and Install Rebar3
RUN git clone --depth=1 https://github.com/erlang/rebar3.git && \
    cd rebar3 && \
    ./bootstrap && \
    sudo mv rebar3 /usr/local/bin/ && \
    cd .. && rm -rf rebar3

# Install Rust and Cargo
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | \
    sh -s -- -y --default-toolchain stable

#Install Node.js (includes npm and npx)
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash - && \
    apt-get install -y nodejs=22.16.0-1nodesource1 && \
    node -v && npm -v

# Set up build directories
RUN mkdir -p /build /release

# Add cache buster to prevent git clone caching
ARG CACHEBUST=1

# Add build argument to control HyperBEAM building
ARG SKIP_HYPERBEAM=false

# Conditionally build HyperBEAM (skip entirely in debug mode)
COPY ./hyperbeam/hyperbeam.service ./hyperbeam/config.flat /tmp/
RUN if [ "$SKIP_HYPERBEAM" != "true" ]; then \
        echo "Building HyperBEAM..."; \
        git clone --depth=1 --branch <HB_BRANCH> https://github.com/permaweb/HyperBEAM.git /build/HyperBEAM && \
        cp /tmp/config.flat /build/HyperBEAM/config.flat && \
        echo "Compiling HyperBEAM..." && \
        cd /build/HyperBEAM && \
        rebar3 as genesis_wasm release && \
        cp -r _build/genesis_wasm/rel/hb /release/hb && \
        mkdir -p /release/hb/test && \
        cp test/OVMF-1.55.fd /release/hb/test/OVMF-1.55.fd && \
        cp /tmp/hyperbeam.service /release/hyperbeam.service; \
    else \
        echo "🐛 Debug mode: Skipping HyperBEAM build entirely"; \
    fi

# Clean up build files
RUN rm -rf /build

# Set default command
CMD ["/bin/bash"]
