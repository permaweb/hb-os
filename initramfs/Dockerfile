FROM ubuntu:22.04

# - kmod : required for insmod
# - lvm2, cryptsetup-bin : required to unlock encrypted disk
# - isc-dhcp-client : required to get ip via dhcp
# - iproute2 : installes the "ip" command. Useful for debugging network issues
# - rsync : for copying read-only directories to read-write RAM filesystems
# - openssh-client : for generating new SSH keys
RUN apt-get update && \
    apt-get install -y \
    kmod \
    lvm2 \
    cryptsetup-bin \
    isc-dhcp-client \
    iproute2 \
    rsync \
    openssh-client

RUN apt-get update && apt-get install -y ncurses-dev make gcc g++ cmake git libssl-dev 
RUN git clone https://github.com/erlang/otp.git
RUN cd otp && git checkout maint-27
RUN cd otp && ./configure --without-wx --without-debugger --without-observer --without-et 
RUN cd otp && make -j8
RUN apt-get install -y sudo
RUN cd otp && sudo make install

RUN git clone https://github.com/erlang/rebar3.git && cd rebar3 && ./bootstrap && sudo mv rebar3 /usr/local/bin/

# Clone HyperBEAM
RUN git clone https://github.com/permaweb/HyperBEAM.git && cd HyperBEAM && git checkout feat/dev_snp_nif

RUN apt-get install -y curl

# Get Rust
RUN curl https://sh.rustup.rs -sSf | bash -s -- -y

# Add .cargo/bin to PATH
ENV PATH="/root/.cargo/bin:${PATH}"

RUN cargo --version

RUN apt-get install -y pkg-config

RUN cd HyperBEAM && rebar3 compile

RUN cd HyperBEAM && rebar3 release

# Copy HyperBEAM to the /usr/ directory
RUN cp -r HyperBEAM/_build/default/rel/hb /usr/hb
RUN rm -rf HyperBEAM

RUN apt-get install -y systemd dbus

# Set up systemd in Docker
RUN mkdir -p /run/systemd && \
    echo 'docker' > /run/systemd/container

# Create systemd service for HyperBEAM
RUN echo '[Unit]' > /etc/systemd/system/hyperbeam.service && \
    echo 'Description=HyperBEAM Node' >> /etc/systemd/system/hyperbeam.service && \
    echo '[Service]' >> /etc/systemd/system/hyperbeam.service && \
    echo 'Type=simple' >> /etc/systemd/system/hyperbeam.service && \
    echo 'WorkingDirectory=/usr/HyperBEAM' >> /etc/systemd/system/hyperbeam.service && \
    echo 'ExecStart=/usr/local/bin/rebar3 shell' >> /etc/systemd/system/hyperbeam.service && \
    echo 'Restart=on-failure' >> /etc/systemd/system/hyperbeam.service && \
    echo '[Install]' >> /etc/systemd/system/hyperbeam.service && \
    echo 'WantedBy=multi-user.target' >> /etc/systemd/system/hyperbeam.service

# Enable the HyperBEAM service
RUN systemctl enable hyperbeam.service

ENV TZ=Etc/UTC
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone


# Set systemd as the entry point
STOPSIGNAL SIGRTMIN+3
CMD ["/lib/systemd/systemd"]
