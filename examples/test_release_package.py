#!/usr/bin/env python3
"""
Test script for SNP release package creation.
Uses existing build artifacts to test just the packaging functionality.
"""

import sys
import os
sys.path.insert(0, '.')

from src.core.snp_builder import SNPBuildOrchestrator
from src.utils.snp_config import SNPConfigManager

def test_release_package():
    """Test creating a release package from existing build artifacts."""
    
    # Path to your existing build directory
    build_dir = "/home/hb/ftp/hb-os2/build/SNP_PACKAGE"
    install_dir = os.path.join(build_dir, "usr", "local")
    
    print(f"🧪 Testing release package creation...")
    print(f"Build directory: {build_dir}")
    print(f"Install directory: {install_dir}")
    
    # Check if build artifacts exist
    if not os.path.exists(build_dir):
        print(f"❌ Build directory not found: {build_dir}")
        return False
        
    if not os.path.exists(install_dir):
        print(f"⚠️  Install directory not found: {install_dir}")
        print("   Will create release package without usr/local files")
    
    try:
        # Create orchestrator
        config = SNPConfigManager()
        orchestrator = SNPBuildOrchestrator(config)
        
        # Test release package creation
        print("📦 Creating release package...")
        tarball_path = orchestrator.create_release_package(
            build_dir=build_dir,
            install_dir=install_dir
        )
        
        print(f"✅ Success! Release package created: {tarball_path}")
        
        # Show some info about the created package
        if os.path.exists(tarball_path):
            size_mb = os.path.getsize(tarball_path) / (1024 * 1024)
            print(f"📊 Package size: {size_mb:.1f} MB")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating release package: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_release_package()
    sys.exit(0 if success else 1)