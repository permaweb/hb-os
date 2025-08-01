#!/usr/bin/env python3
"""
Dependency Injection Container for HyperBEAM OS.

This module provides a simple but powerful dependency injection system that allows:
- Registration of service factories and singletons
- Automatic resolution of dependencies
- Interface-based service definitions
- Lifecycle management for services
"""

from typing import TypeVar, Type, Any, Dict, Callable, Optional, Protocol, runtime_checkable
from abc import ABC, abstractmethod
import inspect


# Type variables for generic service resolution
T = TypeVar('T')
ServiceFactory = Callable[..., T]


class ServiceNotFoundError(Exception):
    """Raised when a requested service is not registered in the container."""
    def __init__(self, service_type: Type):
        self.service_type = service_type
        super().__init__(f"Service of type {service_type.__name__} is not registered")


class CircularDependencyError(Exception):
    """Raised when a circular dependency is detected during service resolution."""
    def __init__(self, dependency_chain: list):
        self.dependency_chain = dependency_chain
        chain_str = " -> ".join(dep.__name__ for dep in dependency_chain)
        super().__init__(f"Circular dependency detected: {chain_str}")


class DIContainer:
    """
    Dependency Injection Container that manages service registration and resolution.
    
    Features:
    - Service registration via factory functions or classes
    - Singleton and transient lifecycle management  
    - Automatic dependency resolution via constructor injection
    - Interface-based service registration
    - Circular dependency detection
    """
    
    def __init__(self):
        self._services: Dict[Type, ServiceFactory] = {}
        self._singletons: Dict[Type, Any] = {}
        self._resolving: set = set()  # For circular dependency detection
    
    def register_singleton(self, service_type: Type[T], instance: T) -> None:
        """
        Register a singleton instance for the given service type.
        
        Args:
            service_type: The type/interface that this service implements
            instance: The singleton instance to register
        """
        self._services[service_type] = lambda: instance
        self._singletons[service_type] = instance
    
    def register_factory(self, service_type: Type[T], factory: ServiceFactory[T]) -> None:
        """
        Register a factory function for creating instances of the service type.
        
        Args:
            service_type: The type/interface that this service implements
            factory: Factory function that creates instances of this service
        """
        self._services[service_type] = factory
    
    def register_class(self, service_type: Type[T], implementation_class: Type[T], 
                      singleton: bool = True) -> None:
        """
        Register a class as the implementation for a service type.
        
        Args:
            service_type: The type/interface that this service implements
            implementation_class: The concrete class that implements the service
            singleton: Whether to create a singleton instance or new instances each time
        """
        if singleton:
            def factory():
                if service_type not in self._singletons:
                    self._singletons[service_type] = self._create_instance(implementation_class)
                return self._singletons[service_type]
            self._services[service_type] = factory
        else:
            self._services[service_type] = lambda: self._create_instance(implementation_class)
    
    def resolve(self, service_type: Type[T]) -> T:
        """
        Resolve an instance of the requested service type.
        
        Args:
            service_type: The type/interface to resolve
            
        Returns:
            An instance of the requested service
            
        Raises:
            ServiceNotFoundError: If the service is not registered
            CircularDependencyError: If a circular dependency is detected
        """
        if service_type not in self._services:
            raise ServiceNotFoundError(service_type)
        
        # Check for circular dependencies
        if service_type in self._resolving:
            chain = list(self._resolving) + [service_type]
            raise CircularDependencyError(chain)
        
        # Return singleton if already created
        if service_type in self._singletons:
            return self._singletons[service_type]
        
        # Add to resolving set for circular dependency detection
        self._resolving.add(service_type)
        
        try:
            factory = self._services[service_type]
            instance = factory()
            return instance
        finally:
            # Remove from resolving set
            self._resolving.discard(service_type)
    
    def _create_instance(self, cls: Type[T]) -> T:
        """
        Create an instance of the given class with automatic dependency injection.
        
        Args:
            cls: The class to instantiate
            
        Returns:
            An instance of the class with dependencies injected
        """
        # Get constructor signature
        sig = inspect.signature(cls.__init__)
        args = {}
        
        # Resolve dependencies for each constructor parameter (except 'self')
        for name, param in sig.parameters.items():
            if name == 'self':
                continue
                
            # Skip parameters with default values for now
            if param.default != inspect.Parameter.empty:
                continue
                
            # Get the parameter type annotation
            param_type = param.annotation
            if param_type != inspect.Parameter.empty:
                args[name] = self.resolve(param_type)
        
        return cls(**args)
    
    def is_registered(self, service_type: Type) -> bool:
        """Check if a service type is registered in the container."""
        return service_type in self._services
    
    def clear(self) -> None:
        """Clear all registered services and singletons."""
        self._services.clear()
        self._singletons.clear()
        self._resolving.clear()