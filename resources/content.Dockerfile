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
RUN curl -fsSL https://deb.nodesource.com/setup_22.16.0 | sudo -E bash - && \
    apt-get install -y nodejs && \
    node -v && npm -v

# Set up build directories
RUN mkdir -p /build /release

# Clone the subdirectory "servers/cu" from the "permaweb/ao" repository using sparse checkout
# RUN git clone --filter=blob:none --no-checkout https://github.com/permaweb/ao.git /build/ao && \
#     cd /build/ao && \
#     git sparse-checkout init --cone && \
#     git sparse-checkout set servers/cu && \
#     git checkout <AO_BRANCH> && \
#     cp -r servers/cu /release/cu

# Copy the cu.env file to the release directory
# COPY ./cu/cu.env /release/cu.env

# Copy the cu.env file to the release directory
# RUN cp /release/cu.env /release/cu/.env

# # Generate a wallet and inject it into the cu.env file
# RUN WALLET=$(npx --yes @permaweb/wallet) && \
#     cp /release/cu.env /release/cu/.env && \
#     echo "WALLET=${WALLET}" >> /release/cu/.env

# Copy CU service file to /release
# COPY ./cu/cu.service /release

# Add cache buster to prevent git clone caching
ARG CACHEBUST=1

# Clone the HyperBEAM repository
RUN git clone --depth=1 --branch <HB_BRANCH> https://github.com/permaweb/HyperBEAM.git /build/HyperBEAM

# Copy the config flat configurations to HyperBEAM Dir before building release.
COPY ./hyperbeam/config.flat /build/HyperBEAM/config.flat

# Compile the application code using Rebar3
RUN cd /build/HyperBEAM && \
    rebar3 as genesis_wasm release && \
    cp -r _build/genesis_wasm/rel/hb /release/hb && \
    mkdir -p /release/hb/test && \
    cp test/OVMF-1.55.fd /release/hb/test/OVMF-1.55.fd

# Copy the service file to /release
COPY ./hyperbeam/hyperbeam.service /release

# Clean up build files
RUN rm -rf /build

# Set default command
CMD ["/bin/bash"]
