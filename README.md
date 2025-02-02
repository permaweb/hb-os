# Project Build and Deployment Guide

This project uses a Makefile to automate the build, setup, and deployment processes for both the host and guest environments. The following instructions explain the available commands and their purpose.

---

## Initialization Steps

### 1. Initialization (For **Both Host and Guests**)

Before any build steps, you must initialize the build environment. This target creates required directories, installs dependencies, downloads the SNP release, and builds essential tools.

Run:
```bash
make init
```

The `init` target will:
- Create the build directories.
- Install required dependencies via `./install-dependencies.sh`.
- Download and extract the SNP release.
- Build the attestation server and digest calculator using Cargo.

---

## Host Setup

### 2. Host Setup

On the **HOST** machine, you must run additional setup steps to install host-specific components (e.g., installing the SNP release).

Run:
```bash
make setup_host
```

This target will change to the `build/snp-release` directory and run the host installation script (`./install.sh`).

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
make build_base_image
```

The `build_base_image` target internally calls:
- `unpack_kernel`: Unpacks the kernel into the `$(KERNEL_DIR)` directory.
- `initramfs`: Builds the initial ramdisk (initramfs) using Docker.
- `create_vm`: Creates a new VM image (using a shell script in `src/guest-vm/`).
- `run_setup`: Launches QEMU to run the setup (with defined memory, CPU, OVMF, and policy parameters).

---

### 4. Building the Guest Image

Once the base image is ready, you can build the final guest image. This step will:
- Build the HyperBEAM release.
- Set up dm-verity on the base image.
- Fetch a VM configuration template.
- Calculate hashes from the VM configuration (used for attestation).

Run:
```bash
make build_guest_image
```

The `build_guest_image` target runs these sub-targets:
- `build_hb_release`: Releases the HyperBEAM components.
- `setup_verity`: Sets up dm-verity on the base image.
- `fetch_vm_config_template`: Copies the VM configuration template and customizes it.
- `get_hashes`: Runs the digest calculator to produce a measurement file.

---

## Running the Guest

### 5. Running the Guest

After building the guest image, you can run the guest environment using QEMU with SNP parameters.

Run:
```bash
make run
```

This command will launch QEMU with the following:
- The verity image and hash tree.
- The generated VM configuration.
- Ports and debugging options as specified in the Makefile.

For a release version of the guest, you may also use:
```bash
make run_release
```

---

## Additional Helper Commands

The Makefile provides several helper targets:
- **attest_verity_vm**: Attest the verity-enabled VM.
- **ssh**: SSH into the guest machine using the configured port and SSH keys.
- **package_base** and **package_guest**: Package the base or guest images for distribution.
- **clean**: Remove the build directory and all build artifacts.

Use these targets as needed for further operations or troubleshooting.

---

## Summary of Commands

- **For both host and guests:**  
  ```bash
  make init
  ```

- **For HOST:**  
  ```bash
  make setup_host
  ```

- **For Building Base Image (prerequisite to building guest image):**  
  ```bash
  make build_base_image
  ```

- **For Building Guest Image:**  
  ```bash
  make build_guest_image
  ```

- **For running the guest:**  
  ```bash
  make run
  ```

---

Follow these steps in order to set up and deploy the project correctly. For any issues or further customization, please refer to the individual Makefile targets or consult the project documentation.
