#!/usr/bin/env python3
"""
Docker service for managing Docker operations with proper error handling.

This service encapsulates all Docker-related operations including building images,
running containers, copying files, and managing container lifecycles.
"""

import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, List, Optional, Union, Tuple

from src.core.service_interfaces import IDockerService, ICommandExecutionService, IFileSystemService
from src.utils import DockerError, handle_generic_error


class DockerService(IDockerService):
    """
    Service class for managing Docker operations with proper error handling and lifecycle management.
    
    This class provides a high-level interface for Docker operations commonly used
    in the HyperBEAM OS build process, including image building, container management,
    and file operations.
    """

    def __init__(self, command_service: ICommandExecutionService, fs_service: IFileSystemService):
        """
        Initialize the Docker service with injected dependencies.
        
        Args:
            command_service: Service for executing shell commands
            fs_service: Service for file system operations
        """
        self._command_service = command_service
        self._fs_service = fs_service
        self._running_containers = set()
    
    def build_image(self, context_dir: Union[str, Path], dockerfile_name: str, 
                   image_name: str, build_args: Optional[Dict[str, str]] = None) -> str:
        """
        Build a Docker image with proper error handling.
        
        Args:
            context_dir: Build context directory
            dockerfile_name: Name of the Dockerfile
            image_name: Name to tag the built image
            build_args: Build arguments to pass to Docker
        
        Returns:
            str: The image name that was built
            
        Raises:
            DockerError: If the build fails
            FileSystemError: If context directory or Dockerfile doesn't exist
        """
        context_path = Path(context_dir)
        dockerfile_path = context_path / dockerfile_name
        
        if not context_path.exists():
            raise DockerError(f"Build context directory not found: {context_path}", 
                             docker_operation="build")
        
        if not dockerfile_path.exists():
            raise DockerError(f"Dockerfile not found: {dockerfile_path}", 
                             docker_operation="build")
        
        print(f"Building Docker image: {image_name}")
        
        cmd = ["docker", "build", "-t", image_name]
        
        # Add build arguments if provided
        if build_args:
            for key, value in build_args.items():
                cmd.extend(["--build-arg", f"{key}={value}"])
        
        # Add dockerfile argument
        cmd.extend(["-f", dockerfile_name, "."])
        
        try:
            old_dir = os.getcwd()
            os.chdir(context_dir)
            self._command_service.run_command(cmd, shell=False)
            print(f"✅ Successfully built Docker image: {image_name}")
            return image_name
        except Exception as e:
            raise DockerError(f"Failed to build image '{image_name}': {str(e)}", 
                             docker_operation="build", cause=e)
        finally:
            os.chdir(old_dir)

    def run_container(self, image_name: str, container_name: str, 
                     command: str = "sleep 3600", 
                     additional_args: Optional[List[str]] = None,
                     auto_remove: bool = True) -> str:
        """
        Run a Docker container in detached mode.
        
        Args:
            image_name: Name of the Docker image to run
            container_name: Name for the container
            command: Command to run in the container
            additional_args: Additional arguments for docker run
            auto_remove: Whether to automatically remove container when it stops
        
        Returns:
            str: The container name that was started
            
        Raises:
            DockerError: If the container fails to start
        """
        print(f"Running Docker container: {container_name}")
        
        # Stop any existing container with the same name
        self.stop_container(container_name, ignore_errors=True)
        
        cmd = ["docker", "run", "-d", "--name", container_name]
        
        if auto_remove:
            cmd.append("--rm")
        
        if additional_args:
            cmd.extend(additional_args)
        
        cmd.extend([image_name] + command.split())
        
        try:
            self._command_service.run_command(cmd, shell=False)
            self._running_containers.add(container_name)
            print(f"✅ Successfully started container: {container_name}")
            return container_name
        except Exception as e:
            raise DockerError(f"Failed to run container '{container_name}': {str(e)}", 
                             docker_operation="run", cause=e)

    def stop_container(self, container_name: str, ignore_errors: bool = False) -> None:
        """
        Stop a Docker container.
        
        Args:
            container_name: Name of the container to stop
            ignore_errors: Whether to ignore errors if container doesn't exist
            
        Raises:
            DockerError: If stopping fails and ignore_errors is False
        """
        print(f"Stopping Docker container: {container_name}")
        
        try:
            self._command_service.run_command_silent(["docker", "stop", container_name])
            self._running_containers.discard(container_name)
            print(f"✅ Successfully stopped container: {container_name}")
        except Exception as e:
            if not ignore_errors:
                raise DockerError(f"Failed to stop container '{container_name}': {str(e)}", 
                                 docker_operation="stop", cause=e)

    def copy_from_container(self, container_name: str, src_path: str, dest_path: Union[str, Path]) -> None:
        """
        Copy files from a Docker container to the host.
        
        Args:
            container_name: Name of the source container
            src_path: Source path inside the container
            dest_path: Destination path on the host
            
        Raises:
            DockerError: If the copy operation fails
        """
        dest_path = Path(dest_path)
        print(f"Copying {src_path} from container {container_name} to: {dest_path}")
        
        # Ensure destination directory exists
        if dest_path.is_dir() or str(dest_path).endswith('/'):
            self._fs_service.ensure_directory(str(dest_path))
        else:
            self._fs_service.ensure_directory(str(dest_path.parent))
        
        try:
            self._command_service.run_command(["docker", "cp", f"{container_name}:{src_path}", str(dest_path)], shell=False)
            print(f"✅ Successfully copied from container: {container_name}")
        except Exception as e:
            raise DockerError(f"Failed to copy from container '{container_name}': {str(e)}", 
                             docker_operation="copy", cause=e)

    def export_filesystem(self, container_name: str, dest_dir: Union[str, Path]) -> None:
        """
        Export a container's entire filesystem to a directory.
        
        Args:
            container_name: Name of the container to export
            dest_dir: Destination directory for the exported filesystem
            
        Raises:
            DockerError: If the export operation fails
        """
        dest_path = Path(dest_dir)
        print(f"Exporting filesystem from {container_name} to {dest_path}")
        
        # Ensure destination directory exists
        self._fs_service.ensure_directory(str(dest_path))
        
        try:
            cmd = f"docker export {container_name} | tar xpf - -C {dest_path}"
            self._command_service.run_command(cmd, shell=True)
            print(f"✅ Successfully exported filesystem from container: {container_name}")
        except Exception as e:
            raise DockerError(f"Failed to export filesystem from container '{container_name}': {str(e)}", 
                             docker_operation="export", cause=e)

    def cleanup_containers(self) -> None:
        """
        Stop all containers managed by this service.
        
        This is useful for cleanup operations to ensure no containers are left running.
        """
        print("Cleaning up Docker containers...")
        for container_name in list(self._running_containers):
            self.stop_container(container_name, ignore_errors=True)
        self._running_containers.clear()

    @contextmanager
    def managed_container(self, image_name: str, container_name: str, 
                         command: str = "sleep 3600", 
                         additional_args: Optional[List[str]] = None):
        """
        Context manager for running a container with automatic cleanup.
        
        Args:
            image_name: Name of the Docker image to run
            container_name: Name for the container
            command: Command to run in the container
            additional_args: Additional arguments for docker run
            
        Yields:
            str: The container name
            
        Example:
            with docker_service.managed_container("my-image", "my-container") as container:
                docker_service.copy_from_container(container, "/data", "./output")
        """
        container = None
        try:
            container = self.run_container(image_name, container_name, command, additional_args)
            yield container
        finally:
            if container:
                self.stop_container(container, ignore_errors=True)


class DockerfileTemplateProcessor:
    """
    Utility class for processing Dockerfile templates with variable substitution.
    
    This class handles template variable replacement in Dockerfiles and provides
    mechanisms for restoring original content after operations.
    """

    @staticmethod
    def process_template(dockerfile_path: Union[str, Path], 
                        template_vars: Dict[str, str]) -> Tuple[str, str]:
        """
        Process a Dockerfile template by replacing template variables.
        
        Args:
            dockerfile_path: Path to the Dockerfile template
            template_vars: Dictionary of template variables to replace
        
        Returns:
            tuple: (original_content, modified_content) for restoration later
            
        Raises:
            DockerError: If the template processing fails
        """
        dockerfile_path = Path(dockerfile_path)
        
        if not dockerfile_path.exists():
            raise DockerError(f"Dockerfile template not found: {dockerfile_path}", 
                             docker_operation="template_processing")
        
        try:
            with open(dockerfile_path, 'r') as f:
                original_content = f.read()
            
            modified_content = original_content
            for var, value in template_vars.items():
                placeholder = f"<{var}>"
                modified_content = modified_content.replace(placeholder, value)
                print(f"Replaced {placeholder} -> {value}")
            
            with open(dockerfile_path, 'w') as f:
                f.write(modified_content)
            
            print(f"✅ Successfully processed Dockerfile template: {dockerfile_path}")
            return original_content, modified_content
            
        except Exception as e:
            raise DockerError(f"Failed to process Dockerfile template: {str(e)}", 
                             docker_operation="template_processing", cause=e)

    @staticmethod
    def restore_template(dockerfile_path: Union[str, Path], original_content: str) -> None:
        """
        Restore original content to a Dockerfile template.
        
        Args:
            dockerfile_path: Path to the Dockerfile to restore
            original_content: Original content to restore
            
        Raises:
            DockerError: If the restoration fails
        """
        dockerfile_path = Path(dockerfile_path)
        
        try:
            with open(dockerfile_path, 'w') as f:
                f.write(original_content)
            print(f"✅ Successfully restored Dockerfile template: {dockerfile_path}")
        except Exception as e:
            raise DockerError(f"Failed to restore Dockerfile template: {str(e)}", 
                             docker_operation="template_restoration", cause=e)

    @classmethod
    @contextmanager
    def managed_template(cls, dockerfile_path: Union[str, Path], 
                        template_vars: Dict[str, str]):
        """
        Context manager for processing a Dockerfile template with automatic restoration.
        
        Args:
            dockerfile_path: Path to the Dockerfile template
            template_vars: Dictionary of template variables to replace
            
        Yields:
            tuple: (original_content, modified_content)
            
        Example:
            with DockerfileTemplateProcessor.managed_template(dockerfile, vars) as (orig, mod):
                # Dockerfile is now processed with variables
                docker_service.build_image(context, "Dockerfile", "my-image")
                # Dockerfile is automatically restored on exit
        """
        original_content = None
        try:
            original_content, modified_content = cls.process_template(dockerfile_path, template_vars)
            yield original_content, modified_content
        finally:
            if original_content:
                cls.restore_template(dockerfile_path, original_content)


# Global Docker service instance - maintained for backward compatibility
# TODO: Migrate remaining usages to dependency injection
from .command_execution_service import CommandExecutionService
from .filesystem_service import FileSystemService

# Create global instance with required dependencies
_command_service = CommandExecutionService()
_fs_service = FileSystemService()
docker_service = DockerService(_command_service, _fs_service)