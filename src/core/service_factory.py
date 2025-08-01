#!/usr/bin/env python3
"""
Service Factory for Dependency Injection.

This module provides factory functions for creating and configuring the dependency injection
container with all the required services for the HyperBEAM OS application.
"""

from config import config
from src.core.di_container import DIContainer
from src.core.service_interfaces import (
    IConfigurationService, ICommandExecutionService, IDockerService, 
    IFileSystemService, IVMService, IDependencyService, IBuildService, IReleaseService
)
from src.core.facade_interfaces import (
    ISetupFacade, IBuildFacade, IVMFacade, IReleaseFacade, IHyperBeamFacade
)
from src.services import ConfigurationService, CommandExecutionService, DockerService, FileSystemService


def create_service_container() -> DIContainer:
    """
    Create and configure the dependency injection container with all required services.
    
    Returns:
        DIContainer: Fully configured container with all services registered
    """
    container = DIContainer()
    
    # Register core services
    _register_core_services(container)
    
    # Register higher-level services that depend on core services
    _register_application_services(container)
    
    # Register facades that depend on services
    _register_facades(container)
    
    return container


def _register_core_services(container: DIContainer) -> None:
    """Register core infrastructure services."""
    
    # Configuration service (singleton)
    config_service = ConfigurationService(config)
    container.register_singleton(IConfigurationService, config_service)
    
    # Command execution service (singleton)
    container.register_class(ICommandExecutionService, CommandExecutionService, singleton=True)
    
    # File system service (singleton)
    container.register_class(IFileSystemService, FileSystemService, singleton=True)
    
    # Docker service (singleton, depends on command and filesystem services)
    container.register_class(IDockerService, DockerService, singleton=True)


def _register_application_services(container: DIContainer) -> None:
    """Register application-level services that depend on core services."""
    
    # Import here to avoid circular dependencies
    from src.core.vm_manager import VMService
    
    # VM service - implemented as injectable
    container.register_class(IVMService, VMService, singleton=True)
    
    # Dependency service - will be implemented as injectable  
    # container.register_class(IDependencyService, DependencyService, singleton=True)
    
    # Build service - will be implemented as injectable
    # container.register_class(IBuildService, BuildService, singleton=True)
    
    # Release service - will be implemented as injectable
    # container.register_class(IReleaseService, ReleaseService, singleton=True)
    
    # These services will be added as we refactor each module


def _register_facades(container: DIContainer) -> None:
    """Register facade services that provide high-level workflows."""
    
    # Import here to avoid circular dependencies
    from src.facades import (
        SetupFacade, BuildFacade, VMFacade, ReleaseFacade, HyperBeamFacade
    )
    
    # Setup facade (singleton)
    container.register_class(ISetupFacade, SetupFacade, singleton=True)
    
    # Build facade (singleton)
    container.register_class(IBuildFacade, BuildFacade, singleton=True)
    
    # VM facade (singleton)
    container.register_class(IVMFacade, VMFacade, singleton=True)
    
    # Release facade (singleton)
    container.register_class(IReleaseFacade, ReleaseFacade, singleton=True)
    
    # Main HyperBeam facade (singleton)
    container.register_class(IHyperBeamFacade, HyperBeamFacade, singleton=True)


def get_service_container() -> DIContainer:
    """
    Get a singleton instance of the configured service container.
    
    Returns:
        DIContainer: The global service container instance
    """
    if not hasattr(get_service_container, '_container'):
        get_service_container._container = create_service_container()
    return get_service_container._container


def reset_service_container() -> None:
    """Reset the global service container (useful for testing)."""
    if hasattr(get_service_container, '_container'):
        delattr(get_service_container, '_container')