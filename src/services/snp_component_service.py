#!/usr/bin/env python3
"""
SNP Component Service

Service interface for building SNP components (kernel, OVMF, QEMU).
Provides a clean API for the SNP build functionality.
"""

import os
from typing import Dict, List, Optional, Any
from pathlib import Path
import shutil
from src.core.snp_builder import SNPBuildOrchestrator, SNPComponentBuilder, SNPBuildError
from src.utils.snp_config import SNPConfigManager
from src.utils import HyperBeamError


class SNPComponentService:
    """Service for managing SNP component builds."""
    
    def __init__(self, config_manager: Optional[SNPConfigManager] = None):
        """
        Initialize SNP component service.
        
        Args:
            config_manager: Optional SNP configuration manager
        """
        self.config = config_manager or SNPConfigManager()
        self.orchestrator = SNPBuildOrchestrator(self.config)
        self.builder = SNPComponentBuilder(self.config)
    
    def build_kernel(self, kernel_type: Optional[str] = None, 
                    build_dir: str = ".", output_dir: Optional[str] = None) -> List[str]:
        """
        Build SNP-enabled kernel packages.
        
        Args:
            kernel_type: 'host', 'guest', or None for both
            build_dir: Directory to build in
            output_dir: Directory to copy packages to (optional)
            
        Returns:
            List of built package file paths
            
        Raises:
            SNPBuildError: If kernel build fails
        """
        try:
            packages = self.builder.build_kernel(kernel_type, build_dir)
            
            # Copy packages to output directory if specified
            if output_dir and packages:
                os.makedirs(output_dir, exist_ok=True)
                copied_packages = []
                
                for package_path in packages:
                    package_name = os.path.basename(package_path)
                    dest_path = os.path.join(output_dir, package_name)
                    
                    shutil.copy2(package_path, dest_path)
                    copied_packages.append(dest_path)
                
                return copied_packages
            
            return packages
            
        except Exception as e:
            if isinstance(e, SNPBuildError):
                raise
            raise SNPBuildError(f"Kernel build failed: {str(e)}", "kernel", "build", e)
    
    def build_ovmf(self, install_dir: str, build_dir: str = ".") -> str:
        """
        Build OVMF firmware.
        
        Args:
            install_dir: Directory to install OVMF
            build_dir: Directory to build in
            
        Returns:
            Path to built OVMF file
            
        Raises:
            SNPBuildError: If OVMF build fails
        """
        try:
            return self.builder.build_ovmf(install_dir, build_dir)
        except Exception as e:
            if isinstance(e, SNPBuildError):
                raise
            raise SNPBuildError(f"OVMF build failed: {str(e)}", "ovmf", "build", e)
    
    def build_qemu(self, install_dir: str, build_dir: str = ".") -> str:
        """
        Build QEMU hypervisor.
        
        Args:
            install_dir: Directory to install QEMU
            build_dir: Directory to build in
            
        Returns:
            Path to QEMU installation directory
            
        Raises:
            SNPBuildError: If QEMU build fails
        """
        try:
            return self.builder.build_qemu(install_dir, build_dir)
        except Exception as e:
            if isinstance(e, SNPBuildError):
                raise
            raise SNPBuildError(f"QEMU build failed: {str(e)}", "qemu", "build", e)
    
    def build_all_components(self, install_dir: str, build_dir: str = ".",
                           kernel_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Build all SNP components (kernel, OVMF, QEMU).
        
        Args:
            install_dir: Directory to install components
            build_dir: Directory to build in
            kernel_type: Specific kernel type ('host', 'guest') or None for both
            
        Returns:
            Dictionary containing build results and paths
            
        Raises:
            SNPBuildError: If any component build fails
        """
        try:
            return self.orchestrator.build_all_components(install_dir, build_dir, kernel_type)
        except Exception as e:
            if isinstance(e, SNPBuildError):
                raise
            raise SNPBuildError(f"Component build failed: {str(e)}", "all", "build", e)
    
    def create_release_package(self, build_dir: str = ".", 
                             install_dir: Optional[str] = None) -> str:
        """
        Create a release package tarball with all built components.
        
        Args:
            build_dir: Build directory containing components
            install_dir: Installation directory (optional)
            
        Returns:
            Path to created tarball
            
        Raises:
            SNPBuildError: If package creation fails
        """
        try:
            return self.orchestrator.create_release_package(build_dir, install_dir)
        except Exception as e:
            if isinstance(e, SNPBuildError):
                raise
            raise SNPBuildError(f"Release package creation failed: {str(e)}", "package", "create", e)
    
    def create_kvm_config(self, output_path: str) -> str:
        """
        Create KVM module configuration file for SEV support.
        
        Args:
            output_path: Path to write the kvm.conf file
            
        Returns:
            Path to created config file
            
        Raises:
            SNPBuildError: If config creation fails
        """
        try:
            return self.builder.create_kvm_config(output_path)
        except Exception as e:
            raise SNPBuildError(f"KVM config creation failed: {str(e)}", "kvm", "config", e)
    
    def get_build_status(self, build_dir: str = ".") -> Dict[str, Any]:
        """
        Get status of SNP component builds.
        
        Args:
            build_dir: Build directory to check
            
        Returns:
            Dictionary with component build status
        """
        status = {
            "build_directory": os.path.abspath(build_dir),
            "components": {},
            "source_commits": {},
            "packages": {}
        }
        
        build_path = Path(build_dir)
        
        # Check for source commit files
        for commit_file in build_path.glob("source-commit.*"):
            component = commit_file.name.replace("source-commit.", "")
            try:
                with open(commit_file, 'r') as f:
                    commit_hash = f.read().strip()
                status["source_commits"][component] = commit_hash
            except:
                status["source_commits"][component] = "unknown"
        
        # Check for built packages
        linux_dir = build_path / "linux"
        if linux_dir.exists():
            # Debian packages
            deb_packages = list(linux_dir.glob("*.deb"))
            if deb_packages:
                status["packages"]["debian"] = [str(p) for p in deb_packages]
            
            # RPM packages  
            rpm_packages = list(linux_dir.glob("*.rpm"))
            if rpm_packages:
                status["packages"]["rpm"] = [str(p) for p in rpm_packages]
        
        # Check for QEMU installation
        qemu_path = build_path / "usr" / "local" / "bin" / "qemu-system-x86_64"
        status["components"]["qemu"] = {
            "built": qemu_path.exists(),
            "path": str(qemu_path) if qemu_path.exists() else None
        }
        
        # Check for OVMF installation
        ovmf_path = build_path / "usr" / "local" / "share" / "qemu" / "DIRECT_BOOT_OVMF.fd"
        status["components"]["ovmf"] = {
            "built": ovmf_path.exists(),
            "path": str(ovmf_path) if ovmf_path.exists() else None
        }
        
        # Check for KVM config
        kvm_config_path = build_path / "kvm.conf"
        status["components"]["kvm_config"] = {
            "built": kvm_config_path.exists(),
            "path": str(kvm_config_path) if kvm_config_path.exists() else None
        }
        
        return status
    
    def validate_build_environment(self) -> Dict[str, Any]:
        """
        Validate that the build environment has necessary dependencies.
        
        Returns:
            Dictionary with validation results
        """
        validation = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "dependencies": {}
        }
        
        # Check required tools
        required_tools = [
            "git", "make", "gcc", "python3", "tar", "gzip"
        ]
        
        for tool in required_tools:
            try:
                tool_path = shutil.which(tool)
                validation["dependencies"][tool] = {
                    "available": tool_path is not None,
                    "path": tool_path
                }
                
                if not tool_path:
                    validation["valid"] = False
                    validation["errors"].append(f"Required tool '{tool}' not found in PATH")
                    
            except Exception as e:
                validation["valid"] = False
                validation["errors"].append(f"Error checking tool '{tool}': {str(e)}")
        
        # Check for kernel build dependencies (Debian-based)
        if self.builder._is_debian_based():
            kernel_deps = [
                "build-essential", "bc", "kmod", "cpio", "flex", "bison", 
                "libssl-dev", "libelf-dev", "libudev-dev", "libpci-dev",
                "libiberty-dev", "autoconf"
            ]
            
            # Note: We can't easily check for installed packages without dpkg,
            # so we'll just warn about them
            validation["warnings"].append(
                f"Ensure these Debian packages are installed: {', '.join(kernel_deps)}"
            )
        
        return validation
    
    def clean_build_artifacts(self, build_dir: str = ".", 
                            keep_packages: bool = False) -> None:
        """
        Clean build artifacts and temporary files.
        
        Args:
            build_dir: Build directory to clean
            keep_packages: Whether to keep built packages
        """
        build_path = Path(build_dir)
        
        # Directories to clean
        clean_dirs = ["linux", "ovmf", "qemu"]
        
        for dir_name in clean_dirs:
            dir_path = build_path / dir_name
            if dir_path.exists():
                print(f"Cleaning {dir_path}")
                shutil.rmtree(dir_path)
        
        # Files to clean
        if not keep_packages:
            # Remove package files
            for pattern in ["*.deb", "*.rpm", "*.tar.gz"]:
                for file_path in build_path.glob(pattern):
                    print(f"Removing {file_path}")
                    file_path.unlink()
        
        # Remove commit files
        for commit_file in build_path.glob("source-commit.*"):
            commit_file.unlink()
        
        # Remove other build artifacts
        other_files = ["kvm.conf"]
        for filename in other_files:
            file_path = build_path / filename
            if file_path.exists():
                file_path.unlink()
        
        print("✅ Build artifacts cleaned")


def get_snp_component_service(config_manager: Optional[SNPConfigManager] = None) -> SNPComponentService:
    """
    Factory function to get SNP component service instance.
    
    Args:
        config_manager: Optional SNP configuration manager
        
    Returns:
        SNPComponentService instance
    """
    return SNPComponentService(config_manager)