#!/usr/bin/env python3
"""
Service Interfaces for Dependency Injection.

This module defines the contracts (interfaces) that service implementations must follow.
Using protocols allows for flexible implementations while maintaining type safety.
"""

from typing import Protocol, Optional, Dict, Any, List, Union, runtime_checkable
from pathlib import Path
from subprocess import CompletedProcess
from contextlib import contextmanager


@runtime_checkable
class IConfigurationService(Protocol):
    """Interface for configuration management services."""
    
    # Directory properties
    @property
    def build_dir(self) -> str: ...
    
    @property 
    def guest_dir(self) -> str: ...
    
    @property
    def content_dir(self) -> str: ...
    
    @property
    def kernel_dir(self) -> str: ...
    
    # File path properties
    @property
    def verity_image(self) -> str: ...
    
    @property
    def verity_hash_tree(self) -> str: ...
    
    @property
    def vm_config_file(self) -> str: ...
    
    @property
    def kernel_vmlinuz(self) -> str: ...
    
    @property
    def initrd(self) -> str: ...
    
    # VM configuration properties
    @property
    def vcpu_count(self) -> int: ...
    
    @property
    def debug(self) -> str: ...
    
    @property
    def enable_kvm(self) -> str: ...
    
    @property
    def enable_tpm(self) -> str: ...
    
    # Network properties
    @property
    def network_vm_host(self) -> str: ...
    
    @property
    def network_vm_port(self) -> str: ...
    
    @property
    def network_vm_user(self) -> str: ...
    
    # Branch properties
    @property
    def hb_branch(self) -> str: ...
    
    @property
    def ao_branch(self) -> str: ...


@runtime_checkable
class ICommandExecutionService(Protocol):
    """Interface for command execution services."""
    
    def run_command(self, cmd: Union[str, List[str]], cwd: Optional[str] = None, 
                   check: bool = True, shell: bool = True, ignore_errors: bool = False, 
                   capture_output: bool = False) -> CompletedProcess: ...
    
    def run_command_silent(self, cmd: Union[str, List[str]], cwd: Optional[str] = None, 
                          check: bool = False) -> CompletedProcess: ...


@runtime_checkable
class IDockerService(Protocol):
    """Interface for Docker operation services."""
    
    def build_image(self, context_dir: Union[str, Path], dockerfile_name: str, 
                   image_name: str, build_args: Optional[Dict[str, str]] = None) -> str: ...
    
    def run_container(self, image_name: str, container_name: str, command: str = "sleep 3600", 
                     additional_args: Optional[List[str]] = None) -> str: ...
    
    def stop_container(self, container_name: str, ignore_errors: bool = False) -> None: ...
    
    def copy_from_container(self, container_name: str, src_path: str, 
                           dest_path: Union[str, Path]) -> None: ...
    
    def export_filesystem(self, container_name: str, dest_dir: Union[str, Path]) -> None: ...
    
    @contextmanager
    def managed_container(self, image_name: str, container_name: str, 
                         command: str = "sleep 3600", 
                         additional_args: Optional[List[str]] = None): ...


@runtime_checkable  
class IFileSystemService(Protocol):
    """Interface for file system operation services."""
    
    def ensure_directory(self, path: str) -> None: ...
    
    def remove_directory(self, path: str) -> None: ...
    
    def ensure_parent_directory(self, file_path: str) -> None: ...
    
    def replace_in_file(self, file_path: str, replacements: Dict[str, str]) -> None: ...


@runtime_checkable
class IVMService(Protocol):
    """Interface for VM management services."""
    
    def start_vm(self, data_disk: Optional[str] = None, enable_ssl: bool = False) -> None: ...
    
    def start_release_vm(self, data_disk: Optional[str] = None, enable_ssl: bool = False) -> None: ...
    
    def ssh_vm(self) -> None: ...


@runtime_checkable
class IDependencyService(Protocol):
    """Interface for dependency installation services."""
    
    def install_dependencies(self, force: bool = False) -> None: ...
    
    def check_distro(self) -> None: ...
    
    def check_root(self) -> None: ...
    
    def check_sudo(self) -> None: ...


@runtime_checkable
class IBuildService(Protocol):
    """Interface for build operation services."""
    
    def build_base_image(self) -> None: ...
    
    def build_guest_image(self) -> None: ...
    
    def build_guest_content(self, out_dir: str, dockerfile: str, hb_branch: str, ao_branch: str, debug: bool = False) -> None: ...
    
    def build_initramfs(self, kernel_dir: str, init_script: str, dockerfile: str, 
                       context_dir: str, build_dir: str, init_patch: Optional[str] = None, 
                       out: Optional[str] = None) -> None: ...
    
    def setup_verity(self) -> None: ...
    
    def create_vm_config(self) -> None: ...
    
    def get_hashes(self) -> None: ...


@runtime_checkable
class IReleaseService(Protocol):
    """Interface for release management services."""
    
    def package_release(self) -> None: ...
    
    def download_release(self, url: str) -> None: ...
    
    def clean(self) -> None: ...