#!/usr/bin/env python3
"""
Command Execution Service Implementation.

This service wraps the existing command execution utilities and provides them as injectable dependencies.
"""

from typing import Optional, List, Union
from subprocess import CompletedProcess
from src.core.service_interfaces import ICommandExecutionService
from src.utils import run_command as util_run_command, run_command_silent as util_run_command_silent


class CommandExecutionService(ICommandExecutionService):
    """Injectable command execution service that wraps utility functions."""
    
    def run_command(self, cmd: Union[str, List[str]], cwd: Optional[str] = None, 
                   check: bool = True, shell: bool = True, ignore_errors: bool = False, 
                   capture_output: bool = False) -> CompletedProcess:
        """
        Run a shell command with comprehensive error handling and logging.
        
        Args:
            cmd: Command to execute
            cwd: Working directory to run command in
            check: Whether to raise exception on non-zero exit codes
            shell: Whether to run command through shell
            ignore_errors: Whether to continue execution on errors
            capture_output: Whether to capture stdout/stderr
        
        Returns:
            Result of the command execution
        """
        return util_run_command(cmd, cwd=cwd, check=check, shell=shell, 
                               ignore_errors=ignore_errors, capture_output=capture_output)
    
    def run_command_silent(self, cmd: Union[str, List[str]], cwd: Optional[str] = None, 
                          check: bool = False) -> CompletedProcess:
        """
        Run a command silently with minimal output.
        
        Args:
            cmd: Command to execute
            cwd: Working directory to run command in
            check: Whether to raise exception on non-zero exit codes
        
        Returns:
            Result of the command execution
        """
        return util_run_command_silent(cmd, cwd=cwd, check=check)