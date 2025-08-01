#!/usr/bin/env python3
"""
Release Facade Implementation.

This facade simplifies release management operations.
"""

import os
from typing import Optional, Dict, Any
from src.core.facade_interfaces import IReleaseFacade
from src.core.service_interfaces import IConfigurationService, ICommandExecutionService, IFileSystemService


class ReleaseFacade(IReleaseFacade):
    """
    Facade for release management operations.
    
    Provides high-level methods for packaging, distributing, and managing releases.
    """
    
    def __init__(self, config_service: IConfigurationService,
                 command_service: ICommandExecutionService,
                 fs_service: IFileSystemService):
        """
        Initialize ReleaseFacade with injected dependencies.
        
        Args:
            config_service: Configuration service for accessing settings
            command_service: Command execution service
            fs_service: File system service
        """
        self._config = config_service
        self._command = command_service
        self._fs = fs_service
    
    def create_release_package(self, output_path: Optional[str] = None) -> str:
        """
        Create a complete release package.
        
        This orchestrates the packaging of all required files into a distributable archive.
        
        Args:
            output_path: Optional custom output path for the release
            
        Returns:
            Path to the created release package
        """
        print("📦 Creating release package...")
        
        # Import here to avoid circular dependencies
        from src.services.release_manager import package_release
        
        # Create the release package
        package_release()
        
        # Determine output path
        if output_path is None:
            output_path = os.path.join(os.getcwd(), "release.tar.gz")
        
        # Create tarball if it doesn't exist
        release_dir = os.path.join(os.getcwd(), "release")
        if os.path.exists(release_dir) and not os.path.exists(output_path):
            print(f"📁 Creating archive: {output_path}")
            self._command.run_command(f"tar -czf {output_path} -C {os.getcwd()} release")
        
        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            print(f"✅ Release package created: {output_path} ({file_size / (1024*1024):.1f} MB)")
        else:
            print(f"✅ Release folder created: {release_dir}")
            output_path = release_dir
        
        return output_path
    
    def download_and_install_release(self, url: str, 
                                   verify_checksum: bool = True) -> None:
        """
        Download and install a release package.
        
        Args:
            url: URL to the release package
            verify_checksum: Whether to verify package integrity
        """
        print(f"⬇️  Downloading release from: {url}")
        
        # Import here to avoid circular dependencies
        from src.services.release_manager import download_release
        
        # Download the release
        download_release(url)
        
        # TODO: Add checksum verification if requested
        if verify_checksum:
            print("⚠️  Checksum verification not yet implemented")
        
        print("✅ Release downloaded and installed successfully!")
    
    def clean_build_artifacts(self, keep_downloads: bool = True) -> None:
        """
        Clean up build artifacts and temporary files.
        
        Args:
            keep_downloads: Whether to preserve downloaded files
        """
        print("🧹 Cleaning build artifacts...")
        
        # Import here to avoid circular dependencies
        from src.services.release_manager import clean
        
        # Clean using the existing clean function
        clean()
        
        if not keep_downloads:
            # Additional cleanup of downloaded files
            downloads_to_clean = [
                "snp-release.tar.gz",
                "ubuntu-22.04.3-server-cloudimg-amd64.img"
            ]
            
            for download in downloads_to_clean:
                download_path = os.path.join(self._config.build_dir, download)
                if os.path.exists(download_path):
                    print(f"  🗑️  Removing: {download}")
                    os.remove(download_path)
        
        print("✅ Build artifacts cleaned!")
    
    def list_available_releases(self) -> Dict[str, Any]:
        """
        List information about available releases.
        
        Returns:
            Dictionary with release information
        """
        releases = {
            'local_releases': [],
            'build_artifacts': {},
            'remote_releases': []
        }
        
        # Check for local release packages
        current_dir = os.getcwd()
        for item in os.listdir(current_dir):
            if item.endswith('.tar.gz') and 'release' in item.lower():
                item_path = os.path.join(current_dir, item)
                releases['local_releases'].append({
                    'name': item,
                    'path': item_path,
                    'size_mb': os.path.getsize(item_path) / (1024*1024),
                    'modified': os.path.getmtime(item_path)
                })
        
        # Check for release directory
        release_dir = os.path.join(current_dir, "release")
        if os.path.exists(release_dir):
            releases['build_artifacts']['release_folder'] = {
                'path': release_dir,
                'files': len(os.listdir(release_dir)),
                'size_mb': self._get_directory_size(release_dir) / (1024*1024)
            }
        
        # Check for built artifacts
        artifacts = {
            'verity_image': self._config.verity_image,
            'verity_hash_tree': self._config.verity_hash_tree,
            'vm_config': self._config.vm_config_file,
            'kernel': self._config.kernel_vmlinuz,
            'initrd': self._config.initrd
        }
        
        for name, path in artifacts.items():
            if os.path.exists(path):
                releases['build_artifacts'][name] = {
                    'path': path,
                    'size_mb': os.path.getsize(path) / (1024*1024),
                    'modified': os.path.getmtime(path)
                }
        
        # TODO: Add information about remote releases if available
        releases['remote_releases'] = [
            {
                'name': 'SNP Release v0.1.2',
                'url': 'https://github.com/SNPGuard/snp-guard/releases/download/v0.1.2/snp-release.tar.gz',
                'description': 'Latest stable SNP release'
            }
        ]
        
        return releases
    
    def _get_directory_size(self, directory: str) -> int:
        """Get the total size of a directory and its contents."""
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(directory):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                if os.path.exists(filepath):
                    total_size += os.path.getsize(filepath)
        return total_size