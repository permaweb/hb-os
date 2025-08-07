#!/usr/bin/env python3

import os
import sys
from typing import Optional
from src.services.snp_component_service import get_snp_component_service
from src.utils import BuildError


def install_snp_dependencies(dependencies: list[str]) -> None:
    """Install build dependencies for SNP packages."""
    from src.utils import run_command
    
    print("📦 Installing SNP build dependencies...")
    
    # Update apt package list
    run_command("sudo apt update")
    
    # Install dependencies
    deps_str = " ".join(dependencies)
    run_command(f"sudo apt install -y --no-install-recommends {deps_str}")
    
    print("✅ Dependencies installed successfully")


def build_snp_packages(config, amd_path: Optional[str] = None) -> None:
    """
    Build SNP release package with full workflow:
    1. Install dependencies from config
    2. Build all components (kernel, OVMF, QEMU)
    3. Create release package
    """
    print("===> Building SNP release package")
    
    try:
        # Step 1: Install dependencies
        install_snp_dependencies(config.snp_dependencies)
        
        # Step 2: Use the modern SNP component service
        snp_service = get_snp_component_service()
        build_dir = config.dir.snp_package
        
        print(f"🚀 Building SNP components in {build_dir}")
        
        # Use default installation directory within build directory
        install_dir = os.path.join(build_dir, "usr", "local")
        
        # Build all components
        results = snp_service.build_all_components(
            install_dir=install_dir,
            build_dir=build_dir,
            kernel_type=None  # Always build both host and guest kernels
        )
        
        print("✅ Component build results:")
        for component, result in results.items():
            print(f"  {component}: {result}")
        
        # Step 3: Create release package
        print("📦 Creating release package...")
        tarball = snp_service.create_release_package(
            build_dir=build_dir,
            install_dir=install_dir
        )
        print(f"✅ Release package created: {tarball}")
        
        print("🎉 SNP release build completed successfully!")
        
    except KeyboardInterrupt:
        print("\nSNP release build interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error during SNP release build: {e}")
        # Re-raise as BuildError if not already a HyperBeamError
        if hasattr(e, 'error_code'):
            raise  # Already a HyperBeamError, re-raise as-is
        else:
            raise BuildError(f"SNP release build failed: {str(e)}", build_phase="snp_release", cause=e)