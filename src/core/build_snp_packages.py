#!/usr/bin/env python3

import os
import sys
import glob
from typing import List, Optional, Union
from pathlib import Path
from src.utils import run_command, ensure_directory, ensure_parent_directory, remove_directory, BuildError, FileSystemError


def install_snp_dependencies(dependencies: List[str]) -> None:
    """Install build dependencies for SNP packages (kernel, OVMF and QEMU)."""
    print("Installing build dependencies for kernel, OVMF and QEMU")
    
    # Update apt package list
    run_command("sudo apt update")
    
    # Install dependencies
    deps_str = " ".join(dependencies)
    run_command(f"sudo apt install -y --no-install-recommends {deps_str}")


def setup_amdsev_repo(amd_path: Optional[str], repo_url: str, branch: str) -> str:
    """Setup or use existing AMDSEV repository."""
    if amd_path is None or not os.path.exists(amd_path):
        if amd_path is None:
            print("No AMDSEV path provided, will clone to default location")
        else:
            print(f"AMDSEV path {amd_path} does not exist, will clone to that location")
        
        # Ensure parent directory exists
        if amd_path:
            ensure_parent_directory(amd_path)
        
        print(f"Cloning AMDSEV repository to {amd_path}")
        run_command(f"git clone {repo_url} --branch {branch} --depth 1 {amd_path}")
    else:
        amd_path = Path(amd_path).resolve()
        print(f"Using existing AMDSEV repository: {amd_path}")
        
    return amd_path


def build_snp_packages_core(amd_path: str) -> None:
    """Run the build script in AMDSEV repository."""
    print("Building SNP packages...")
    build_script = os.path.join(amd_path, "build.sh")
    if not os.path.exists(build_script):
        raise FileSystemError(f"Build script not found: {build_script}", path=build_script)
    
    run_command(f"cd {amd_path} && ./build.sh --package")


def move_snp_release_packages(amd_path: str, build_dir: str) -> None:
    """Move SNP release directory and clean up debug files."""
    print("Moving SNP dir to root")
    
    # Find snp-release-* directory
    snp_release_pattern = os.path.join(amd_path, "snp-release-*")
    snp_release_dirs = glob.glob(snp_release_pattern)
    
    if not snp_release_dirs:
        raise BuildError("No snp-release-* directory found after package build", build_phase="snp_packages")
    
    if len(snp_release_dirs) > 1:
        print("Warning: Multiple snp-release-* directories found, using the first one")
    
    source_dir = Path(snp_release_dirs[0])
    target_dir = Path(build_dir) / "snp-release"
    
    # Remove existing target directory if it exists
    if target_dir.exists():
        remove_directory(str(target_dir))
    
    # Move the directory
    import shutil
    shutil.move(str(source_dir), str(target_dir))
    
    # Clean up debug .deb files
    print("Cleaning up debug .deb files")
    for search_dir in [target_dir / "linux" / "host", target_dir / "linux" / "guest"]:
        if search_dir.exists():
            for debug_file in search_dir.glob("**/*dbg*.deb"):
                print(f"Removing debug file: {debug_file}")
                debug_file.unlink()


def build_snp_packages(config, amd_path: Optional[str] = None) -> None:
    """
    Build SNP packages by:
      1. Installing dependencies
      2. Setting up AMDSEV repository
      3. Building packages
      4. Moving SNP release and cleanup
    """
    print("===> Building SNP packages")
    
    try:
        # Install dependencies
        install_snp_dependencies(config.snp_dependencies)
        
        # Setup AMDSEV repository - use provided path or default
        effective_amd_path = amd_path if amd_path else config.snp_amdsev_path
        amd_path = setup_amdsev_repo(effective_amd_path, config.snp_amdsev_repo, config.snp_amdsev_branch)
        
        # Build packages
        build_snp_packages_core(amd_path)
        
        # Move SNP release and cleanup
        move_snp_release_packages(amd_path, config.dir.build)
        
        print("SNP package build completed successfully!")
        
    except KeyboardInterrupt:
        print("\nSNP package build interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error during SNP package build: {e}")
        # Re-raise as BuildError if not already a HyperBeamError
        if hasattr(e, 'error_code'):
            raise  # Already a HyperBeamError, re-raise as-is
        else:
            raise BuildError(f"SNP package build failed: {str(e)}", build_phase="snp_packages", cause=e)