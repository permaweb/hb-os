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
RUN git clone https://github.com/erlang/otp.git && \
    cd otp && \
    git checkout maint-27 && \
    ./configure --without-wx --without-debugger --without-observer --without-et && \
    make -j$(nproc) && \
    sudo make install && \
    cd .. && rm -rf otp

# Build and Install Rebar3
RUN git clone https://github.com/erlang/rebar3.git && \
    cd rebar3 && \
    ./bootstrap && \
    sudo mv rebar3 /usr/local/bin/ && \
    cd .. && rm -rf rebar3

# Install Rust and Cargo
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | \
    sh -s -- -y --default-toolchain stable

# Set up build directories
RUN mkdir -p /build /release

# Copy the service file to /release
COPY hyperbeam.service /release

# Clone the HyperBEAM repository
RUN git clone https://github.com/permaweb/HyperBEAM.git /build/HyperBEAM

# Compile the application code using Rebar3
RUN echo "Force rebuild: $(date +%s)"
RUN cd /build/HyperBEAM && git pull && git checkout test/snp && \
    rebar3 release && \
    cp -r _build/default/rel/hb /release/hb && \
    mkdir -p /release/hb/test && \
    cp test/OVMF-1.55.fd /release/hb/test/OVMF-1.55.fd


# Clean up build files
RUN rm -rf /build

# Set default command
CMD ["/bin/bash"]
