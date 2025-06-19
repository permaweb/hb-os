#!/bin/bash

# Set non-interactive mode globally for the entire script
export DEBIAN_FRONTEND=noninteractive
export NEEDRESTART_MODE=a

# Install Node.js
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt-get install -y nodejs
node -v && npm -v

# Install Linux packages
sudo dpkg -i linux-*.deb
rm -rf linux-*.deb

# Install Nvidia driver
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

# Disable multipathd service and shutdown
sudo systemctl disable multipathd.service
sudo shutdown now 