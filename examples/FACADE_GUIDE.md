# HyperBEAM Facade System Guide

The HyperBEAM Facade System provides high-level, simplified interfaces for complex multi-step operations. Instead of managing multiple services and their dependencies manually, you can use facades to accomplish common workflows with just a few method calls.

## Overview

The facade system consists of several layers:

1. **Service Layer**: Low-level services (Configuration, Docker, VM, etc.)
2. **Facade Layer**: High-level workflow orchestration
3. **Main Facade**: Orchestrates all operations for common use cases

## Available Facades

### ISetupFacade
Handles environment setup and initialization.

```python
setup_facade.initialize_environment(force_dependencies=False)
setup_facade.setup_host_system()
setup_facade.verify_environment()
```

### IBuildFacade  
Manages build operations and orchestration.

```python
build_facade.build_complete_system(hb_branch="main", ao_branch="v1.0")
build_facade.build_snp_packages(amdsev_path="/path/to/amdsev")
build_facade.build_base_image()
build_facade.build_guest_image(hb_branch="main")
build_facade.get_build_status()
```

### IVMFacade
Simplifies VM lifecycle management.

```python
vm_facade.create_and_start_vm(
    data_disk="/path/to/disk.img",
    release_mode=False
)
vm_facade.connect_to_vm()
vm_facade.get_vm_status()
```

### IReleaseFacade
Handles release management operations.

```python
release_path = release_facade.create_release_package()
release_facade.download_and_install_release("https://example.com/release.tar.gz")
release_facade.clean_build_artifacts(keep_downloads=True)
release_facade.list_available_releases()
```

### IHyperBeamFacade (Main Facade)
Provides complete workflows for common use cases.

```python
# Complete setup and build
hyperbeam.quick_setup(force=False)

# Development workflow: build and start VM
hyperbeam.development_workflow(hb_branch="main", ao_branch="v1.0")

# Release workflow: build and package
release_path = hyperbeam.release_workflow(hb_branch="main")

# Demo workflow: showcase HyperBEAM
hyperbeam.demo_workflow(release_url="https://example.com/demo.tar.gz")

# Get comprehensive status
status = hyperbeam.get_system_status()
hyperbeam.print_status_report()
```

## Usage Examples

### Quick Start for Development

```python
from src.core.service_factory import get_service_container
from src.core.facade_interfaces import IHyperBeamFacade

# Get the main facade
container = get_service_container()
hyperbeam = container.resolve(IHyperBeamFacade)

# Complete setup and start development
hyperbeam.quick_setup()
hyperbeam.development_workflow(hb_branch="feature-branch")
```

### Creating a Release

```python
# Build and package everything
release_path = hyperbeam.release_workflow(
    hb_branch="release-v1.0",
    ao_branch="stable"
)
print(f"Release created: {release_path}")
```

### Working with Individual Facades

```python
from src.core.facade_interfaces import IBuildFacade, IVMFacade

# Use specific facades for targeted operations
build_facade = container.resolve(IBuildFacade)
vm_facade = container.resolve(IVMFacade)

# Build only the guest image
build_facade.build_guest_image(hb_branch="experimental")

# Start VM with custom configuration
vm_facade.create_and_start_vm(
    data_disk="/mnt/large-disk.img"
)
```

### Status Monitoring

```python
# Get detailed system status
status = hyperbeam.get_system_status()

if status['overall']['system_ready']:
    print("✅ System is ready!")
    hyperbeam.development_workflow()
else:
    print("❌ System needs setup:")
    if not status['environment']['initialized']:
        print("  - Run environment initialization")
    if not status['build']['vm_config']:
        print("  - Build VM configuration")
```

## Benefits of the Facade System

### **Simplified APIs**
- Complex multi-step operations become single method calls
- Intelligent defaults reduce configuration complexity
- Clear, intuitive method names

### **Error Handling**
- Comprehensive error messages with troubleshooting hints
- Validation of prerequisites before operations
- Graceful failure recovery suggestions

### **Testing & Mocking**
- Interface-based design enables easy mocking
- Individual facades can be tested in isolation
- Dependency injection simplifies test setup

### **Maintainability**
- Clear separation of concerns
- Easy to extend with new workflows
- Backward compatible with existing code

### **Performance**
- Intelligent caching and status checking
- Avoids redundant operations
- Optimized workflow orchestration

## Migration from Legacy Commands

The facade system maintains backward compatibility while providing improved APIs:

| Legacy Command | Facade Equivalent |
|----------------|-------------------|
| `./run init && ./run build_base && ./run build_guest` | `hyperbeam.quick_setup()` |
| `./run build_guest && ./run start` | `hyperbeam.development_workflow()` |
| `./run build_base && ./run build_guest && ./run package_release` | `hyperbeam.release_workflow()` |
| `./run start --data-disk /path` | `vm_facade.create_and_start_vm(...)` |

## Advanced Usage

### Custom Workflows

```python
class CustomWorkflow:
    def __init__(self, hyperbeam_facade: IHyperBeamFacade):
        self.hyperbeam = hyperbeam_facade
    
    def ci_cd_pipeline(self, branch: str):
        """Custom CI/CD pipeline workflow."""
        # Build with specific branch
        self.hyperbeam.release_workflow(hb_branch=branch)
        
        # Run tests
        vm_facade = container.resolve(IVMFacade)
        vm_facade.create_and_start_vm()
        # ... run tests ...
        
        # Package if tests pass
        release_facade = container.resolve(IReleaseFacade)
        return release_facade.create_release_package()
```

### Configuration Override

```python
# Facades respect dependency injection
custom_config = CustomConfigurationService(custom_settings)
container.register_singleton(IConfigurationService, custom_config)

# All facades will use the custom configuration
build_facade = container.resolve(IBuildFacade)
build_facade.build_complete_system()  # Uses custom settings
```

## Best Practices

1. **Use the Main Facade** for common workflows (`IHyperBeamFacade`)
2. **Use Individual Facades** for specific operations
3. **Check System Status** before starting complex operations
4. **Handle Exceptions** appropriately for production use
5. **Leverage DI Container** for custom configurations and testing

## Future Enhancements

The facade system is designed to be extensible:

- **Parallel Builds**: Execute build steps in parallel where possible
- **Remote Operations**: Support for distributed builds and deployments
- **Progress Tracking**: Real-time progress updates for long operations
- **Rollback Support**: Automatic rollback on failure
- **Plugin System**: Custom workflow plugins