#!/bin/bash

# Check for NVIDIA GPU parameter (empty means no GPU)
USE_GPU=${1:-""}

# Install Node.js
echo "Installing Node.js..."
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt-get install -y nodejs=22.16.0-1nodesource1
node -v && npm -v

echo "Installing TPM passthrough dependencies..."
sudo apt-get install -y tpm2-tools libtss2-dev

# Install Linux packages
sudo dpkg -i linux-*.deb
rm -rf linux-*.deb

# Install Nvidia driver only if NVIDIA GPU is detected
if [ "$USE_GPU" = "1" ]; then
    echo "GPU enabled, installing NVIDIA drivers..."
    export DEBIAN_FRONTEND=noninteractive
    export NEEDRESTART_MODE=a

    echo "Installing NVIDIA CUDA repository..."
    # https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb
    wget -O cuda-keyring_1.1-1_all.deb https://arweave.net/hn7zxIPhJtnJXk_1MhybRtispij3paeOrw-KWVDD19Q

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