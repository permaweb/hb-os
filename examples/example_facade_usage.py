#!/usr/bin/env python3
"""
Example demonstrating the HyperBEAM Facade System.

This script shows how the facade pattern simplifies complex operations
into easy-to-use, high-level workflows.
"""

from src.core.service_factory import get_service_container
from src.core.facade_interfaces import IHyperBeamFacade


def main():
    """Demonstrate facade usage patterns."""
    
    print("🎭 HyperBEAM Facade System Demo")
    print("=" * 50)
    
    # Get the main facade through dependency injection
    container = get_service_container()
    hyperbeam = container.resolve(IHyperBeamFacade)
    
    print("\n🔍 Getting system status...")
    hyperbeam.print_status_report()
    
    print("\n" + "=" * 50)
    print("✨ Facade Examples:")
    print("\n1. Quick Setup (complete environment initialization):")
    print("   hyperbeam.quick_setup()")
    print("\n2. Development Workflow (build and start VM):")
    print("   hyperbeam.development_workflow(hb_branch='main')")
    print("\n3. Release Workflow (build and package):")
    print("   release_path = hyperbeam.release_workflow()")
    print("\n4. Demo Workflow (showcase HyperBEAM):")
    print("   hyperbeam.demo_workflow()")
    
    print("\n" + "=" * 50)
    print("🎯 Individual Facade Usage:")
    
    # You can also use individual facades for specific operations
    from src.core.facade_interfaces import ISetupFacade, IBuildFacade, IVMFacade, IReleaseFacade
    
    setup_facade = container.resolve(ISetupFacade)
    build_facade = container.resolve(IBuildFacade)
    vm_facade = container.resolve(IVMFacade)
    release_facade = container.resolve(IReleaseFacade)
    
    print("\n🔧 Setup Operations:")
    print("   setup_facade.initialize_environment()")
    print("   setup_facade.verify_environment()")
    
    print("\n🏗️  Build Operations:")
    print("   build_facade.build_complete_system()")
    print("   build_facade.get_build_status()")
    
    print("\n🚀 VM Operations:")
    print("   vm_facade.create_and_start_vm(release_mode=True)")
    print("   vm_facade.connect_to_vm()")
    
    print("\n📦 Release Operations:")
    print("   release_facade.create_release_package()")
    print("   release_facade.list_available_releases()")
    
    print("\n" + "=" * 50)
    print("✅ Facade system provides simple, high-level APIs")
    print("   for complex multi-step operations!")


if __name__ == "__main__":
    main()