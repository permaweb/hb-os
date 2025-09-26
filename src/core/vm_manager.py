#!/usr/bin/env python3
"""
VM management functionality - refactored to eliminate code duplication.
Provides unified VM launching with support for both guest and release modes.
"""

import os
import json
from typing import Optional, Dict, Any
from src.core.service_interfaces import IConfigurationService, ICommandExecutionService, IVMService
from src.utils import QEMUCommandBuilder


class VMLauncher:
    """
    Handles VM launching with configurable file paths and parameters.
    Eliminates duplication between guest and release mode launches.
    """
    
    def __init__(self, config_service: IConfigurationService, command_service: ICommandExecutionService):
        """
        Initialize VMLauncher with injected dependencies.
        
        Args:
            config_service: Configuration service for accessing settings
            command_service: Command execution service for running QEMU
        """
        self._config = config_service
        self._command_service = command_service
    

    

    
    def _build_complete_command(self, verity_image: str, verity_hash_tree: str, vm_config_file: str, 
                               data_disk: Optional[str] = None, enable_ssl: bool = False) -> str:
        """
        Build the complete QEMU command with all parameters.
        
        Args:
            verity_image: Path to verity image file
            verity_hash_tree: Path to verity hash tree file
            vm_config_file: Path to VM configuration file
            data_disk: Data disk path
            enable_ssl: Whether to enable SSL port forwarding
            
        Returns:
            Complete command string
        """
        builder = (QEMUCommandBuilder(self._config.config.qemu_launch_script)
                   .args(*self._config.config.qemu_default_params.split())
                   .args(*self._config.config.qemu_snp_params.split())
                   .hda(verity_image)
                   .hdb(verity_hash_tree)
                   .load_config(vm_config_file)
                   .hb_port(self._config.config.qemu_hb_port)
                   .qemu_port(self._config.config.qemu_port)
                   .debug(self._config.debug)
                   .enable_kvm(self._config.enable_kvm)
                   .enable_tpm(self._config.enable_tpm))
        
        # Add optional parameters conditionally
        if data_disk:
            builder.data_disk(data_disk)
        
        if enable_ssl:
            builder.enable_ssl(enable_ssl)
        
        return builder.build()
    
    def launch(self, verity_image: str, verity_hash_tree: str, vm_config_file: str, 
               data_disk: Optional[str] = None, enable_ssl: bool = False) -> None:
        """
        Launch VM with specified configuration files and parameters.
        
        Args:
            verity_image: Path to verity image file
            verity_hash_tree: Path to verity hash tree file  
            vm_config_file: Path to VM configuration file
            data_disk: Path to data disk image
            enable_ssl: Whether to enable SSL port forwarding
        """
        # Build complete command with all parameters
        cmd = self._build_complete_command(verity_image, verity_hash_tree, vm_config_file, data_disk, enable_ssl)
        
        # Execute the command
        self._command_service.run_command(cmd)


class VMService(IVMService):
    """Injectable VM service that provides VM management operations."""
    
    def __init__(self, config_service: IConfigurationService, command_service: ICommandExecutionService):
        """
        Initialize VMService with injected dependencies.
        
        Args:
            config_service: Configuration service for accessing settings
            command_service: Command execution service for running commands
        """
        self._launcher = VMLauncher(config_service, command_service)
        self._config = config_service
        self._command_service = command_service
    
    def start_vm(self, data_disk: Optional[str] = None, enable_ssl: bool = False) -> None:
        """
        Run the VM using QEMU with the guest image configuration.
        
        Args:
            data_disk: Optional path to a data disk image
            enable_ssl: Whether to enable SSL port forwarding
        """
        self._launcher.launch(
            verity_image=self._config.verity_image,
            verity_hash_tree=self._config.verity_hash_tree,
            vm_config_file=self._config.vm_config_file,
            data_disk=data_disk,
            enable_ssl=enable_ssl
        )
    
    def start_release_vm(self, data_disk: Optional[str] = None, enable_ssl: bool = False) -> None:
        """
        Start the VM in release mode, using files from the release folder.
        
        Args:
            data_disk: Optional path to a data disk image
            enable_ssl: Whether to enable SSL port forwarding
        """
        release_dir = os.path.join(os.getcwd(), "release")
        verity_image = os.path.join(release_dir, os.path.basename(self._config.verity_image))
        verity_hash_tree = os.path.join(release_dir, os.path.basename(self._config.verity_hash_tree))
        vm_config_file = os.path.join(release_dir, os.path.basename(self._config.vm_config_file))
        
        self._launcher.launch(
            verity_image=verity_image,
            verity_hash_tree=verity_hash_tree,
            vm_config_file=vm_config_file,
            data_disk=data_disk,
            enable_ssl=enable_ssl
        )
    
    def ssh_vm(self) -> None:
        """SSH into the virtual machine."""
        self._command_service.run_command(
            f"ssh -p {self._config.network_vm_port} -o UserKnownHostsFile={self._config.config.ssh_hosts_file} {self._config.network_vm_user}@{self._config.network_vm_host}"
        )


# Legacy functions for backward compatibility - these will be removed later
def start_vm(data_disk: Optional[str] = None, enable_ssl: bool = False) -> None:
    """
    Run the VM using QEMU with the guest image configuration.
    
    Args:
        data_disk: Optional path to a data disk image
        enable_ssl: Whether to enable SSL port forwarding
    """
    from src.core.service_factory import get_service_container
    container = get_service_container()
    vm_service = container.resolve(IVMService)
    vm_service.start_vm(data_disk=data_disk, enable_ssl=enable_ssl)


def start_release_vm(data_disk: Optional[str] = None, enable_ssl: bool = False) -> None:
    """
    Start the VM in release mode, using files from the release folder.
    
    Args:
        data_disk: Optional path to a data disk image
        enable_ssl: Whether to enable SSL port forwarding
    """
    from src.core.service_factory import get_service_container
    container = get_service_container()
    vm_service = container.resolve(IVMService)
    vm_service.start_release_vm(data_disk=data_disk, enable_ssl=enable_ssl)


def ssh_vm() -> None:
    """
    SSH into the virtual machine.
    """
    from src.core.service_factory import get_service_container
    container = get_service_container()
    vm_service = container.resolve(IVMService)
    vm_service.ssh_vm()