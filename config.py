# config.py
"""
HyperBEAM OS Configuration Management

Provides type-safe, well-structured configuration for the HyperBEAM build system.
Uses dataclasses for better IDE support, type checking, and validation.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional


@dataclass
class DirectoryConfig:
    """Directory paths used throughout the build system."""
    
    # Core directories
    base: str = field(init=False)
    build: str = field(init=False)
    bin: str = field(init=False)
    content: str = field(init=False)
    guest: str = field(init=False)
    kernel: str = field(init=False)
    verity: str = field(init=False)
    snp: str = field(init=False)
    resources: str = field(init=False)
    scripts: str = field(init=False)
    config: str = field(init=False)
    
    def __post_init__(self):
        """Initialize computed directory paths."""
        self.base = os.path.realpath(os.path.join(os.path.dirname(__file__), ".."))
        self.build = os.path.realpath("build")
        self.bin = os.path.join(self.build, "bin")
        self.content = os.path.join(self.build, "content")
        self.guest = os.path.join(self.build, "guest")
        self.kernel = os.path.join(self.build, "kernel")
        self.verity = os.path.join(self.build, "verity")
        self.snp = os.path.join(self.build, "snp-release")
        self.resources = os.path.realpath("resources")
        self.scripts = os.path.realpath("scripts")
        self.config = os.path.realpath("config")


@dataclass
class BuildConfig:
    """Build-related configuration settings."""
    
    # Branch configuration
    hb_branch: str = "edge"
    ao_branch: str = "tillathehun0/cu-experimental"
    
    # Debug and virtualization
    debug: bool = False
    enable_kvm: bool = True
    enable_tpm: bool = True
    
    # Image names
    base_image: str = "base.qcow2"
    guest_image: str = "guest.qcow2"


@dataclass
class VMConfig:
    """Virtual machine configuration settings."""
    
    # VM Hardware Configuration
    host_cpu_family: str = "Milan"
    vcpu_count: int = 42
    memory_mb: int = 204800  # Changed from string to int
    
    # SEV-SNP Guest Policy Settings
    guest_features: str = "0x1"
    platform_info: str = "0x3"
    guest_policy: str = "0x30000"
    family_id: str = "00000000000000000000000000000000"
    image_id: str = "00000000000000000000000000000000"
    
    # Kernel command line
    cmdline: str = "console=ttyS0 earlyprintk=serial root=/dev/sda"


@dataclass
class TCBConfig:
    """Trusted Computing Base (TCB) configuration."""
    
    bootloader: int = 4
    tee: int = 0
    snp: int = 22
    microcode: int = 213
    reserved: List[int] = field(default_factory=lambda: [0, 0, 0, 0])


@dataclass
class NetworkConfig:
    """Network and SSH configuration."""
    
    vm_host: str = "localhost"
    vm_port: int = 2222  # Changed from string to int
    vm_user: str = "ubuntu"
    hb_port: int = 80  # Changed from string to int
    qemu_port: int = 4444  # Changed from string to int


@dataclass
class QEMUConfig:
    """QEMU-specific configuration."""
    
    launch_script: str = "./launch.sh"
    snp_params: str = "-sev-snp"


@dataclass
class SNPConfig:
    """SNP package building configuration."""
    
    use_stable_snapshots: bool = False
    amdsev_repo: str = "https://github.com/permaweb/AMDSEV.git"
    amdsev_branch: str = "snp-cc"
    dependencies: List[str] = field(default_factory=lambda: [
        "build-essential", "git", "python3", "python3-venv", "ninja-build",
        "libglib2.0-dev", "uuid-dev", "iasl", "nasm", "python-is-python3",
        "flex", "bison", "openssl", "libssl-dev", "libelf-dev", "bc",
        "libncurses-dev", "gawk", "dkms", "libudev-dev", "libpci-dev",
        "libiberty-dev", "autoconf", "llvm", "cpio", "zstd", "debhelper",
        "rsync", "wget", "python3-tomli"
    ])


class HyperBeamConfig:
    """
    Main configuration class that aggregates all configuration sections.
    
    Provides type-safe access to all configuration settings with logical grouping
    and computed properties for commonly used derived values.
    """
    
    def __init__(self):
        # Configuration sections
        self.dirs = DirectoryConfig()
        self.build = BuildConfig()
        self.vm = VMConfig()
        self.tcb = TCBConfig()
        self.network = NetworkConfig()
        self.qemu = QEMUConfig()
        self.snp = SNPConfig()
        
        # Allow runtime modification of branch settings
        self._runtime_hb_branch: Optional[str] = None
        self._runtime_ao_branch: Optional[str] = None
    
    # ===================== Dynamic Properties =====================
    
    @property
    def hb_branch(self) -> str:
        """HyperBEAM branch (can be overridden at runtime)."""
        return self._runtime_hb_branch or self.build.hb_branch
    
    @hb_branch.setter
    def hb_branch(self, value: str):
        """Set HyperBEAM branch at runtime."""
        self._runtime_hb_branch = value
    
    @property
    def ao_branch(self) -> str:
        """AO branch (can be overridden at runtime)."""
        return self._runtime_ao_branch or self.build.ao_branch
    
    @ao_branch.setter
    def ao_branch(self, value: str):
        """Set AO branch at runtime."""
        self._runtime_ao_branch = value
    
    # ===================== Computed File Paths =====================
    
    @property
    def vm_image_base_name(self) -> str:
        """Base VM image filename."""
        return self.build.base_image
    
    @property
    def vm_image_base_path(self) -> str:
        """Full path to base VM image."""
        return os.path.join(self.dirs.guest, self.build.base_image)
    
    @property
    def vm_cloud_config(self) -> str:
        """Path to VM cloud config blob."""
        return os.path.join(self.dirs.guest, "config-blob.img")
    
    @property
    def vm_template_user_data(self) -> str:
        """Path to VM template user data."""
        return os.path.join(self.dirs.resources, "template-user-data")
    
    @property
    def kernel_deb(self) -> str:
        """Path pattern for kernel .deb package."""
        return os.path.join(self.dirs.snp, "linux", "guest", "linux-image-*.deb")
    
    @property
    def kernel_vmlinuz(self) -> str:
        """Path pattern for kernel vmlinuz."""
        return os.path.join(self.dirs.kernel, "boot", "vmlinuz-*")
    
    @property
    def ovmf(self) -> str:
        """Path to OVMF firmware."""
        return os.path.join(self.dirs.snp, "usr", "local", "share", "qemu", "DIRECT_BOOT_OVMF.fd")
    
    @property
    def initrd(self) -> str:
        """Path to initramfs image."""
        return os.path.join(self.dirs.build, "initramfs.cpio.gz")
    
    @property
    def initramfs_script(self) -> str:
        """Path to initramfs init script."""
        return os.path.join(self.dirs.scripts, "init.sh")
    
    @property
    def initramfs_dockerfile(self) -> str:
        """Path to initramfs Dockerfile."""
        return os.path.join(self.dirs.resources, "initramfs.Dockerfile")
    
    @property
    def content_dockerfile(self) -> str:
        """Path to content Dockerfile."""
        return os.path.join(self.dirs.resources, "content.Dockerfile")
    
    @property
    def vm_config_file(self) -> str:
        """Path to VM configuration file."""
        return os.path.join(self.dirs.guest, "vm-config.toml")
    
    @property
    def verity_image(self) -> str:
        """Path to verity image."""
        return os.path.join(self.dirs.verity, self.build.guest_image)
    
    @property
    def verity_hash_tree(self) -> str:
        """Path to verity hash tree."""
        return os.path.join(self.dirs.verity, "hash_tree.bin")
    
    @property
    def verity_root_hash(self) -> str:
        """Path to verity root hash file."""
        return os.path.join(self.dirs.verity, "roothash.txt")
    
    @property
    def ssh_hosts_file(self) -> str:
        """Path to SSH known hosts file."""
        return os.path.join(self.dirs.build, "known_hosts")
    
    @property
    def snp_amdsev_path(self) -> str:
        """Path to AMDSEV repository."""
        return os.path.join(self.dirs.build, "AMDSEV")
    
    # ===================== Computed Parameters =====================
    
    @property
    def debug(self) -> str:
        """Debug flag as string (for backward compatibility)."""
        return "1" if self.build.debug else "0"
    
    @property
    def enable_kvm(self) -> str:
        """KVM enable flag as string (for backward compatibility)."""
        return "1" if self.build.enable_kvm else "0"
    
    @property
    def enable_tpm(self) -> str:
        """TPM enable flag as string (for backward compatibility)."""
        return "1" if self.build.enable_tpm else "0"
    
    @property
    def vcpu_count(self) -> int:
        """Number of virtual CPUs."""
        return self.vm.vcpu_count
    
    @property
    def cmdline(self) -> str:
        """Kernel command line."""
        return self.vm.cmdline
    
    @property
    def guest_policy(self) -> str:
        """Guest policy setting."""
        return self.vm.guest_policy
    
    @property
    def host_cpu_family(self) -> str:
        """Host CPU family."""
        return self.vm.host_cpu_family
    
    @property
    def guest_features(self) -> str:
        """Guest features setting."""
        return self.vm.guest_features
    
    @property
    def platform_info(self) -> str:
        """Platform info setting."""
        return self.vm.platform_info
    
    @property
    def family_id(self) -> str:
        """Family ID."""
        return self.vm.family_id
    
    @property
    def image_id(self) -> str:
        """Image ID."""
        return self.vm.image_id
    
    @property
    def min_committed_tcb(self) -> Dict[str, Any]:
        """Minimum committed TCB configuration."""
        return {
            "bootloader": self.tcb.bootloader,
            "tee": self.tcb.tee,
            "snp": self.tcb.snp,
            "microcode": self.tcb.microcode,
            "_reserved": self.tcb.reserved,
        }
    
    @property
    def network_vm_host(self) -> str:
        """VM network host."""
        return self.network.vm_host
    
    @property
    def network_vm_port(self) -> str:
        """VM network port as string (for backward compatibility)."""
        return str(self.network.vm_port)
    
    @property
    def network_vm_user(self) -> str:
        """VM network user."""
        return self.network.vm_user
    
    @property
    def qemu_launch_script(self) -> str:
        """QEMU launch script path."""
        return self.qemu.launch_script
    
    @property
    def qemu_snp_params(self) -> str:
        """QEMU SNP parameters."""
        return self.qemu.snp_params
    
    @property
    def qemu_memory(self) -> str:
        """QEMU memory as string (for backward compatibility)."""
        return str(self.vm.memory_mb)
    
    @property
    def qemu_hb_port(self) -> str:
        """QEMU HyperBEAM port as string (for backward compatibility)."""
        return str(self.network.hb_port)
    
    @property
    def qemu_port(self) -> str:
        """QEMU port as string (for backward compatibility)."""
        return str(self.network.qemu_port)
    
    @property
    def qemu_ovmf(self) -> str:
        """QEMU OVMF path."""
        return self.ovmf
    
    @property
    def qemu_build_dir(self) -> str:
        """QEMU build directory."""
        return self.dirs.build
    
    @property
    def qemu_default_params(self) -> str:
        """Default QEMU parameters."""
        log_file = os.path.join(self.dirs.build, 'stdout.log')
        return (f"-default-network -log {log_file} "
                f"-mem {self.qemu_memory} -smp {self.vcpu_count} ")
    
    @property
    def qemu_extra_params(self) -> str:
        """Extra QEMU parameters."""
        return f"-bios {self.qemu_ovmf} -policy {self.guest_policy}"
    
    @property
    def snp_use_stable_snapshots(self) -> bool:
        """Whether to use stable SNP snapshots."""
        return self.snp.use_stable_snapshots
    
    @property
    def snp_amdsev_repo(self) -> str:
        """SNP AMDSEV repository URL."""
        return self.snp.amdsev_repo
    
    @property
    def snp_amdsev_branch(self) -> str:
        """SNP AMDSEV branch."""
        return self.snp.amdsev_branch
    
    @property
    def snp_dependencies(self) -> List[str]:
        """SNP build dependencies."""
        return self.snp.dependencies
    
    @property
    def verity_params(self) -> str:
        """
        Computes the verity parameters by reading the content of the root hash file.
        If the file does not exist or an error occurs, a placeholder value is used.
        """
        try:
            with open(self.verity_root_hash, "r") as f:
                roothash = f.read().strip()
        except Exception:
            roothash = "unknown"
        return f"boot=verity verity_disk=/dev/sdb verity_roothash={roothash}"
    
    # ===================== Backward Compatibility =====================
    
    @property
    def dir(self) -> DirectoryConfig:
        """Backward compatibility alias for directories."""
        return self.dirs


# Create the global configuration instance
config = HyperBeamConfig()