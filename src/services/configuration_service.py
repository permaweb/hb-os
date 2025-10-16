#!/usr/bin/env python3
"""
Configuration Service Implementation.

This service wraps the existing HyperBeamConfig and provides it as an injectable dependency.
"""

from typing import Optional
from config import HyperBeamConfig
from src.core.service_interfaces import IConfigurationService


class ConfigurationService(IConfigurationService):
    """Injectable configuration service that wraps HyperBeamConfig."""
    
    def __init__(self, config: HyperBeamConfig):
        self._config = config
    
    # Directory properties
    @property
    def build_dir(self) -> str:
        return self._config.dirs.build
    
    @property 
    def guest_dir(self) -> str:
        return self._config.dirs.guest
    
    @property
    def content_dir(self) -> str:
        return self._config.dirs.content
    
    @property
    def kernel_dir(self) -> str:
        return self._config.dirs.kernel
    
    # File path properties
    @property
    def verity_image(self) -> str:
        return self._config.verity_image
    
    @property
    def verity_hash_tree(self) -> str:
        return self._config.verity_hash_tree
    
    @property
    def vm_config_file(self) -> str:
        return self._config.vm_config_file
    
    @property
    def kernel_vmlinuz(self) -> str:
        return self._config.kernel_vmlinuz
    
    @property
    def initrd(self) -> str:
        return self._config.initrd
    
    # VM configuration properties
    @property
    def vcpu_count(self) -> int:
        return self._config.vcpu_count
    
    @property
    def debug(self) -> str:
        return self._config.debug
    
    @property
    def enable_kvm(self) -> str:
        return self._config.enable_kvm
    
    @property
    def enable_tpm(self) -> str:
        return self._config.enable_tpm
    
    @property
    def enable_gpu(self) -> str:
        return self._config.enable_gpu
    
    # Network properties
    @property
    def network_vm_host(self) -> str:
        return self._config.network_vm_host
    
    @property
    def network_vm_port(self) -> str:
        return self._config.network_vm_port
    
    @property
    def network_vm_user(self) -> str:
        return self._config.network_vm_user
    
    # Branch properties
    @property
    def hb_branch(self) -> str:
        return self._config.hb_branch
    
    @property
    def ao_branch(self) -> str:
        return self._config.ao_branch
    
    # Provide access to underlying config for complex operations
    @property
    def config(self) -> HyperBeamConfig:
        return self._config