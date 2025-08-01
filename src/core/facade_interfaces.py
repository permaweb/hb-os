#!/usr/bin/env python3
"""
Facade Interfaces for Complex Operations.

This module defines high-level facade interfaces that simplify complex multi-step
workflows by providing simple, intuitive APIs for common use cases.
"""

from typing import Protocol, Optional, Dict, Any, runtime_checkable
from pathlib import Path


@runtime_checkable
class ISetupFacade(Protocol):
    """
    Facade for environment setup and initialization operations.
    
    Simplifies the complex process of setting up the HyperBEAM development environment.
    """
    
    def initialize_environment(self, force_dependencies: bool = False) -> None:
        """
        Initialize the complete build environment.
        
        This orchestrates:
        1. Creating necessary directories
        2. Installing system dependencies
        3. Downloading SNP release components
        4. Building attestation tools
        5. Setting up the host system
        
        Args:
            force_dependencies: Force reinstallation of dependencies
        """
        ...
    
    def setup_host_system(self) -> None:
        """
        Set up the host system for SNP operations.
        
        This configures the host system using the SNP release installer.
        """
        ...
    
    def verify_environment(self) -> bool:
        """
        Verify that the environment is properly configured.
        
        Returns:
            True if environment is ready, False otherwise
        """
        ...


@runtime_checkable
class IBuildFacade(Protocol):
    """
    Facade for build operations and orchestration.
    
    Simplifies the complex process of building VM images and components.
    """
    
    def build_complete_system(self, hb_branch: Optional[str] = None, 
                             ao_branch: Optional[str] = None,
                             amdsev_path: Optional[str] = None) -> None:
        """
        Build the complete HyperBEAM system from scratch.
        
        This orchestrates:
        1. Building SNP packages if needed
        2. Building base VM image
        3. Building guest image with content
        4. Generating all configuration files
        
        Args:
            hb_branch: HyperBEAM branch to use
            ao_branch: AO branch to use  
            amdsev_path: Optional local AMDSEV repository path
        """
        ...
    
    def build_snp_packages(self, amdsev_path: Optional[str] = None) -> None:
        """
        Build SNP packages (kernel, OVMF, QEMU) from source.
        
        Args:
            amdsev_path: Optional local AMDSEV repository path
        """
        ...
    
    def build_base_image(self) -> None:
        """
        Build the base VM image.
        
        This orchestrates:
        1. Unpacking the kernel
        2. Building initramfs
        3. Creating VM image
        4. Setting up VM configuration
        5. Generating hashes
        """
        ...
    
    def build_guest_image(self, hb_branch: Optional[str] = None,
                         ao_branch: Optional[str] = None) -> None:
        """
        Build the guest VM image with content.
        
        This orchestrates:
        1. Building guest content
        2. Setting up dm-verity
        3. Creating VM configuration  
        4. Generating hashes
        
        Args:
            hb_branch: HyperBEAM branch to use
            ao_branch: AO branch to use
        """
        ...
    
    def get_build_status(self) -> Dict[str, bool]:
        """
        Get the status of various build components.
        
        Returns:
            Dictionary mapping component names to their build status
        """
        ...


@runtime_checkable
class IVMFacade(Protocol):
    """
    Facade for VM lifecycle management operations.
    
    Simplifies VM creation, configuration, and management workflows.
    """
    
    def create_and_start_vm(self, data_disk: Optional[str] = None,
                           release_mode: bool = False) -> None:
        """
        Create and start a VM with intelligent defaults.
        
        Args:
            data_disk: Optional path to data disk image
            release_mode: Use release files instead of build files
        """
        ...
    
    def start_vm(self, data_disk: Optional[str] = None) -> None:
        """
        Start VM with guest image configuration.
        
        Args:
            data_disk: Optional path to data disk image
        """
        ...
    
    def start_release_vm(self, data_disk: Optional[str] = None) -> None:
        """
        Start VM in release mode using release folder files.
        
        Args:
            data_disk: Optional path to data disk image
        """
        ...
    
    def connect_to_vm(self) -> None:
        """SSH into the running virtual machine."""
        ...
    
    def get_vm_status(self) -> Dict[str, Any]:
        """
        Get the current status of VM components.
        
        Returns:
            Dictionary with VM status information
        """
        ...


@runtime_checkable
class IReleaseFacade(Protocol):
    """
    Facade for release management operations.
    
    Simplifies the process of packaging, distributing, and managing releases.
    """
    
    def create_release_package(self, output_path: Optional[str] = None) -> str:
        """
        Create a complete release package.
        
        This orchestrates:
        1. Packaging all required files
        2. Creating configuration files
        3. Generating release archive
        
        Args:
            output_path: Optional custom output path for the release
            
        Returns:
            Path to the created release package
        """
        ...
    
    def download_and_install_release(self, url: str, 
                                   verify_checksum: bool = True) -> None:
        """
        Download and install a release package.
        
        Args:
            url: URL to the release package
            verify_checksum: Whether to verify package integrity
        """
        ...
    
    def clean_build_artifacts(self, keep_downloads: bool = True) -> None:
        """
        Clean up build artifacts and temporary files.
        
        Args:
            keep_downloads: Whether to preserve downloaded files
        """
        ...
    
    def list_available_releases(self) -> Dict[str, Any]:
        """
        List information about available releases.
        
        Returns:
            Dictionary with release information
        """
        ...


@runtime_checkable
class IHyperBeamFacade(Protocol):
    """
    Main facade that orchestrates all HyperBEAM operations.
    
    This is the highest-level interface that provides simple workflows
    for the most common use cases.
    """
    
    def quick_setup(self, force: bool = False) -> None:
        """
        Perform a complete quick setup for development.
        
        This runs: initialize_environment -> build_complete_system
        
        Args:
            force: Force reinstallation of dependencies
        """
        ...
    
    def development_workflow(self, hb_branch: Optional[str] = None,
                           ao_branch: Optional[str] = None) -> None:
        """
        Complete development workflow: build and start VM.
        
        This runs: build_guest_image -> start_vm
        
        Args:
            hb_branch: HyperBEAM branch to use
            ao_branch: AO branch to use
        """
        ...
    
    def release_workflow(self, hb_branch: Optional[str] = None,
                        ao_branch: Optional[str] = None) -> str:
        """
        Complete release workflow: build and package.
        
        This runs: build_complete_system -> create_release_package
        
        Args:
            hb_branch: HyperBEAM branch to use
            ao_branch: AO branch to use
            
        Returns:
            Path to created release package
        """
        ...
    
    def demo_workflow(self, release_url: Optional[str] = None) -> None:
        """
        Demo workflow for showcasing HyperBEAM.
        
        This either downloads a release or uses existing build,
        then starts the VM for demonstration.
        
        Args:
            release_url: Optional URL to download demo release
        """
        ...
    
    def get_system_status(self) -> Dict[str, Any]:
        """
        Get comprehensive system status.
        
        Returns:
            Dictionary with complete system status information
        """
        ...
    
    def print_status_report(self) -> None:
        """
        Print a comprehensive status report.
        """
        ...