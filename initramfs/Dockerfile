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
RUN git clone https://github.com/permaweb/HyperBEAM.git

RUN apt-get install -y curl
RUN cd HyperBEAM && rebar3 compile

# Copy HyperBEAM to the /usr/ directory
RUN cp -r HyperBEAM /usr/HyperBEAM

ENV TZ=Etc/UTC
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone
