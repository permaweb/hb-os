#!/usr/bin/env python3
"""
File System Service Implementation.

This service wraps the existing file system utilities and provides them as injectable dependencies.
"""

from typing import Dict
from src.core.service_interfaces import IFileSystemService
from src.utils import (
    ensure_directory as util_ensure_directory, 
    remove_directory as util_remove_directory,
    ensure_parent_directory as util_ensure_parent_directory,
    replace_in_file as util_replace_in_file
)


class FileSystemService(IFileSystemService):
    """Injectable file system service that wraps utility functions."""
    
    def ensure_directory(self, path: str) -> None:
        """
        Ensure that a directory exists, creating it if necessary.
        
        Args:
            path: Directory path to ensure exists
        """
        util_ensure_directory(path)
    
    def remove_directory(self, path: str) -> None:
        """
        Remove a directory and all its contents.
        
        Args:
            path: Directory path to remove
        """
        util_remove_directory(path)
    
    def ensure_parent_directory(self, file_path: str) -> None:
        """
        Ensure that the parent directory of a file exists.
        
        Args:
            file_path: File path whose parent directory should exist
        """
        util_ensure_parent_directory(file_path)
    
    def replace_in_file(self, file_path: str, replacements: Dict[str, str]) -> None:
        """
        Replace text patterns in a file.
        
        Args:
            file_path: Path to the file to modify
            replacements: Dictionary mapping search patterns to replacement text
        """
        util_replace_in_file(file_path, replacements)