#!/usr/bin/env python3
"""
Utility functions shared across the HyperBEAM build system.
Common functionality for command execution, file operations, and Docker management.
"""

import os
import sys
import subprocess
import shutil
import traceback
from pathlib import Path
from typing import List, Optional, Union


# -----------------------------------------------------------------------------
# Exception Hierarchy
# -----------------------------------------------------------------------------

class HyperBeamError(Exception):
    """
    Base exception class for all HyperBEAM OS errors.
    
    Provides consistent error handling throughout the application with
    proper context and error codes.
    """
    
    def __init__(self, message: str, error_code: int = 1, cause: Optional[Exception] = None):
        """
        Initialize HyperBEAM error.
        
        Args:
            message: Human-readable error message
            error_code: Exit code for command-line tools (default: 1)
            cause: Original exception that caused this error (optional)
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.cause = cause
    
    def __str__(self) -> str:
        """String representation of the error."""
        if self.cause:
            return f"{self.message} (caused by: {self.cause})"
        return self.message


class ConfigurationError(HyperBeamError):
    """Raised when there are configuration-related errors."""
    
    def __init__(self, message: str, config_key: Optional[str] = None, cause: Optional[Exception] = None):
        super().__init__(f"Configuration error: {message}", error_code=2, cause=cause)
        self.config_key = config_key


class CommandExecutionError(HyperBeamError):
    """Raised when external command execution fails."""
    
    def __init__(self, message: str, command: str, exit_code: int = 1, 
                 stdout: Optional[str] = None, stderr: Optional[str] = None, 
                 cause: Optional[Exception] = None):
        super().__init__(f"Command execution failed: {message}", error_code=exit_code, cause=cause)
        self.command = command
        self.stdout = stdout
        self.stderr = stderr


class BuildError(HyperBeamError):
    """Raised when build operations fail."""
    
    def __init__(self, message: str, build_phase: Optional[str] = None, cause: Optional[Exception] = None):
        super().__init__(f"Build failed: {message}", error_code=3, cause=cause)
        self.build_phase = build_phase


class DependencyError(HyperBeamError):
    """Raised when dependency checks or installations fail."""
    
    def __init__(self, message: str, dependency: Optional[str] = None, cause: Optional[Exception] = None):
        super().__init__(f"Dependency error: {message}", error_code=4, cause=cause)
        self.dependency = dependency


class VMError(HyperBeamError):
    """Raised when VM operations fail."""
    
    def __init__(self, message: str, vm_operation: Optional[str] = None, cause: Optional[Exception] = None):
        super().__init__(f"VM operation failed: {message}", error_code=5, cause=cause)
        self.vm_operation = vm_operation


class DockerError(HyperBeamError):
    """Raised when Docker operations fail."""
    
    def __init__(self, message: str, docker_operation: Optional[str] = None, cause: Optional[Exception] = None):
        super().__init__(f"Docker operation failed: {message}", error_code=6, cause=cause)
        self.docker_operation = docker_operation


class FileSystemError(HyperBeamError):
    """Raised when file system operations fail."""
    
    def __init__(self, message: str, path: Optional[str] = None, cause: Optional[Exception] = None):
        super().__init__(f"File system error: {message}", error_code=7, cause=cause)
        self.path = path


class SecurityError(HyperBeamError):
    """Raised when security-related operations fail."""
    
    def __init__(self, message: str, security_context: Optional[str] = None, cause: Optional[Exception] = None):
        super().__init__(f"Security error: {message}", error_code=8, cause=cause)
        self.security_context = security_context


def handle_subprocess_error(e: subprocess.CalledProcessError, command_description: str) -> CommandExecutionError:
    """
    Convert subprocess.CalledProcessError to standardized CommandExecutionError.
    
    Args:
        e: The subprocess error
        command_description: Human-readable description of what command failed
        
    Returns:
        CommandExecutionError: Standardized error with context
    """
    stdout = getattr(e, 'stdout', None)
    stderr = getattr(e, 'stderr', None)
    
    return CommandExecutionError(
        message=command_description,
        command=str(e.cmd) if hasattr(e, 'cmd') else 'unknown',
        exit_code=e.returncode,
        stdout=stdout,
        stderr=stderr,
        cause=e
    )


def handle_generic_error(e: Exception, operation_description: str, 
                        error_type: type = HyperBeamError) -> HyperBeamError:
    """
    Convert generic exceptions to standardized HyperBEAM errors.
    
    Args:
        e: The original exception
        operation_description: Human-readable description of what operation failed
        error_type: Type of HyperBEAM error to create (default: HyperBeamError)
        
    Returns:
        HyperBeamError: Standardized error with context
    """
    return error_type(
        message=f"{operation_description}: {str(e)}",
        cause=e
    )


# -----------------------------------------------------------------------------
# Command Builder Abstraction
# -----------------------------------------------------------------------------

class CommandBuilder:
    """
    A fluent interface for building shell commands safely and readably.
    
    Eliminates error-prone string concatenation and provides a clean API
    for constructing complex commands with parameters, flags, and pipes.
    
    Examples:
        # Simple command
        cmd = CommandBuilder("ls").arg("-la").arg("/home").build()
        # Result: "ls -la /home"
        
        # QEMU command with many parameters
        cmd = (CommandBuilder("sudo", "-E", "qemu-system-x86_64")
               .flag("enable-kvm")
               .param("m", "2048")
               .param("hda", "/path/to/image.qcow2")
               .build())
        
        # Pipeline command  
        cmd = (CommandBuilder("sudo", "veritysetup", "format", device, hash_tree)
               .pipe("grep", "Root")
               .pipe("cut", "-f2")
               .build())
    """
    
    def __init__(self, *initial_args: str):
        """
        Initialize the command builder with initial command and arguments.
        
        Args:
            *initial_args: Initial command parts (e.g., "sudo", "-E", "qemu-system-x86_64")
        """
        self._parts: List[str] = list(initial_args)
        self._pipes: List[List[str]] = []
    
    def arg(self, argument: str) -> 'CommandBuilder':
        """
        Add a single argument to the command.
        
        Args:
            argument: Argument to add
            
        Returns:
            CommandBuilder: Self for method chaining
        """
        self._parts.append(argument)
        return self
    
    def args(self, *arguments: str) -> 'CommandBuilder':
        """
        Add multiple arguments to the command.
        
        Args:
            *arguments: Arguments to add
            
        Returns:
            CommandBuilder: Self for method chaining
        """
        self._parts.extend(arguments)
        return self
    
    def flag(self, flag_name: str, prefix: str = "-") -> 'CommandBuilder':
        """
        Add a flag (e.g., --enable-kvm, -v).
        
        Args:
            flag_name: Name of the flag (without prefix)
            prefix: Flag prefix (default: "-")
            
        Returns:
            CommandBuilder: Self for method chaining
        """
        if len(flag_name) == 1:
            self._parts.append(f"{prefix}{flag_name}")
        else:
            prefix = prefix + "-" if prefix == "-" else prefix
            self._parts.append(f"{prefix}{flag_name}")
        return self
    
    def param(self, key: str, value: Union[str, int, Path], prefix: str = "-") -> 'CommandBuilder':
        """
        Add a parameter with key-value pair (e.g., -m 2048, --hda /path/to/image).
        
        Args:
            key: Parameter key
            value: Parameter value
            prefix: Parameter prefix (default: "-")
            
        Returns:
            CommandBuilder: Self for method chaining
        """
        if len(key) == 1:
            self._parts.extend([f"{prefix}{key}", str(value)])
        else:
            prefix = prefix + "-" if prefix == "-" else prefix
            self._parts.extend([f"{prefix}{key}", str(value)])
        return self
    
    def param_if(self, condition: bool, key: str, value: Union[str, int, Path], prefix: str = "-") -> 'CommandBuilder':
        """
        Conditionally add a parameter.
        
        Args:
            condition: Whether to add the parameter
            key: Parameter key
            value: Parameter value  
            prefix: Parameter prefix (default: "-")
            
        Returns:
            CommandBuilder: Self for method chaining
        """
        if condition:
            self.param(key, value, prefix)
        return self
    
    def flag_if(self, condition: bool, flag_name: str, prefix: str = "-") -> 'CommandBuilder':
        """
        Conditionally add a flag.
        
        Args:
            condition: Whether to add the flag
            flag_name: Name of the flag
            prefix: Flag prefix (default: "-")
            
        Returns:
            CommandBuilder: Self for method chaining
        """
        if condition:
            self.flag(flag_name, prefix)
        return self
    
    def arg_if(self, condition: bool, argument: str) -> 'CommandBuilder':
        """
        Conditionally add an argument.
        
        Args:
            condition: Whether to add the argument
            argument: Argument to add
            
        Returns:
            CommandBuilder: Self for method chaining
        """
        if condition:
            self.arg(argument)
        return self
    
    def pipe(self, *pipe_command: str) -> 'CommandBuilder':
        """
        Add a piped command.
        
        Args:
            *pipe_command: Command to pipe to
            
        Returns:
            CommandBuilder: Self for method chaining
        """
        self._pipes.append(list(pipe_command))
        return self
    
    def build(self) -> str:
        """
        Build the final command string.
        
        Returns:
            str: Complete command string
        """
        # Build main command
        main_cmd = " ".join(self._parts)
        
        # Add pipes if any
        if self._pipes:
            pipe_parts = [main_cmd]
            for pipe_cmd in self._pipes:
                pipe_parts.append(" ".join(pipe_cmd))
            return " | ".join(pipe_parts)
        
        return main_cmd
    
    def __str__(self) -> str:
        """String representation of the command."""
        return self.build()


class QEMUCommandBuilder(CommandBuilder):
    """
    Specialized command builder for QEMU commands with common parameter patterns.
    
    Provides convenience methods for typical QEMU parameters like -hda, -hdb, etc.
    """
    
    def __init__(self, launch_script: str, with_sudo: bool = True):
        """
        Initialize QEMU command builder.
        
        Args:
            launch_script: Path to QEMU launch script
            with_sudo: Whether to prefix with sudo -E
        """
        if with_sudo:
            super().__init__("sudo", "-E", launch_script)
        else:
            super().__init__(launch_script)
    
    def param(self, key: str, value: Union[str, int, Path], prefix: str = "-") -> 'QEMUCommandBuilder':
        """
        Override param method to always use single dashes for QEMU launch.sh compatibility.
        
        Args:
            key: Parameter key
            value: Parameter value
            prefix: Parameter prefix (always uses single dash for launch.sh)
            
        Returns:
            QEMUCommandBuilder: Self for method chaining
        """
        # Always use single dash for launch.sh script compatibility
        self._parts.extend([f"-{key}", str(value)])
        return self
    
    def flag(self, flag_name: str, prefix: str = "-") -> 'QEMUCommandBuilder':
        """
        Override flag method to always use single dashes for QEMU launch.sh compatibility.
        
        Args:
            flag_name: Name of the flag (without prefix)
            prefix: Flag prefix (always uses single dash for launch.sh)
            
        Returns:
            QEMUCommandBuilder: Self for method chaining
        """
        # Always use single dash for launch.sh script compatibility
        self._parts.append(f"-{flag_name}")
        return self
    
    def memory(self, mb: Union[str, int]) -> 'QEMUCommandBuilder':
        """Add memory parameter."""
        return self.param("mem", mb)
    
    def smp(self, count: Union[str, int]) -> 'QEMUCommandBuilder':
        """Add SMP (CPU count) parameter."""
        return self.param("smp", count)
    
    def hda(self, image_path: Union[str, Path]) -> 'QEMUCommandBuilder':
        """Add primary hard disk image."""
        return self.param("hda", image_path)
    
    def hdb(self, image_path: Union[str, Path]) -> 'QEMUCommandBuilder':
        """Add secondary hard disk image."""
        return self.param("hdb", image_path)
    
    def bios(self, bios_path: Union[str, Path]) -> 'QEMUCommandBuilder':
        """Add BIOS parameter."""
        return self.param("bios", bios_path)
    
    def load_config(self, config_path: Union[str, Path]) -> 'QEMUCommandBuilder':
        """Add load-config parameter."""
        return self.param("load-config", config_path)
    
    def hb_port(self, port: Union[str, int]) -> 'QEMUCommandBuilder':
        """Add HyperBEAM port parameter."""
        return self.param("hb-port", port)
    
    def qemu_port(self, port: Union[str, int]) -> 'QEMUCommandBuilder':
        """Add QEMU port parameter."""
        return self.param("qemu-port", port)
    
    def debug(self, debug_flag: Union[str, bool]) -> 'QEMUCommandBuilder':
        """Add debug parameter."""
        debug_val = debug_flag if isinstance(debug_flag, str) else ("1" if debug_flag else "0")
        return self.param("debug", debug_val)
    
    def enable_kvm(self, enable: Union[str, bool] = True) -> 'QEMUCommandBuilder':
        """Add enable-kvm parameter."""
        kvm_val = enable if isinstance(enable, str) else ("1" if enable else "0")
        return self.param("enable-kvm", kvm_val)
    
    def enable_tpm(self, enable: Union[str, bool] = True) -> 'QEMUCommandBuilder':
        """Add enable-tpm parameter."""
        tpm_val = enable if isinstance(enable, str) else ("1" if enable else "0")
        return self.param("enable-tpm", tpm_val)
    
    def enable_gpu(self, enable: Union[str,bool] = True) -> 'QEMUCommandBuilder':
        """Add enable-gpu parameter."""
        gpu_val = enable if isinstance(enable, str) else ("1" if enable else "0")
        return self.param("enable-gpu", gpu_val)
    
    def policy(self, policy: str) -> 'QEMUCommandBuilder':
        """Add guest policy parameter."""
        return self.param("policy", policy)
    
    def data_disk(self, disk_path: Union[str, Path]) -> 'QEMUCommandBuilder':
        """Add data disk parameter."""
        return self.param("data-disk", disk_path)
    
    def enable_ssl(self, enable: Union[str, bool] = True) -> 'QEMUCommandBuilder':
        """Add enableSSL parameter."""
        ssl_val = enable if isinstance(enable, str) else ("1" if enable else "0")
        return self.param("enableSSL", ssl_val)
    



# -----------------------------------------------------------------------------
# Command Execution Utilities
# -----------------------------------------------------------------------------

def run_command(cmd, cwd=None, check=True, shell=True, ignore_errors=False, capture_output=False):
    """
    Run a shell command with comprehensive error handling and logging.
    
    Args:
        cmd (str or list): Command to execute
        cwd (str, optional): Working directory to run command in
        check (bool): Whether to raise exception on non-zero exit codes
        shell (bool): Whether to run command through shell
        ignore_errors (bool): Whether to continue execution on errors
        capture_output (bool): Whether to capture stdout/stderr
    
    Returns:
        subprocess.CompletedProcess: Result of the command execution
    """
    print(f"Running: {cmd if isinstance(cmd, str) else ' '.join(cmd)}")
    
    try:
        result = subprocess.run(
            cmd,
            shell=shell,
            check=check,
            cwd=cwd,
            capture_output=capture_output,
            text=capture_output
        )
        return result
    except subprocess.CalledProcessError as e:
        if not ignore_errors:
            print(f"Command failed with exit code {e.returncode}: {cmd}")
            if capture_output:
                print(f"stdout: {e.stdout}")
                print(f"stderr: {e.stderr}")
            
            # Convert to standardized exception instead of sys.exit()
            command_str = cmd if isinstance(cmd, str) else ' '.join(cmd)
            raise handle_subprocess_error(e, f"Failed to execute command: {command_str}")
        else:
            print(f"Command failed but continuing due to ignore_errors=True: {cmd}")
            return e


def run_command_silent(cmd, cwd=None, check=False):
    """
    Run a command silently (suppressing output), typically for cleanup operations.
    
    Args:
        cmd (str or list): Command to execute
        cwd (str, optional): Working directory
        check (bool): Whether to check return code (default False for cleanup)
    
    Returns:
        subprocess.CompletedProcess: Result of the command execution
    """
    return subprocess.run(
        cmd,
        shell=isinstance(cmd, str),
        check=check,
        cwd=cwd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )


# -----------------------------------------------------------------------------
# Directory and File Operations
# -----------------------------------------------------------------------------

def ensure_directory(path):
    """
    Ensure a directory exists, creating it if necessary.
    
    Args:
        path (str): Directory path to create
    """
    os.makedirs(path, exist_ok=True)
    print(f"Ensured directory exists: {path}")


def remove_directory(path):
    """
    Remove a directory tree if it exists.
    
    Args:
        path (str): Directory path to remove
    """
    if os.path.exists(path):
        shutil.rmtree(path)
        print(f"Removed directory: {path}")


def ensure_parent_directory(file_path):
    """
    Ensure the parent directory of a file exists.
    
    Args:
        file_path (str): File path whose parent directory should exist
    """
    parent_dir = os.path.dirname(file_path)
    if parent_dir:
        ensure_directory(parent_dir)


def replace_in_file(file_path, replacements):
    """
    Replace multiple strings in a file.
    
    Args:
        file_path (str): Path to the file
        replacements (dict): Dictionary of {old_string: new_string} replacements
    """
    with open(file_path, 'r') as f:
        content = f.read()
    
    for old_str, new_str in replacements.items():
        content = content.replace(old_str, new_str)
    
    with open(file_path, 'w') as f:
        f.write(content)


# -----------------------------------------------------------------------------
# Template and Configuration Utilities
# -----------------------------------------------------------------------------

def process_dockerfile_template(dockerfile_path, template_vars):
    """
    DEPRECATED: Use DockerfileTemplateProcessor from docker_service instead.
    
    Process a Dockerfile template by replacing template variables.
    
    Args:
        dockerfile_path (str): Path to the Dockerfile template
        template_vars (dict): Dictionary of template variables to replace
    
    Returns:
        tuple: (original_content, modified_content) for restoration later
    """
    import warnings
    warnings.warn(
        "process_dockerfile_template is deprecated. Use DockerfileTemplateProcessor from docker_service instead.",
        DeprecationWarning,
        stacklevel=2
    )
    
    with open(dockerfile_path, 'r') as f:
        original_content = f.read()
    
    modified_content = original_content
    for var, value in template_vars.items():
        modified_content = modified_content.replace(f"<{var}>", value)
    
    with open(dockerfile_path, 'w') as f:
        f.write(modified_content)
    
    return original_content, modified_content


def restore_file_content(file_path, original_content):
    """
    DEPRECATED: Use DockerfileTemplateProcessor from docker_service instead.
    
    Restore original content to a file.
    
    Args:
        file_path (str): Path to the file to restore
        original_content (str): Original content to restore
    """
    import warnings
    warnings.warn(
        "restore_file_content is deprecated. Use DockerfileTemplateProcessor from docker_service instead.",
        DeprecationWarning,
        stacklevel=2
    )
    
    with open(file_path, 'w') as f:
        f.write(original_content)


# -----------------------------------------------------------------------------
# Error Reporting Utilities
# -----------------------------------------------------------------------------

def err_report(line_no):
    """
    Report error information with line number.
    
    Args:
        line_no: Line number where error occurred
    """
    print(f"Error occurred at line {line_no}")
    tb = traceback.extract_tb(sys.exc_info()[2])
    if tb:
        print(f"Traceback: {tb[-1]}")