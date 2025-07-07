#!/bin/bash

# Install Node.js
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt-get install -y nodejs=22.16.0-1nodesource1
node -v && npm -v

# Install Linux packages
sudo dpkg -i linux-*.deb
rm -rf linux-*.deb

# Disable multipathd service and shutdown
sudo systemctl disable multipathd.service
sudo shutdown now 