#!/usr/bin/env python3
"""
SNP Configuration Management

Configuration settings for SNP component repositories, branches, and build options.
Converted from convert/stable-commits and related configuration.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class SNPRepositoryConfig:
    """Configuration for SNP component repositories."""
    
    # Kernel repository configuration
    kernel_git_url: str = "https://github.com/AMDESE/linux.git"
    kernel_host_branch: str = "snp-host-v15"
    kernel_guest_branch: str = "snp-guest-req-v3"
    
    # QEMU repository configuration
    qemu_git_url: str = "https://github.com/AMDESE/qemu.git"
    qemu_branch: str = "snp-latest"
    
    # OVMF repository configuration
    ovmf_git_url: str = "https://github.com/AMDESE/ovmf.git"
    ovmf_branch: str = "snp-latest"
    
    # Optional kernel config templates
    kernel_host_config_template: Optional[str] = None
    kernel_guest_config_template: Optional[str] = None


@dataclass
class KernelBuildConfig:
    """Kernel-specific build configuration."""
    
    # Default kernel configurations to apply
    config_options: Dict[str, str] = None
    
    def __post_init__(self):
        if self.config_options is None:
            self.config_options = {
                # Core SEV/SNP options
                "EXPERT": "enable",
                "DEBUG_INFO": "enable", 
                "DEBUG_INFO_REDUCED": "enable",
                "AMD_MEM_ENCRYPT": "enable",
                "AMD_MEM_ENCRYPT_ACTIVE_BY_DEFAULT": "disable",
                "KVM_AMD_SEV": "enable",
                "CRYPTO_DEV_CCP_DD": "module",
                "SYSTEM_TRUSTED_KEYS": "disable",
                "SYSTEM_REVOCATION_KEYS": "disable", 
                "MODULE_SIG_KEY": "disable",
                "SEV_GUEST": "module",
                "IOMMU_DEFAULT_PASSTHROUGH": "disable",
                
                # Preemption settings
                "PREEMPT_COUNT": "disable",
                "PREEMPTION": "disable",
                "PREEMPT_DYNAMIC": "disable",
                "DEBUG_PREEMPT": "disable",
                
                # Control groups and CPU features
                "CGROUP_MISC": "enable",
                "X86_CPUID": "module",
                "UBSAN": "disable",
                "RCU_EXP_CPU_STALL_TIMEOUT": "1000",
                
                # Mellanox networking
                "MLX4_EN": "module",
                "MLX4_EN_DCB": "enable",
                "MLX4_CORE": "module", 
                "MLX4_DEBUG": "enable",
                "MLX4_CORE_GEN2": "enable",
                "MLX5_CORE": "module",
                "MLX5_FPGA": "enable",
                "MLX5_CORE_EN": "enable",
                "MLX5_EN_ARFS": "enable",
                "MLX5_EN_RXNFC": "enable",
                "MLX5_MPFS": "enable",
                "MLX5_ESWITCH": "enable",
                "MLX5_BRIDGE": "enable",
                "MLX5_CLS_ACT": "enable",
                "MLX5_TC_CT": "enable",
                "MLX5_TC_SAMPLE": "enable",
                "MLX5_CORE_EN_DCB": "enable",
                "MLX5_CORE_IPOIB": "enable",
                "MLX5_SW_STEERING": "enable",
                "MLXSW_CORE": "module",
                "MLXSW_CORE_HWMON": "enable",
                "MLXSW_CORE_THERMAL": "enable",
                "MLXSW_PCI": "module",
                "MLXSW_I2C": "module",
                "MLXSW_SPECTRUM": "module",
                "MLXSW_SPECTRUM_DCB": "enable",
                "MLXSW_MINIMAL": "module",
                "MLXFW": "module",
                
                # Cryptography
                "CRYPTO_ECC": "enable",
                "CRYPTO_ECDH": "enable", 
                "CRYPTO_ECDSA": "enable",
            }


@dataclass
class OVMFBuildConfig:
    """OVMF-specific build configuration."""
    
    # Build command template
    build_args: List[str] = None
    
    def __post_init__(self):
        if self.build_args is None:
            self.build_args = [
                "-q",  # Quiet mode
                "--cmd-len=64436",
                "-DDEBUG_ON_SERIAL_PORT=TRUE", 
                "-DTPM_ENABLE=TRUE",
                "-DTPM2_ENABLE=TRUE",
                "-DTPM2_CONFIG_ENABLE=TRUE",   # Enable TPM2 configuration
                "-a", "X64",  # Architecture
                "-p", "OvmfPkg/AmdSev/AmdSevX64.dsc"  # Platform description
            ]


@dataclass
class QEMUBuildConfig:
    """QEMU-specific build configuration."""
    
    # Configure options
    configure_args: List[str] = None
    
    def __post_init__(self):
        if self.configure_args is None:
            self.configure_args = [
                "--target-list=x86_64-softmmu"
            ]


@dataclass 
class KVMModuleConfig:
    """KVM module configuration for SEV support."""
    
    # Module options for enabling SEV support
    module_options: Dict[str, str] = None
    
    def __post_init__(self):
        if self.module_options is None:
            self.module_options = {
                "sev-snp": "1",
                "sev": "1", 
                "sev-es": "1"
            }
    
    def to_conf_content(self) -> str:
        """Generate kvm.conf file content."""
        lines = [
            "###",
            "### Set these options to enable the SEV support", 
            "###",
            "",
            "# Enable SEV Support"
        ]
        
        option_parts = []
        for key, value in self.module_options.items():
            option_parts.append(f"{key}={value}")
        
        lines.append(f"options kvm_amd {' '.join(option_parts)}")
        return "\n".join(lines) + "\n"


class SNPConfigManager:
    """Manager for all SNP-related configurations."""
    
    def __init__(self):
        self.repository = SNPRepositoryConfig()
        self.kernel = KernelBuildConfig()
        self.ovmf = OVMFBuildConfig()
        self.qemu = QEMUBuildConfig()
        self.kvm = KVMModuleConfig()
    
    def get_default_kernel_config_path(self) -> str:
        """Get the default kernel config template path."""
        import os
        return f"/boot/config-{os.uname().release}"
    
    def get_kernel_config_path(self, kernel_type: str) -> str:
        """Get kernel config path for host or guest."""
        if kernel_type == "host" and self.repository.kernel_host_config_template:
            return self.repository.kernel_host_config_template
        elif kernel_type == "guest" and self.repository.kernel_guest_config_template:
            return self.repository.kernel_guest_config_template
        else:
            return self.get_default_kernel_config_path()
    
    def get_kernel_branch(self, kernel_type: str) -> str:
        """Get the appropriate kernel branch for host or guest."""
        if kernel_type == "guest":
            return self.repository.kernel_guest_branch
        else:
            return self.repository.kernel_host_branch