#!/usr/bin/env python3
"""
Setup Facade Implementation.

This facade simplifies environment setup and initialization operations.
"""
import requests
import shutil
import os
from typing import Optional
from src.core.facade_interfaces import ISetupFacade
from src.core.service_interfaces import (
    IConfigurationService, ICommandExecutionService, 
    IFileSystemService, IDependencyService
)


class SetupFacade(ISetupFacade):
    """
    Facade for environment setup and initialization operations.
    
    Provides high-level methods for setting up the HyperBEAM development environment.
    """
    
    def __init__(self, config_service: IConfigurationService,
                 command_service: ICommandExecutionService,
                 fs_service: IFileSystemService):
        """
        Initialize SetupFacade with injected dependencies.
        
        Args:
            config_service: Configuration service for accessing settings
            command_service: Command execution service
            fs_service: File system service
        """
        self._config = config_service
        self._command = command_service
        self._fs = fs_service
    
    def initialize_environment(self, force_dependencies: bool = False) -> None:
        """
        Initialize the complete build environment.
        
        This orchestrates the entire initialization process including
        directory creation, dependency installation, SNP release setup,
        and tool building.
        
        Args:
            force_dependencies: Force reinstallation of dependencies
        """
        print("🚀 Initializing HyperBEAM environment...")
        
        # Step 1: Create necessary directories
        print("📁 Creating build directories...")
        self._create_build_directories()
        
        # Step 2: Install system dependencies
        print("📦 Installing system dependencies...")
        self._install_dependencies(force_dependencies)
        
        # Step 3: Download and extract SNP release
        print("⬇️  Setting up SNP release...")
        self._setup_snp_release()
        
        # Step 4: Build attestation tools
        print("🔨 Building attestation tools...")
        self._build_attestation_tools()
        
        # Step 5: Set up host system
        print("🖥️  Setting up host system...")
        self.setup_host_system()
        
        print("✅ Environment initialization complete!")
    
    def setup_host_system(self) -> None:
        """
        Set up the host system for SNP operations.
        
        This configures the host system using the SNP release installer.
        """
        print("🖥️  Setting up host system with SNP release...")
        snp_release_dir = os.path.join(self._config.build_dir, "snp-release")
        self._command.run_command(f"cd {snp_release_dir} && sudo ./install.sh")
        print("✅ Host system setup complete!")
    
    def verify_environment(self) -> bool:
        """
        Verify that the environment is properly configured.
        
        Returns:
            True if environment is ready, False otherwise
        """
        print("🔍 Verifying environment configuration...")
        
        # Check if key directories exist
        required_dirs = [
            self._config.build_dir,
            self._config.guest_dir,
            self._config.content_dir,
            self._config.kernel_dir
        ]
        
        for directory in required_dirs:
            if not os.path.exists(directory):
                print(f"❌ Missing directory: {directory}")
                return False
        
        # Check if key tools exist
        bin_dir = self._config.config.dirs.bin
        required_tools = [
            os.path.join(bin_dir, "digest_calc"),
            os.path.join(bin_dir, "server"),
            os.path.join(bin_dir, "client")
        ]
        
        for tool in required_tools:
            if not os.path.exists(tool):
                print(f"❌ Missing tool: {tool}")
                return False
        
        # Check if SNP release exists
        snp_release_dir = os.path.join(self._config.build_dir, "snp-release")
        if not os.path.exists(snp_release_dir):
            print(f"❌ Missing SNP release: {snp_release_dir}")
            return False
        
        print("✅ Environment verification passed!")
        return True
    
    def _create_build_directories(self) -> None:
        """Create all necessary build directories."""
        # Get all directory paths from config and create them
        for attr_name in dir(self._config.config.dirs):
            if not attr_name.startswith('_'):
                directory = getattr(self._config.config.dirs, attr_name)
                if isinstance(directory, str):
                    self._fs.ensure_directory(directory)
                    print(f"  📁 Created: {directory}")
    
    def _install_dependencies(self, force: bool = False) -> None:
        """Install system dependencies."""
        # Import here to avoid circular dependencies
        from src.services.dependencies import install_dependencies
        install_dependencies(force=force)
    
    def _setup_snp_release(self) -> None:
        """Download and extract SNP release."""

        
        tarball = os.path.join(self._config.build_dir, "snp-release.tar.gz")
        url = "https://github.com/SNPGuard/snp-guard/releases/download/v0.1.2/snp-release.tar.gz"
        
        print(f"  ⬇️  Downloading SNP release from {url}...")
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            with open(tarball, "wb") as f:
                shutil.copyfileobj(r.raw, f)
        
        print(f"  📦 Extracting SNP release...")
        self._command.run_command(f"tar -xf {tarball} -C {self._config.build_dir}")
        self._command.run_command(f"rm {tarball}")
    
    def _build_attestation_tools(self) -> None:
        """Build attestation server and digest calculator tools."""
        bin_dir = self._config.config.dirs.bin
        
        # Build attestation server binaries
        print("  🔨 Building attestation server...")
        self._command.run_command("cargo build --manifest-path=tools/attestation_server/Cargo.toml")
        
        binaries = ["server", "client", "get_report", "idblock-generator", "sev-feature-info", "verify_report"]
        for binary in binaries:
            src = os.path.join("tools", "attestation_server", "target", "debug", binary)
            self._command.run_command(f"cp {src} {bin_dir}")
        
        # Build digest calculator binary
        print("  🔨 Building digest calculator...")
        self._command.run_command("cargo build --manifest-path=tools/digest_calc/Cargo.toml")
        self._command.run_command(f"cp ./tools/digest_calc/target/debug/digest_calc {bin_dir}")