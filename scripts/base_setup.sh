#!/bin/bash

# Check for NVIDIA GPU parameter (empty means no GPU)
NVIDIA_GPU=${1:-""}

# Install Node.js
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt-get install -y nodejs
node -v && npm -v

# Install Linux packages
sudo dpkg -i linux-*.deb
rm -rf linux-*.deb

# Install Nvidia driver only if NVIDIA GPU is detected
if [ -n "$NVIDIA_GPU" ]; then
    echo "NVIDIA GPU detected ($NVIDIA_GPU), installing NVIDIA drivers..."
    export DEBIAN_FRONTEND=noninteractive
    export NEEDRESTART_MODE=a

    echo "Installing NVIDIA CUDA repository..."
    wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb

    echo "Installing CUDA keyring..."
    sudo -E dpkg -i cuda-keyring_1.1-1_all.deb

    echo "Updating package lists..."
    sudo -E apt-get update -qq

    echo "Installing CUDA toolkit..."
    sudo -E apt-get install -y -qq --no-install-recommends -o Dpkg::Options::="--force-confnew" cuda-toolkit-12-4

    echo "Installing NVIDIA driver..."
    sudo -E apt-get install -y -qq --no-install-recommends -o Dpkg::Options::="--force-confnew" nvidia-driver-550-server-open

    # Clean up downloaded file
    rm -f cuda-keyring_1.1-1_all.deb

    # enable gpu uvm-persistence-mode
    sudo sed -i 's/no-persistence-mode/uvm-persistence-mode/g' /usr/lib/systemd/system/nvidia-persistenced.service
fi

# Disable multipathd service and shutdown
sudo systemctl disable multipathd.service
sudo shutdown now 