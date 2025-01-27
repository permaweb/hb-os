FROM ubuntu:22.04

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    kmod \
    lvm2 \
    cryptsetup-bin \
    isc-dhcp-client \
    iproute2 \
    rsync \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

ENV TZ=Etc/UTC
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone
