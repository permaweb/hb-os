# Project Build and Deployment Guide

This project uses a Python automation tool (via `run`) to automate the build, setup, and deployment processes for both the host and guest environments. This guide explains the available commands (targets) and their purposes.

---

## Initialization Steps

### 1. Initialization (For **Both Host and Guests**)

Before any build steps, you must initialize the build environment. This target creates the required directories, installs dependencies, downloads the SNP release, and builds essential tools.

Run:
```bash
./run init
```

The `init` target will:
- Create all necessary build directories.
- Install required dependencies.
- Download and extract the SNP release.
- Build the attestation server and digest calculator using Cargo.

---

## Host Setup

### 2. Host Setup

On the **HOST** machine, run the host-specific setup to install host components (for example, installing the SNP release).

Run:
```bash
./run setup_host
```

This target changes into the `build/snp-release` directory and runs the host installation script (`./install.sh`).

---

## Building the Images

### 3. Building the Base Image

Before building the guest image, you must create the base image. This process involves:
- Unpacking the kernel from the downloaded Debian package.
- Building the initramfs.
- Creating a new VM image.
- Running a setup script to configure the VM.

Run:
```bash
./run build_base_image
```

The `build_base_image` target performs the following sub-steps:
- **unpack_kernel:** Unpacks the kernel into the designated kernel directory.
- **initramfs:** Builds the initial ramdisk (initramfs) using Docker.
- **create_vm:** Creates a new VM image.
- **run_setup:** Launches QEMU to run the setup with specified memory, CPU, OVMF, and policy parameters.

---

### 4. Building the Guest Image

Once the base image is ready, build the final guest image. This step will:
- Build the HyperBEAM release.
- Set up dm-verity on the base image.
- Generate a VM configuration file.
- Compute measurement hashes from the VM configuration (for attestation).

Run:
```bash
./run build_guest_image
```

The `build_guest_image` target runs these sub-targets:
- **build_content:** Builds the guest content.
- **setup_verity:** Sets up dm-verity on the base image.
- **setup_vm_config:** Creates and customizes the VM configuration file.
- **get_hashes:** Executes the digest calculator to produce a measurement file.

---

## Running the Guest

### 5. Running the Guest

After building the guest image, you can run the guest environment using QEMU with SNP parameters.

Run:
```bash
./run run
```

This command launches QEMU with the following:
- The dm-verity image and its hash tree.
- The generated VM configuration.
- Specified ports and debugging options from your configuration.

---

## Summary of Commands

- **Initialization (for both host and guests):**
  ```bash
  ./run init
  ```

- **Host Setup:**
  ```bash
  ./run setup_host
  ```

- **Build Base Image:**
  ```bash
  ./run build_base_image
  ```

- **Build Guest Image:**
  ```bash
  ./run build_guest_image
  ```

- **Run Guest:**
  ```bash
  ./run run
  ```

- **Other Targets:**  
  ```bash
  ./run ssh
  ./run clean
  ```
