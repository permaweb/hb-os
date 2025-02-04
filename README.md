# VM Automation Tool

This automation tool builds and runs virtual machine images. It replaces traditional Makefile tasks with an updated configuration and improved readability. The tool handles everything from setting up the build environment and installing dependencies to creating VM images and launching QEMU.

---

## Table of Contents

- [VM Automation Tool](#vm-automation-tool)
  - [Table of Contents](#table-of-contents)
  - [Overview](#overview)
  - [Features](#features)
  - [Prerequisites](#prerequisites)
    - [BIOS Configuration](#bios-configuration)
    - [Checking Configuration](#checking-configuration)
  - [Installation](#installation)
  - [Usage](#usage)
    - [Available Targets](#available-targets)
    - [Example Commands](#example-commands)
  - [Project Structure](#project-structure)

---

## Overview

This tool automates tasks such as:

- Initializing the build environment
- Installing dependencies
- Downloading and extracting the SNP release tarball
- Building attestation server binaries and a digest calculator
- Creating and configuring VM images
- Building the initramfs
- Setting up guest content and verity
- Running the VM via QEMU
- Cleaning up the build directory

It integrates multiple components (found in the `src/` directory) and uses configuration parameters defined in `config/config.py`.

---

## Features

- **Initialization**: Creates required directories and installs system dependencies.
- **SNP Release Handling**: Downloads, extracts, and builds SNP release components.
- **Kernel & Initramfs**: Unpacks the kernel package and builds the initramfs image.
- **VM Image Creation**: Uses a template to create a new VM image.
- **Guest Content Build**: Builds the guest content (via Docker) and sets up dm-verity.
- **VM Configuration**: Creates configuration files for the VM.
- **Hash Measurements**: Generates measurement inputs using a digest calculator.
- **VM Execution**: Launches QEMU with both base and guest image configurations.
- **Host Setup**: Installs the SNP release on the host.
- **Cleanup**: Cleans the build directory when needed.

---

## Prerequisites

### BIOS Configuration

Some BIOS settings are required in order to use SEV-SNP. The settings slightly
differ from machine to machine, but make sure to check the following options:

- `Secure Nested Paging`: to enable SNP
- `Secure Memory Encryption`: to enable SME (not strictly required for running
  SNP guests)
- `SNP Memory Coverage`: needs to be enabled to reserve space for the Reverse
  Map Page Table (RMP). [Source](https://github.com/AMDESE/AMDSEV/issues/68)
- `Minimum SEV non-ES ASID`: this option configures the minimum address space ID
  used for non-ES SEV guests. By setting this value to 1 you are allocating all
  ASIDs for normal SEV guests, and it would not be possible to enable SEV-ES and
  SEV-SNP. So, this value should be greater than 1.

### Checking Configuration

```bash
# Check kernel version
uname -r
# 6.9.0-rc7-snp-host-05b10142ac6a

# Check if SEV is among the CPU flags
grep -w sev /proc/cpuinfo
# flags           : ...
# flush_l1d sme sev sev_es sev_snp

# Check if SEV, SEV-ES and SEV-SNP are available in KVM
cat /sys/module/kvm_amd/parameters/sev
# Y
cat /sys/module/kvm_amd/parameters/sev_es 
# Y
cat /sys/module/kvm_amd/parameters/sev_snp 
# Y

# Check if SEV is enabled in the kernel
sudo dmesg | grep -i -e rmp -e sev
# SEV-SNP: RMP table physical range [0x000000bf7e800000 - 0x000000c03f0fffff]
# SEV-SNP: Reserving start/end of RMP table on a 2MB boundary [0x000000c03f000000]
# ccp 0000:01:00.5: sev enabled
# ccp 0000:01:00.5: SEV firmware update successful
# ccp 0000:01:00.5: SEV API:1.55 build:21
# ccp 0000:01:00.5: SEV-SNP API:1.55 build:21
# kvm_amd: SEV enabled (ASIDs 510 - 1006)
# kvm_amd: SEV-ES enabled (ASIDs 1 - 509)
# kvm_amd: SEV-SNP enabled (ASIDs 1 - 509)
```

---

## Installation

1. **Clone the Repository:**

2. **Ensure System Dependencies:**

   The tool will install many system dependencies automatically during the `init` target, but you may need to have some pre-installed (like QEMU, Cargo, etc.).

---

## Usage

This tool is driven by command-line targets. To run the tool, use:

```bash
./run <target>
```

### Available Targets

- **init**:  
  Initializes the build environment, creates directories, installs dependencies, downloads and extracts the SNP release tarball, and builds attestation server binaries and the digest calculator.

- **setup_host**:  
  This target prepares the host machine for running virtualization with SEV-SNP features.

- **build_base_image**:  
  Unpacks the kernel, builds the initramfs, creates the base VM image, and runs QEMU setup.

- **build_guest_image**:  
  Builds the guest content, sets up dm-verity, creates the VM configuration file, and generates hash measurements.

- **start**:  
  Starts the VM using QEMU with the guest image configuration.

- **clean**:  
  Cleans up the build directory.

### Example Commands

- **Initialize the Environment:**

  ```bash
  ./run init
  ```

- **Setup Host Machine:**

  ```bash
  ./run setup_host
  ```

- **Build the Base VM Image:**

  ```bash
  ./run build_base
  ```

- **Build the Guest Image:**

  ```bash
  ./run build_guest
  ```

- **Run the VM:**

  ```bash
  ./run start
  ```

- **Clean the Build Directory:**

  ```bash
  ./run clean
  ```

---

## Project Structure

```yaml
├── config                      
│   ├── config.py                 # Configuration Options
│   └── template-user-data
├── examples
│   └── vm-config-template.toml
├── resources
│   ├── content.Dockerfile
│   ├── cu.service
│   ├── hyperbeam.service
│   ├── init.sh
│   └── initramfs.Dockerfile
├── src
│   ├── build_content.py
│   ├── build_initramfs.py
│   ├── create_new_vm.py
│   ├── create_vm_config.py
│   ├── dependencies.py
│   └── setup_guest.py
├── tools
│   ├── attestation_server
│   └── digest_calc
├── launch.sh                    # QEMU Launch VM (Called by Run)
└── run                          # Entry Point
```