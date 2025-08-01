#!/usr/bin/env python3
"""
Main HyperBeam Facade Implementation.

This is the highest-level facade that orchestrates all HyperBEAM operations.
"""

from typing import Optional, Dict, Any
from src.core.facade_interfaces import (
    IHyperBeamFacade, ISetupFacade, IBuildFacade, 
    IVMFacade, IReleaseFacade
)


class HyperBeamFacade(IHyperBeamFacade):
    """
    Main facade that orchestrates all HyperBEAM operations.
    
    This is the highest-level interface that provides simple workflows
    for the most common use cases.
    """
    
    def __init__(self, setup_facade: ISetupFacade, build_facade: IBuildFacade,
                 vm_facade: IVMFacade, release_facade: IReleaseFacade):
        """
        Initialize HyperBeamFacade with all sub-facades.
        
        Args:
            setup_facade: Setup operations facade
            build_facade: Build operations facade
            vm_facade: VM management facade
            release_facade: Release management facade
        """
        self._setup = setup_facade
        self._build = build_facade
        self._vm = vm_facade
        self._release = release_facade
    
    def quick_setup(self, force: bool = False) -> None:
        """
        Perform a complete quick setup for development.
        
        This runs the complete initialization and build process:
        1. Initialize environment
        2. Build complete system
        
        Args:
            force: Force reinstallation of dependencies
        """
        print("🚀 HyperBEAM Quick Setup")
        print("=" * 50)
        
        try:
            # Step 1: Initialize environment
            print("\n🔧 Phase 1: Environment Initialization")
            print("-" * 40)
            self._setup.initialize_environment(force_dependencies=force)
            
            # Step 2: Build complete system
            print("\n🏗️  Phase 2: System Build")
            print("-" * 40)
            self._build.build_complete_system()
            
            print("\n" + "=" * 50)
            print("✅ Quick setup completed successfully!")
            print("\nYou can now:")
            print("  • Start a VM with: ./run start")
            print("  • Create a release with: ./run package_release")
            print("  • Connect to VM with: ./run ssh")
            
        except Exception as e:
            print(f"\n❌ Quick setup failed: {e}")
            print("\nYou can retry with individual commands:")
            print("  • ./run init")
            print("  • ./run build_base")
            print("  • ./run build_guest")
            raise
    
    def development_workflow(self, hb_branch: Optional[str] = None,
                           ao_branch: Optional[str] = None) -> None:
        """
        Complete development workflow: build and start VM.
        
        This runs: build_guest_image -> start_vm
        
        Args:
            hb_branch: HyperBEAM branch to use
            ao_branch: AO branch to use
        """
        print("🔨 HyperBEAM Development Workflow")
        print("=" * 50)
        
        try:
            # Step 1: Build guest image
            print("\n📦 Phase 1: Building Guest Image")
            print("-" * 40)
            self._build.build_guest_image(hb_branch, ao_branch)
            
            # Step 2: Start VM
            print("\n🚀 Phase 2: Starting VM")
            print("-" * 40)
            self._vm.create_and_start_vm()
            
            print("\n" + "=" * 50)
            print("✅ Development workflow completed!")
            print("\nYour VM is now running. You can:")
            print("  • Connect with: ./run ssh")
            print("  • Monitor logs in the QEMU console")
            
        except Exception as e:
            print(f"\n❌ Development workflow failed: {e}")
            print("\nTroubleshooting:")
            print("  • Check build status with get_system_status()")
            print("  • Verify environment with verify_environment()")
            raise
    
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
        print("📦 HyperBEAM Release Workflow")
        print("=" * 50)
        
        try:
            # Step 1: Build complete system
            print("\n🏗️  Phase 1: Building Complete System")
            print("-" * 40)
            self._build.build_complete_system(hb_branch, ao_branch)
            
            # Step 2: Create release package
            print("\n📦 Phase 2: Creating Release Package")
            print("-" * 40)
            release_path = self._release.create_release_package()
            
            print("\n" + "=" * 50)
            print("✅ Release workflow completed!")
            print(f"📦 Release package: {release_path}")
            print("\nYou can now:")
            print("  • Test the release with: ./run start_release")
            print("  • Distribute the release package")
            
            return release_path
            
        except Exception as e:
            print(f"\n❌ Release workflow failed: {e}")
            print("\nTroubleshooting:")
            print("  • Check build status with get_system_status()")
            print("  • Ensure all components built successfully")
            raise
    
    def demo_workflow(self, release_url: Optional[str] = None) -> None:
        """
        Demo workflow for showcasing HyperBEAM.
        
        This either downloads a release or uses existing build,
        then starts the VM for demonstration.
        
        Args:
            release_url: Optional URL to download demo release
        """
        print("🎬 HyperBEAM Demo Workflow")
        print("=" * 50)
        
        try:
            if release_url:
                # Download and use remote release
                print(f"\n⬇️  Phase 1: Downloading Demo Release")
                print("-" * 40)
                self._release.download_and_install_release(release_url, verify_checksum=False)
                
                print("\n🚀 Phase 2: Starting Demo VM")
                print("-" * 40)
                self._vm.create_and_start_vm(release_mode=True)
                
            else:
                # Use existing build or create minimal build
                print("\n🔍 Phase 1: Checking System Status")
                print("-" * 40)
                status = self.get_system_status()
                
                if not status['vm_ready']:
                    print("Building minimal system for demo...")
                    self._build.build_guest_image()
                
                print("\n🚀 Phase 2: Starting Demo VM")
                print("-" * 40)
                self._vm.create_and_start_vm()
            
            print("\n" + "=" * 50)
            print("✅ Demo workflow completed!")
            print("\n🎬 Demo is now running!")
            print("You can:")
            print("  • Connect with: ./run ssh")
            print("  • Explore the HyperBEAM environment")
            print("  • Run attestation commands")
            
        except Exception as e:
            print(f"\n❌ Demo workflow failed: {e}")
            print("\nTroubleshooting:")
            print("  • Ensure environment is initialized")
            print("  • Check system status")
            raise
    
    def get_system_status(self) -> Dict[str, Any]:
        """
        Get comprehensive system status.
        
        Returns:
            Dictionary with complete system status information
        """
        print("🔍 Gathering system status...")
        
        status = {
            'environment': {},
            'build': {},
            'vm': {},
            'releases': {},
            'overall': {}
        }
        
        try:
            # Environment status
            status['environment']['initialized'] = self._setup.verify_environment()
            
            # Build status
            status['build'] = self._build.get_build_status()
            
            # VM status
            status['vm'] = self._vm.get_vm_status()
            
            # Release status
            status['releases'] = self._release.list_available_releases()
            
            # Overall readiness
            status['overall']['environment_ready'] = status['environment']['initialized']
            status['overall']['build_ready'] = all(status['build'].values())
            status['overall']['vm_ready'] = status['vm']['ready_for_start']
            status['overall']['release_ready'] = status['vm']['ready_for_release']
            status['overall']['system_ready'] = (
                status['overall']['environment_ready'] and 
                status['overall']['build_ready'] and 
                status['overall']['vm_ready']
            )
            
        except Exception as e:
            status['error'] = str(e)
            status['overall']['system_ready'] = False
        
        return status
    
    def print_status_report(self) -> None:
        """Print a human-readable status report."""
        print("📊 HyperBEAM System Status Report")
        print("=" * 50)
        
        status = self.get_system_status()
        
        # Environment Status
        print("\n🔧 Environment:")
        env_status = "✅ Ready" if status['environment']['initialized'] else "❌ Not Ready"
        print(f"  Initialization: {env_status}")
        
        # Build Status
        print("\n🏗️  Build Components:")
        build_status = status['build']
        for component, ready in build_status.items():
            icon = "✅" if ready else "❌"
            print(f"  {component.replace('_', ' ').title()}: {icon}")
        
        # VM Status
        print("\n🚀 VM Status:")
        vm_status = status['vm']
        vm_ready = "✅ Ready" if vm_status['ready_for_start'] else "❌ Not Ready"
        release_ready = "✅ Ready" if vm_status['ready_for_release'] else "❌ Not Ready"
        print(f"  VM Start: {vm_ready}")
        print(f"  Release Mode: {release_ready}")
        
        # Overall Status
        print("\n📋 Overall:")
        overall = status['overall']
        system_ready = "✅ System Ready" if overall['system_ready'] else "❌ System Not Ready"
        print(f"  {system_ready}")
        
        # Recommendations
        print("\n💡 Recommendations:")
        if not overall['environment_ready']:
            print("  • Run: ./run init")
        if not overall['build_ready']:
            print("  • Run: ./run build_base && ./run build_guest")
        if overall['system_ready']:
            print("  • System is ready! You can start a VM with: ./run start")
        
        print("\n" + "=" * 50)