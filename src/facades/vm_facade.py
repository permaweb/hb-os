#!/usr/bin/env python3
"""
VM Facade Implementation.

This facade simplifies VM lifecycle management operations.
"""

import os
from typing import Optional, Dict, Any
from src.core.facade_interfaces import IVMFacade
from src.core.service_interfaces import IConfigurationService, IVMService


class VMFacade(IVMFacade):
    """
    Facade for VM lifecycle management operations.
    
    Provides high-level methods for VM creation, configuration, and management.
    """
    
    def __init__(self, config_service: IConfigurationService, vm_service: IVMService):
        """
        Initialize VMFacade with injected dependencies.
        
        Args:
            config_service: Configuration service for accessing settings
            vm_service: VM service for VM operations
        """
        self._config = config_service
        self._vm = vm_service
    
    def create_and_start_vm(self, data_disk: Optional[str] = None,
                           release_mode: bool = False) -> None:
        """
        Create and start a VM with intelligent defaults.
        
        This provides a simplified interface for starting VMs with sensible defaults.
        
        Args:
            data_disk: Optional path to data disk image
            release_mode: Use release files instead of build files
        """
        print("🚀 Starting VM with intelligent defaults...")
        
        # Choose VM start method based on release mode
        if release_mode:
            print("📦 Starting VM in release mode...")
            self.start_release_vm(data_disk)
        else:
            print("🔨 Starting VM with build artifacts...")
            self.start_vm(data_disk)
        
        print("✅ VM started successfully!")
        
        if data_disk:
            print(f"💾 Data disk: {data_disk}")
    
    def start_vm(self, data_disk: Optional[str] = None) -> None:
        """
        Start VM with guest image configuration.
        
        Args:
            data_disk: Optional path to data disk image
        """
        print("🔨 Starting VM with guest image configuration...")
        
        # Validate that required files exist
        self._validate_vm_files()
        
        self._vm.start_vm(data_disk=data_disk)
    
    def start_release_vm(self, data_disk: Optional[str] = None) -> None:
        """
        Start VM in release mode using release folder files.
        
        Args:
            data_disk: Optional path to data disk image
        """
        print("📦 Starting VM in release mode...")
        
        # Validate that release files exist
        self._validate_release_files()
        
        self._vm.start_release_vm(data_disk=data_disk)
    
    def connect_to_vm(self) -> None:
        """SSH into the running virtual machine."""
        print("🔌 Connecting to VM via SSH...")
        self._vm.ssh_vm()
    
    def get_vm_status(self) -> Dict[str, Any]:
        """
        Get the current status of VM components.
        
        Returns:
            Dictionary with VM status information
        """
        status = {
            'build_files': {},
            'release_files': {},
            'configuration': {},
            'network': {}
        }
        
        # Check build files
        status['build_files']['verity_image'] = os.path.exists(self._config.verity_image)
        status['build_files']['verity_hash_tree'] = os.path.exists(self._config.verity_hash_tree)
        status['build_files']['vm_config'] = os.path.exists(self._config.vm_config_file)
        status['build_files']['kernel'] = os.path.exists(self._config.kernel_vmlinuz)
        status['build_files']['initrd'] = os.path.exists(self._config.initrd)
        
        # Check release files
        release_dir = os.path.join(os.getcwd(), "release")
        if os.path.exists(release_dir):
            status['release_files']['directory'] = True
            status['release_files']['verity_image'] = os.path.exists(
                os.path.join(release_dir, os.path.basename(self._config.verity_image))
            )
            status['release_files']['verity_hash_tree'] = os.path.exists(
                os.path.join(release_dir, os.path.basename(self._config.verity_hash_tree))
            )
            status['release_files']['vm_config'] = os.path.exists(
                os.path.join(release_dir, os.path.basename(self._config.vm_config_file))
            )
        else:
            status['release_files']['directory'] = False
        
        # Configuration status
        status['configuration']['vcpu_count'] = self._config.vcpu_count
        status['configuration']['debug_mode'] = self._config.debug == "1"
        status['configuration']['kvm_enabled'] = self._config.enable_kvm == "1"
        status['configuration']['tpm_enabled'] = self._config.enable_tpm == "1"
        
        # Network configuration
        status['network']['host'] = self._config.network_vm_host
        status['network']['port'] = self._config.network_vm_port
        status['network']['user'] = self._config.network_vm_user
        
        # Overall readiness
        status['ready_for_start'] = all(status['build_files'].values())
        status['ready_for_release'] = all(status['release_files'].values()) if status['release_files']['directory'] else False
        
        return status
    
    def _validate_vm_files(self) -> None:
        """Validate that required VM files exist for normal start."""
        required_files = {
            'Verity image': self._config.verity_image,
            'Verity hash tree': self._config.verity_hash_tree,
            'VM configuration': self._config.vm_config_file,
            'Kernel': self._config.kernel_vmlinuz,
            'Initrd': self._config.initrd
        }
        
        missing_files = []
        for name, path in required_files.items():
            if not os.path.exists(path):
                missing_files.append(f"{name} ({path})")
        
        if missing_files:
            raise FileNotFoundError(
                f"Missing required VM files:\n" + 
                "\n".join(f"  - {f}" for f in missing_files) +
                "\n\nPlease run build_guest_image first."
            )
    
    def _validate_release_files(self) -> None:
        """Validate that required release files exist for release mode start."""
        release_dir = os.path.join(os.getcwd(), "release")
        
        if not os.path.exists(release_dir):
            raise FileNotFoundError(
                f"Release directory not found: {release_dir}\n"
                "Please run package_release first or download a release package."
            )
        
        required_files = {
            'Verity image': os.path.join(release_dir, os.path.basename(self._config.verity_image)),
            'Verity hash tree': os.path.join(release_dir, os.path.basename(self._config.verity_hash_tree)),
            'VM configuration': os.path.join(release_dir, os.path.basename(self._config.vm_config_file))
        }
        
        missing_files = []
        for name, path in required_files.items():
            if not os.path.exists(path):
                missing_files.append(f"{name} ({path})")
        
        if missing_files:
            raise FileNotFoundError(
                f"Missing required release files:\n" + 
                "\n".join(f"  - {f}" for f in missing_files) +
                "\n\nPlease ensure the release package is complete."
            )