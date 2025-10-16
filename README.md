# HyperBEAM OS

HyperBEAM OS is an advanced automation tool for building and running secure virtual machine images with AMD SEV-SNP (Secure Nested Paging) support. The project features a modern, modular architecture with a facade pattern for simplified operations, dependency injection for testability, and comprehensive workflow orchestration.

---

## Table of Contents

- [HyperBEAM OS](#hyperbeam-os)
  - [Table of Contents](#table-of-contents)
  - [Overview](#overview)
  - [Architecture](#architecture)
  - [Features](#features)
  - [Prerequisites](#prerequisites)
    - [BIOS Configuration](#bios-configuration)
    - [Environment Verification](#environment-verification)
  - [Configuration](#configuration)
  - [Usage](#usage)
    - [Command Line Interface](#command-line-interface)
    - [Available Commands](#available-commands)
    - [Example Commands](#example-commands)
    - [Facade System (Advanced)](#facade-system-advanced)
  - [Project Structure](#project-structure)

---

## Overview

HyperBEAM OS provides a complete development and deployment environment for secure VMs with SEV-SNP attestation. The tool automates complex workflows including:

- **Environment Setup**: Initializes build directories, installs dependencies, and configures the host system
- **SNP Integration**: Downloads, builds, and integrates AMD SNP packages (kernel, OVMF, QEMU)
- **VM Image Creation**: Builds secure base and guest VM images with dm-verity integrity protection
- **Attestation Support**: Includes attestation server and digest calculation tools for secure measurements
- **Release Management**: Packages and distributes complete VM releases
- **Development Workflows**: Provides streamlined development and testing environments

The project uses modern Python architecture with dependency injection, facade patterns, and modular service layers for maintainability and testability.

---

## Architecture

HyperBEAM OS follows a layered architecture:

### **Core Layer** (`src/core/`)
- **Build Orchestration**: Coordinates complex build workflows
- **VM Management**: Handles VM lifecycle and configuration
- **Service Interfaces**: Defines contracts for all services
- **Dependency Injection**: Manages service dependencies and lifecycle

### **Facade Layer** (`src/facades/`)
- **Main Facade**: Provides complete workflows (setup, development, release)
- **Setup Facade**: Environment initialization and verification
- **Build Facade**: Build orchestration and status monitoring  
- **VM Facade**: VM lifecycle management
- **Release Facade**: Package creation and distribution

### **Service Layer** (`src/services/`)
- **Configuration Service**: Centralized configuration management
- **Command Execution**: Safe command execution with error handling
- **Docker Service**: Container build and management operations
- **File System Service**: File and directory operations
- **Dependency Service**: System dependency management

### **CLI Layer** (`src/cli/`)
- **CLI Handler**: Argument parsing and command dispatch
- **Error Handling**: Comprehensive error management with user-friendly messages

---

## Features

### **Complete Workflows**
- **Quick Setup**: One-command environment initialization and system build
- **Development Workflow**: Streamlined build-and-test cycle for development
- **Release Workflow**: Automated build, test, and packaging for production
- **Demo Workflow**: Easy demonstration and showcase capabilities

### **Environment Management**
- **Automated Dependencies**: Installs and configures system dependencies
- **Host System Setup**: Configures SEV-SNP host environment
- **Build Directory Management**: Creates and manages build artifacts
- **Environment Validation**: Verifies system readiness and configuration

### **Build System**
- **SNP Package Building**: Builds kernel, OVMF, and QEMU from source
- **Base Image Creation**: Creates foundational VM images with initramfs
- **Guest Image Building**: Builds application-specific guest content
- **Integrity Protection**: Implements dm-verity for tamper detection

### **Security Features**
- **SEV-SNP Support**: Full AMD Secure Nested Paging integration
- **Attestation Framework**: Built-in attestation server and measurement tools
- **Secure Boot**: OVMF-based secure boot configuration
- **Memory Encryption**: Transparent memory encryption support

### **Release Management**
- **Package Creation**: Creates distributable release packages
- **Remote Downloads**: Downloads and installs remote releases
- **Version Management**: Tracks and manages multiple release versions
- **Deployment Ready**: Production-ready deployment packages

### **VM Lifecycle**
- **QEMU Integration**: Advanced QEMU configuration and management
- **SSH Access**: Built-in SSH connectivity to running VMs
- **Port Forwarding**: Configurable network access and port mapping
- **Resource Management**: CPU, memory, and disk resource configuration

---

## Prerequisites

### BIOS Configuration

Some BIOS settings are required in order to use SEV-SNP. The settings slightly differ from machine to machine, but make sure to check the following options:

- **Secure Nested Paging**: Enable SNP.
- **Secure Memory Encryption**: Enable SME (not strictly required for running SNP guests).
- **SNP Memory Coverage**: Must be enabled to reserve space for the Reverse Map Page Table (RMP).  
  [Source](https://github.com/AMDESE/AMDSEV/issues/68)
- **Minimum SEV non-ES ASID**: This value should be greater than 1 to allow for the enabling of SEV-ES and SEV-SNP.

### BIOS Configuration (DELL PowerEdge R6615)

<details open>
<summary>Processor Settings</summary>
<ul>
    <li>
        <b>Virtualization Technology: </b>
        <span style="color:#79FFED;">Enabled</span>
    </li>
    <li>
        <b>IOMMU Support: </b>
        <span style="color:#79FFED;">Enabled</span>
    </li>
    <li>
        <b>Secure Memory Encryption: </b>
        <span style="color:#79FFED;">Enabled</span>
    </li>
    <li>
        <b>Minimum SEV non-ES ASID: </b>
        <span style="color:yellow;">100</span>
    </li>
    <li>
        <b>Secure Nested Paging: </b>
        <span style="color:#79FFED;">Enabled</span>
    </li>
    <li>
        <b>SNP Memory Coverage: </b>
        <span style="color:#79FFED;">Enabled</span>
    </li>
    <li>
        <b>Transparent Secure Memory Encryption: </b>
        <span style="color:#CF6679;">Disabled</span>
    </li>
</ul>
</details>

<details open>
<summary>System Security</summary>
<ul>
    <li>
        <b>TPM Security: </b>
        <span style="color:#79FFED;">On</span>
    </li>
    <li>
        <b>TPM Hierarchy: </b>
        <span style="color:#79FFED;">Enabled</span>
    </li>
    <li>
        <b>TPM Advanced Settings</b>
        <ul>
            <li>
                <b>TPM PPI Bypass Provision: </b>
                <span style="color:#CF6679;">
                    Disabled
                </span>
            </li>
            <li>
                <b>TPM PPI Bypass Clear: </b>
                <span style="color:#CF6679;">
                    Disabled
                </span>
            </li>
            <li>
                <b>TPM2 Algorithm Selection: </b>
                <span style="color:yellow;">SHA256</span>
            </li>
        </ul>
    </li>
</ul>
</details>

### Environment Verification

After configuring your BIOS settings, verify that your system is properly configured for SEV-SNP operations:

#### **Kernel Verification**
Confirm you're running the SNP-enabled kernel:

```bash
uname -r
```

<details>
<summary>Expected Output</summary>

```
6.9.0-rc7-snp-host-05b10142ac6a
```

</details>

#### **CPU Features Check**
Verify that SEV capabilities are available in your CPU:

```bash
grep -w sev /proc/cpuinfo
```

<details>
<summary>Expected Output</summary>

```yaml
flags           : fpu vme de pse tsc msr pae mce cx8 apic sep mtrr pge mca cmov pat pse36 clflush mmx fxsr sse sse2 ht syscall nx mmxext fxsr_opt pdpe1gb rdtscp lm constant_tsc rep_good nopl nonstop_tsc cpuid extd_apicid aperfmperf rapl pni pclmulqdq monitor ssse3 fma cx16 sse4_1 sse4_2 movbe popcnt aes xsave avx f16c rdrand lahf_lm cmp_legacy svm extapic cr8_legacy abm sse4a misalignsse 3dnowprefetch osvw ibs skinit wdt tce topoext perfctr_core perfctr_nb bpext perfctr_llc mwaitx cpb cat_l3 cdp_l3 hw_pstate ssbd mba ibrs ibpb stibp vmmcall fsgsbase bmi1 avx2 smep bmi2 erms invpcid cqm rdt_a rdseed adx smap clflushopt clwb sha_ni xsaveopt xsavec xgetbv1 xsaves cqm_llc cqm_occup_llc cqm_mbm_total cqm_mbm_local clzero irperf xsaveerptr rdpru wbnoinvd amd_ppin arat npt lbrv svm_lock nrip_save tsc_scale vmcb_clean flushbyasid decodeassists pausefilter pfthreshold avic v_vmsave_vmload vgif v_spec_ctrl umip pku ospke vaes vpclmulqdq rdpid overflow_recov succor smca fsrm flush_l1d sme sev sev_es sev_snp
```

</details>

#### **KVM SEV Parameters Check**
Verify that SEV features are enabled in KVM:

```bash
cat /sys/module/kvm_amd/parameters/sev
cat /sys/module/kvm_amd/parameters/sev_es 
cat /sys/module/kvm_amd/parameters/sev_snp 
```

<details>
<summary>Expected Output</summary>

```bash
Y
Y
Y
```

</details>

#### **TPM Status Check**
Verify TPM 2.0 is detected and accessible:

```bash
sudo dmesg | grep -i tpm
sudo ls -l /dev/tpm0
```

<details>
<summary>Expected Output</summary>

```yaml
[    0.000000] efi: ACPI=0x6effe000 ACPI 2.0=0x6effe014 TPMFinalLog=0x6ed9c000 MEMATTR=0x615545a0 SMBIOS=0x69898000 SMBIOS 3.0=0x69896000 MOKvar=0x67bc0000 RNG=0x6ef0d020 TPMEventLog=0x3d2a6020
[    0.004228] ACPI: SSDT 0x000000006EF22000 000623 (v02 DELL   Tpm2Tabl 00001000 INTL 20210331)
[    0.004230] ACPI: TPM2 0x000000006EF21000 00004C (v04 DELL   PE_SC3   00000002 DELL 00000001)
[    0.004258] ACPI: Reserving TPM2 table memory at [mem 0x6ef21000-0x6ef2104b]
[    5.207945] tpm_tis MSFT0101:00: 2.0 TPM (device-id 0xFC, rev-id 1)
crw-rw---- 1 tss root 10, 224 Jul 23 16:29 /dev/tpm0
```

</details>

#### **TPM Functionality Test**
Test TPM operations to ensure proper communication:

```bash
# Install TPM tools if not present
sudo apt-get install tpm2-tools

# Test TPM functionality
sudo tpm2_readclock
```

<details>
<summary>Expected Output</summary>

```yaml
time: 9476751982
clock_info:
  clock: 2675690062
  reset_count: 71
  restart_count: 0
  safe: yes
```

</details>

#### **SEV-SNP Status Verification**
Check that SEV-SNP is properly enabled in the kernel:

```bash
sudo dmesg | grep -i 'sev\|snp'
sudo ls /sys/module/kvm_amd/parameters | grep sev
```

<details>
<summary>Expected Output</summary>

```yaml
[    0.000000] Linux version 6.9.0-rc7-snp-host-05b10142ac6a (root@8a011408bee6) (gcc (Ubuntu 11.4.0-1ubuntu1~22.04) 11.4.0, GNU ld (GNU Binutils for Ubuntu) 2.38) #2 SMP Thu May 30 18:35:46 UTC 2024
[    0.000000] Command line: BOOT_IMAGE=/boot/vmlinuz-6.9.0-rc7-snp-host-05b10142ac6a root=UUID=eb1d7853-1fec-4bc0-b7a3-5d987b6d0119 ro serial console=ttyS1,115200n8 modprobe.blacklist=bnxt_re modprobe.blacklist=rndis_host
[    0.000000] SEV-SNP: RMP table physical range [0x000000601d200000 - 0x000000607dafffff]
[    0.003786] SEV-SNP: Reserving start/end of RMP table on a 2MB boundary [0x000000607da00000]
[    0.240623] Kernel command line: BOOT_IMAGE=/boot/vmlinuz-6.9.0-rc7-snp-host-05b10142ac6a root=UUID=eb1d7853-1fec-4bc0-b7a3-5d987b6d0119 ro serial console=ttyS1,115200n8 modprobe.blacklist=bnxt_re modprobe.blacklist=rndis_host
[    0.240689] Unknown kernel command line parameters "serial BOOT_IMAGE=/boot/vmlinuz-6.9.0-rc7-snp-host-05b10142ac6a", will be passed to user space.
[    4.246111] AMD-Vi: IOMMU SNP support enabled.
[    4.630436] AMD-Vi: Extended features (0xa5bf7320a2294aee, 0x1d): PPR X2APIC NX [5] IA GA PC GA_vAPIC SNP
[    4.651376] AMD-Vi: Force to disable Virtual APIC due to SNP
[    5.900355]     BOOT_IMAGE=/boot/vmlinuz-6.9.0-rc7-snp-host-05b10142ac6a
[    6.404977] usb usb1: Manufacturer: Linux 6.9.0-rc7-snp-host-05b10142ac6a xhci-hcd
[    6.490104] usb usb2: Manufacturer: Linux 6.9.0-rc7-snp-host-05b10142ac6a xhci-hcd
[    6.505333] usb usb3: Manufacturer: Linux 6.9.0-rc7-snp-host-05b10142ac6a xhci-hcd
[    6.520267] usb usb4: Manufacturer: Linux 6.9.0-rc7-snp-host-05b10142ac6a xhci-hcd
[    9.628320] ccp 0000:01:00.5: sev enabled
[   13.720990] ccp 0000:01:00.5: SEV API:1.55 build:38
[   13.721003] ccp 0000:01:00.5: SEV-SNP API:1.55 build:38
[   13.734549] kvm_amd: SEV enabled (ASIDs 100 - 1006)
[   13.734552] kvm_amd: SEV-ES enabled (ASIDs 1 - 99)
[   13.734555] kvm_amd: SEV-SNP enabled (ASIDs 1 - 99)
sev
sev_es
sev_snp
```

</details>

#### **GPU Passthrough Verification**

##### 1. Identify your GPU device ID using `lspci`:

```bash
lspci -nn | grep -i nvidia
```

<details>
<summary>Expected Output</summary>

```yaml
c1:00.0 3D controller [0302]: NVIDIA Corporation Device [10de:2331] (rev a1)
```

</details>


##### 2. Verify the GPU is bound to the `vfio-pci` driver:

```bash
lspci -nnk -d 10de:2331
```
<details>
<summary>Expected Output</summary>

```yaml
c1:00.0 3D controller [0302]: NVIDIA Corporation Device [10de:2331] (rev a1)
        Subsystem: NVIDIA Corporation Device [10de:1626]
        Kernel driver in use: vfio-pci
        Kernel modules: nvidiafb, nouveau
```

</details>

#### **Complete Environment Validation**
Use the `snphost` tool for comprehensive validation:

```bash
sudo modprobe msr
sudo snphost ok
```

<details>
<summary>Expected Output</summary>

```bash
[ PASS ] - AMD CPU
[ PASS ]   - Microcode support
[ PASS ]   - Secure Memory Encryption (SME)
[ PASS ]     - SME: Enabled in MSR
[ PASS ]   - Secure Encrypted Virtualization (SEV)
[ PASS ]     - SEV firmware version: 1.55
[ PASS ]     - Encrypted State (SEV-ES)
[ PASS ]       - SEV-ES initialized
[ PASS ]     - SEV initialized: Initialized, no guests running
[ PASS ]     - Secure Nested Paging (SEV-SNP)
[ PASS ]       - VM Permission Levels
[ PASS ]         - Number of VMPLs: 4
[ PASS ]       - SNP: Enabled in MSR
[ PASS ]       - SNP initialized
[ PASS ]         - RMP table addresses: 0x601d200000 - 0x607dafffff
[ PASS ]         - RMP table initialized
[ PASS ]         - Alias check: Completed since last system update, no aliasing addresses
[ PASS ]     - Physical address bit reduction: 6
[ PASS ]     - C-bit location: 51
[ PASS ]     - Number of encrypted guests supported simultaneously: 1006
[ PASS ]     - Minimum ASID value for SEV-enabled, SEV-ES disabled guest: 100
[ PASS ]     - /dev/sev readable
[ PASS ]     - /dev/sev writable
[ PASS ]   - Page flush MSR: DISABLED
[ PASS ] - KVM supported: API version: 12
[ PASS ]   - SEV enabled in KVM
[ PASS ]   - SEV-ES enabled in KVM
[ PASS ]   - SEV-SNP enabled in KVM
[ PASS ] - Memlock resource limit: Soft: 50438688768 | Hard: 50438688768
[ PASS ] - Comparing TCB values: TCB versions match
 Platform TCB version: TCB Version:
  Microcode:   72
  SNP:         22
  TEE:         0
  Boot Loader: 9
  FMC:         None
 Reported TCB version: TCB Version:
  Microcode:   72
  SNP:         22
  TEE:         0
  Boot Loader: 9
  FMC:         None
```

</details>

All checks should return `[ PASS ]` status for a properly configured environment.

---

## Configuration

HyperBEAM OS uses a centralized configuration system defined in `config.py` that provides type-safe, structured configuration management.

### **Configuration Structure**

The configuration is organized into several key areas:

- **Directory Configuration** (`DirectoryConfig`): Defines all build and output directories
- **Build Configuration** (`BuildConfig`): Controls build options, branches, and feature flags  
- **VM Configuration** (`VMConfig`): Virtual machine settings including CPU, memory, and security options
- **Network Configuration** (`NetworkConfig`): VM networking and SSH connectivity settings

### **Configuration Options**

#### **BuildConfig - Build and Development Settings**
```python
# Branch Configuration
hb_branch = "edge"                           # HyperBEAM branch for builds
ao_branch = "tillathehun0/cu-experimental"   # AO branch for local CU (DEPRECATED)

# Virtualization and Debug Features  
debug = False                               # Enable SSH access for development (False = black box VM)
enable_kvm = True                          # Enable KVM acceleration
enable_tpm = True                          # Enable TPM 2.0 support
enable_gpu = False                         # Enable GPU passthrough support

# Image Configuration
base_image = "base.qcow2"                  # Base VM image filename
guest_image = "guest.qcow2"                # Guest VM image filename

# External Repositories
gpu_admin_tools_repo = "https://github.com/permaweb/gpu-admin-tools"  # GPU tools repository
```

#### **VMConfig - Virtual Machine Settings**
```python
# Hardware Configuration
host_cpu_family = "Genoa"                  # Host CPU family (AMD Genoa)
vcpu_count = 12                            # Number of virtual CPUs
memory_mb = 204800                         # Memory allocation in MB (~200GB)

# SEV-SNP Security Configuration
guest_features = "0x1"                     # Guest feature flags
platform_info = "0x3"                     # Platform information
guest_policy = "0x30000"                   # SEV-SNP guest policy
family_id = "00000000000000000000000000000000"  # 32-char family identifier
image_id = "00000000000000000000000000000000"   # 32-char image identifier

# Kernel Configuration
cmdline = "console=ttyS0 earlyprintk=serial root=/dev/sda"  # Kernel command line
```

#### **NetworkConfig - Connectivity Settings**
```python
# VM Network Configuration
vm_host = "localhost"                      # VM host address for SSH
vm_port = 2222                            # SSH port forwarding
vm_user = "ubuntu"                        # Default SSH username
hb_port = 80                              # HyperBEAM service port
qemu_port = 4444                          # QEMU management port
```

#### **TCBConfig - Trusted Computing Base**
```python
# TCB Version Components
bootloader = 9                            # Bootloader TCB version
tee = 0                                   # TEE TCB version
snp = 22                                  # SNP TCB version
microcode = 72                            # Microcode TCB version
reserved = [0, 0, 0, 0]                   # Reserved TCB fields
```

#### **QEMUConfig - QEMU Virtualization**
```python
# QEMU Configuration
launch_script = "./launch.sh"             # QEMU launch script path
snp_params = "-sev-snp"                   # SNP-specific QEMU parameters
```

#### **SNPConfig - SNP Package Management**
```python
# SNP Release Configuration
release_url = "https://github.com/permaweb/hb-os/releases/download/v1.0.0/snp-release.tar.gz"

# Build Dependencies (automatically installed during init)
dependencies = [
    "build-essential", "git", "python3", "python3-venv", "ninja-build",
    "libglib2.0-dev", "uuid-dev", "iasl", "nasm", "python-is-python3",
    "flex", "bison", "openssl", "libssl-dev", "libelf-dev", "bc",
    "libncurses-dev", "gawk", "dkms", "libudev-dev", "libpci-dev",
    "libiberty-dev", "autoconf", "llvm", "cpio", "zstd", "debhelper",
    "rsync", "wget", "python3-tomli"
]
```

### **Customizing Configuration**

You can modify `config.py` to customize the build and runtime behavior:

#### **Common Customizations**

1. **Development Branches**: Change `hb_branch` for different hyperbeam releases
2. **VM Resources**: Adjust `vcpu_count` and `memory_mb` based on your hardware
3. **Debug Mode**: Set `debug = True` to enable SSH access for development (False creates a black box VM)
4. **GPU Support**: Enable `enable_gpu = True` for GPU passthrough capabilities
5. **Network Ports**: Modify `vm_port` and other ports to avoid conflicts
6. **SEV-SNP Security**: Update `guest_policy`, `family_id`, and `image_id` for production deployments

#### **Advanced Configuration**

- **TCB Versions**: Modify TCB component versions to match your platform requirements
- **Kernel Command Line**: Customize `cmdline` for specific kernel parameters
- **QEMU Parameters**: Adjust QEMU launch script and SNP parameters
- **SNP Dependencies**: Add or remove build dependencies for custom environments
- **File Paths**: Directory structure is automatically managed but can be customized if needed

#### **Security Considerations**

- **Debug Mode**: When `debug = False` (production), the VM runs as a completely isolated black box with no external access points, providing maximum security isolation. When `debug = True` (development), SSH access is enabled for debugging and development purposes, which reduces security isolation but allows for development workflows.

#### **Runtime Overrides**

Some settings can be overridden at runtime without modifying `config.py`:
- Branch selection via CLI arguments: `--hb-branch` and `--ao-branch`
- Resource allocation through facade system parameters
- Debug mode via environment variables or facade configuration

### **Configuration Validation**

The configuration system includes:
- **Type Safety**: Uses Python dataclasses for compile-time validation
- **Path Validation**: Automatically creates and validates directory structures
- **Default Values**: Provides sensible defaults for all options
- **Environment Integration**: Seamlessly integrates with the facade system

For detailed configuration options, see the `config.py` file and the `ConfigurationService` class in `src/services/configuration_service.py`.

---

## Usage

### Command Line Interface

HyperBEAM OS provides a command-line interface for all operations:

```bash
./run <command> [options]
./run help  # Display detailed help information
```

### Available Commands

#### **Core Build Commands**
- **`init`** - Initialize the complete build environment
  ```bash
  ./run init [--snp-release PATH]
  ```
  - Creates build directories and installs dependencies
  - Downloads and extracts SNP release packages
  - Builds attestation server and digest calculator tools
  - Configures host system for SEV-SNP operations

- **`setup_host`** - Configure the host system for SEV-SNP
  ```bash
  ./run setup_host
  ```

- **`setup_gpu`** - Configure GPU passthrough for confidential computing
  ```bash
  ./run setup_gpu
  ```

#### **Image Building Commands**
- **`build_snp_release`** - Build SNP packages (kernel, OVMF, QEMU) from source
  ```bash
  ./run build_snp_release
  ```

- **`build_base`** - Build the base VM image with kernel and initramfs
  ```bash
  ./run build_base
  ```

- **`build_guest`** - Build the guest image with application content
  ```bash
  ./run build_guest [--hb-branch BRANCH] [--ao-branch BRANCH]
  ```

#### **VM Management Commands**
- **`start`** - Start the VM with the current configuration
  ```bash
  ./run start [--data-disk PATH]
  ```

- **`start_release`** - Start the VM using packaged release files
  ```bash
  ./run start_release [--data-disk PATH]
  ```

- **`ssh`** - Connect to the running VM via SSH
  ```bash
  ./run ssh
  ```

#### **Release Management Commands**
- **`package_release`** - Create a distributable release package
  ```bash
  ./run package_release
  ```

- **`download_release`** - Download and install a remote release
  ```bash
  ./run download_release --url URL
  ```

#### **Utility Commands**
- **`clean`** - Clean up build artifacts and temporary files
  ```bash
  ./run clean
  ```

- **`help`** - Display comprehensive help information
  ```bash
  ./run help
  ```

### Example Commands

#### **Quick Start (Complete Setup)**
```bash
# Complete environment setup and build
./run init
./run build_base
./run build_guest
./run start
```

#### **Development Workflow**
```bash

# Prerequisits: you have already ran ./run init and ./run build_base
# Set debug = True (config.py)

# Development cycle
./run build_guest --hb-branch feature-branch
./run start --data-disk /path/to/dev-disk.img # (Optional: --data-disk for non vol storage)
ssh -p 2222 root@localhost  # Connect to test your changes (password: hb)
```

#### **Release Workflow**
```bash
# Build complete system for release
./run build_snp_release  # If building from source (Have to init again with new snp-release build)
./run build_base
./run build_guest --hb-branch release-v1.0
./run package_release

# Test the release
./run start_release
```

#### **Using Pre-built Releases**
```bash
# Download and run a release
./run download_release --url https://releases.hyperbeam.com/v1.0.0/release.tar.gz
./run start_release --data-disk /mnt/storage.img # (Optional: --data-disk for non vol storage)
```

#### **System Maintenance**
```bash
# Clean up build artifacts
./run clean

# Verify environment setup
./run init --help  # Check available options
```

### Facade System (Advanced)

For programmatic usage and advanced workflows, HyperBEAM OS provides a facade system:

```python
from src.core.service_factory import get_service_container
from src.core.facade_interfaces import IHyperBeamFacade

# Get the main facade
container = get_service_container()
hyperbeam = container.resolve(IHyperBeamFacade)

# Complete workflows
hyperbeam.quick_setup()                    # Full environment setup
hyperbeam.development_workflow()           # Build and start for development
release_path = hyperbeam.release_workflow() # Build and package for release
hyperbeam.demo_workflow()                  # Run demonstration

# System status and monitoring
status = hyperbeam.get_system_status()
hyperbeam.print_status_report()
```

#### **Individual Facade Usage**
```python
from src.core.facade_interfaces import IBuildFacade, IVMFacade

build_facade = container.resolve(IBuildFacade)
vm_facade = container.resolve(IVMFacade)

# Targeted operations
build_facade.build_guest_image(hb_branch="experimental")
vm_facade.create_and_start_vm(data_disk="/path/to/disk.img")
```

See [FACADE_GUIDE](examples/FACADE_GUIDE.md) for comprehensive facade documentation.

---

## Project Structure

```yaml
hb-os/
├── 📂 src/                           # Main source code
│   ├── 📂 cli/                       # Command Line Interface
│   │   └── cli_handler.py            # Argument parsing and command dispatch
│   ├── 📂 core/                      # Core business logic
│   │   ├── build_orchestrator.py     # Build workflow coordination
│   │   ├── build_content.py          # Guest content building
│   │   ├── build_initramfs.py        # Initramfs creation
│   │   ├── build_snp_packages.py     # SNP package building
│   │   ├── create_new_vm.py          # VM image creation
│   │   ├── create_vm_config.py       # VM configuration generation
│   │   ├── di_container.py           # Dependency injection container
│   │   ├── facade_interfaces.py      # Facade pattern interfaces
│   │   ├── service_factory.py        # Service registration and creation
│   │   ├── service_interfaces.py     # Service contracts
│   │   ├── setup_guest.py            # Guest setup and dm-verity
│   │   ├── vm_manager.py             # VM lifecycle management
│   │   └── initialization.py         # Environment initialization
│   ├── 📂 facades/                   # High-level workflow facades
│   │   ├── build_facade.py           # Build operations facade
│   │   ├── hyperbeam_facade.py       # Main orchestration facade
│   │   ├── release_facade.py         # Release management facade
│   │   ├── setup_facade.py           # Environment setup facade
│   │   └── vm_facade.py              # VM management facade
│   ├── 📂 services/                  # Low-level services
│   │   ├── command_execution_service.py  # Command execution
│   │   ├── configuration_service.py      # Configuration management
│   │   ├── dependencies.py               # Dependency installation
│   │   ├── docker_service.py             # Docker operations
│   │   ├── filesystem_service.py         # File system operations
│   │   ├── release_manager.py            # Release packaging
│   │   └── snp_component_service.py      # SNP component management
│   └── 📂 utils/                     # Utility functions and helpers
│       └── utils.py                  # Common utilities and error handling
├── 📂 config/                        # Configuration management
│   ├── config.py                     # Type-safe configuration classes
│   └── 
├── 📂 examples/                      # Usage examples and documentation
│   ├── FACADE_GUIDE.md              # Comprehensive facade usage guide
│   ├── example_facade_usage.py      # Facade system examples
│   ├── test_release_package.py      # Release testing script
│   └── vm-config-template.toml      # VM configuration template
├── 📂 resources/                     # Build resources and templates
│   ├── content.Dockerfile           # Guest content container definition
│   ├── initramfs.Dockerfile         # Initramfs build container
│   ├── init.sh                      # VM initialization script
│   ├── hyperbeam.service            # HyperBEAM systemd service
│   ├── cu.service                   # Compute unit service
│   └── template-user-data            # Cloud-init template
├── 📂 scripts/                       # Build and setup scripts
│   ├── base_setup.sh               # Base system setup
│   ├── gpu_passthrough.sh          # GPU passthrough configuration
│   ├── init.sh                     # Environment initialization
│   └── install.sh                  # Installation script
├── 📂 tools/                        # Attestation and security tools
│   ├── 📂 attestation_server/       # Rust-based attestation server
│   │   ├── Cargo.toml               # Rust project configuration
│   │   └── src/                     # Attestation server source
│   └── 📂 digest_calc/              # Measurement digest calculator
│       ├── Cargo.toml               # Rust project configuration
│       └── src/                     # Digest calculator source
├── run                              # Main entry point script
├── launch.sh                        # QEMU VM launcher
├── config.py                        # Global configuration
├── LICENSE                          # License information
└── README.md                        # This documentation
```

### Key Directories Explained

#### **`src/cli/`** - Command Line Interface
- Handles argument parsing, command validation, and dispatch
- Provides user-friendly error messages and help documentation
- Entry point for all CLI operations

#### **`src/core/`** - Core Business Logic  
- Contains the main business logic and workflow orchestration
- Implements dependency injection for testable, modular code
- Manages complex build processes and VM lifecycle operations

#### **`src/facades/`** - High-Level Workflows
- Provides simplified APIs for complex multi-step operations
- Implements the facade pattern for better usability
- Orchestrates services to provide complete workflows

#### **`src/services/`** - Infrastructure Services
- Low-level services for system operations (file I/O, commands, Docker)
- Encapsulates external dependencies behind clean interfaces
- Provides consistent error handling and logging

#### **`tools/`** - Security and Attestation
- **Attestation Server**: Rust-based server for SEV-SNP attestation
- **Digest Calculator**: Computes measurement digests for integrity verification
- Built using Cargo and integrated into the Python build system

#### **`resources/`** & **`scripts/`** - Build Assets
- Container definitions, initialization scripts, and system configurations
- Templates and configuration files for VM and service setup
- Shell scripts for system-level operations and environment setup
