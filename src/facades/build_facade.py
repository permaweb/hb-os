#!/usr/bin/env python3
"""
Build Facade Implementation.

This facade simplifies build operations and orchestration.
"""

import os
from typing import Optional, Dict
from src.core.facade_interfaces import IBuildFacade
from src.core.service_interfaces import (
    IConfigurationService, ICommandExecutionService, 
    IDockerService, IFileSystemService
)

class BuildFacade(IBuildFacade):
    """
    Facade for build operations and orchestration.
    
    Provides high-level methods for building VM images and components.
    """

    
    def __init__(self, config_service: IConfigurationService,
                 command_service: ICommandExecutionService,
                 docker_service: IDockerService,
                 fs_service: IFileSystemService):
        """
        Initialize BuildFacade with injected dependencies.
        
        Args:
            config_service: Configuration service for accessing settings
            command_service: Command execution service
            docker_service: Docker service for container operations
            fs_service: File system service
        """
        self._config = config_service
        self._command = command_service
        self._docker = docker_service
        self._fs = fs_service
    
    def build_complete_system(self, hb_branch: Optional[str] = None, 
                             ao_branch: Optional[str] = None,
                             amdsev_path: Optional[str] = None) -> None:
        """
        Build the complete HyperBEAM system from scratch.
        
        This orchestrates the full build process including SNP packages,
        base image, and guest image with content.
        
        Args:
            hb_branch: HyperBEAM branch to use
            ao_branch: AO branch to use  
            amdsev_path: Optional local AMDSEV repository path
        """
        print("🏗️  Starting complete system build...")
        
        # Update configuration if branches specified
        if hb_branch:
            # Set the branch through the underlying config since ConfigurationService doesn't expose setters
            self._config.config.build.hb_branch = hb_branch
        if ao_branch:
            self._config.config.build.ao_branch = ao_branch
        
        # Step 1: Build SNP packages if needed
        if amdsev_path or not self._snp_packages_exist():
            print("📦 Building SNP packages...")
            self.build_snp_packages(amdsev_path)
        else:
            print("✅ SNP packages already exist, skipping...")
        
        # Step 2: Build base VM image
        print("🖼️  Building base VM image...")
        self.build_base_image()
        
        # Step 3: Build guest image with content
        print("👥 Building guest VM image...")
        self.build_guest_image(hb_branch, ao_branch)
        
        print("✅ Complete system build finished!")
    
    def build_snp_packages(self, amdsev_path: Optional[str] = None) -> None:
        """
        Build SNP packages (kernel, OVMF, QEMU) from source.
        
        Args:
            amdsev_path: Optional local AMDSEV repository path
        """
        print("📦 Building SNP packages from source...")
        
        # Import here to avoid circular dependencies
        from src.core.build_snp_packages import build_snp_packages
        build_snp_packages(self._config.config, amdsev_path)
        
        print("✅ SNP packages build complete!")
    
    def build_base_image(self) -> None:
        """
        Build the base VM image.
        
        This orchestrates kernel unpacking, initramfs building,
        VM creation, configuration, and hash generation.
        """
        print("🖼️  Building base VM image...")
        
        # Step 1: Unpack kernel
        print("  📦 Unpacking kernel...")
        self._unpack_kernel()
        
        # Step 2: Build initramfs
        print("  🗃️  Building initramfs...")
        self._build_initramfs()
        
        # Step 3: Create VM image
        print("  💿 Creating VM image...")
        self._create_vm_image()
        
        # Step 4: Setup VM configuration
        print("  ⚙️  Setting up VM configuration...")
        self._setup_vm_config()
        
        # Step 5: Generate hashes
        print("  🔐 Generating measurement hashes...")
        self._generate_hashes()
        
        print("✅ Base image build complete!")
    
    def build_guest_image(self, hb_branch: Optional[str] = None,
                         ao_branch: Optional[str] = None) -> None:
        """
        Build the guest VM image with content.
        
        This orchestrates guest content building, dm-verity setup,
        configuration, and hash generation.
        
        Args:
            hb_branch: HyperBEAM branch to use
            ao_branch: AO branch to use
        """
        print("👥 Building guest VM image...")
        
        # Step 1: Build guest content
        print("  📦 Building guest content...")
        self._build_guest_content(hb_branch, ao_branch)
        
        # Step 2: Setup dm-verity
        print("  🔒 Setting up dm-verity...")
        self._setup_verity()
        
        # Step 3: Setup VM configuration
        print("  ⚙️  Setting up VM configuration...")
        self._setup_vm_config()
        
        # Step 4: Generate hashes
        print("  🔐 Generating measurement hashes...")
        self._generate_hashes()
        
        print("✅ Guest image build complete!")
    
    def get_build_status(self) -> Dict[str, bool]:
        """
        Get the status of various build components.
        
        Returns:
            Dictionary mapping component names to their build status
        """
        status = {}
        
        # Check base image components
        status['kernel_unpacked'] = os.path.exists(self._config.kernel_dir)
        status['initramfs_built'] = os.path.exists(self._config.initrd)
        status['vm_image_created'] = os.path.exists(self._config.config.vm_image_base_path)
        
        # Check guest image components
        status['guest_content_built'] = os.path.exists(self._config.content_dir)
        status['verity_image'] = os.path.exists(self._config.verity_image)
        status['verity_hash_tree'] = os.path.exists(self._config.verity_hash_tree)
        
        # Check configuration files
        status['vm_config'] = os.path.exists(self._config.vm_config_file)
        status['inputs_json'] = os.path.exists("inputs.json")
        
        # Check SNP packages
        status['snp_packages'] = self._snp_packages_exist()
        
        return status
    
    def _unpack_kernel(self) -> None:
        """Unpack the kernel package from a .deb file."""
        import glob
        
        kernel_dir = self._config.kernel_dir
        kernel_deb_pattern = self._config.config.kernel_deb
        
        # Find all matching .deb files
        deb_files = glob.glob(kernel_deb_pattern)
        
        # Filter out debug packages (contain -dbg)
        main_deb_files = [f for f in deb_files if '-dbg' not in f]
        
        if not main_deb_files:
            raise RuntimeError(f"No kernel .deb files found matching: {kernel_deb_pattern}")
        
        if len(main_deb_files) > 1:
            print(f"Warning: Multiple kernel packages found: {main_deb_files}")
            print(f"Using the first one: {main_deb_files[0]}")
        
        kernel_deb = main_deb_files[0]
        print(f"Unpacking kernel from: {kernel_deb}")
        
        self._command.run_command(f"rm -rf {kernel_dir}")
        self._command.run_command(f"dpkg -x {kernel_deb} {kernel_dir}")
    
    def _build_initramfs(self) -> None:
        """Build the initramfs image."""
        from src.core.build_initramfs import build_initramfs
        
        build_initramfs(
            kernel_dir=self._config.kernel_dir,
            init_script=self._config.config.initramfs_script,
            dockerfile=self._config.config.initramfs_dockerfile,
            context_dir=self._config.config.dirs.resources,
            out=self._config.initrd,
            build_dir=self._config.build_dir,
        )
    
    def _create_vm_image(self) -> None:
        """Create a new virtual machine image."""
        from src.core.create_new_vm import create_vm_image
        
        create_vm_image(
            new_vm=self._config.config.vm_image_base_name,
            build_dir=self._config.guest_dir,
            template_user_data=self._config.config.vm_template_user_data
        )
    
    def _build_guest_content(self, hb_branch: Optional[str], ao_branch: Optional[str]) -> None:
        """Build the guest content using Docker."""
        from src.core.build_content import build_guest_content
        
        effective_hb_branch = hb_branch or self._config.hb_branch
        effective_ao_branch = ao_branch or self._config.ao_branch
        
        build_guest_content(
            out_dir=self._config.content_dir, 
            dockerfile=self._config.config.content_dockerfile, 
            hb_branch=effective_hb_branch,
            ao_branch=effective_ao_branch
        )
    
    def _setup_verity(self) -> None:
        """Set up dm-verity for the guest image."""
        from src.core.setup_guest import setup_guest
        
        setup_guest(
            src_image=self._config.config.vm_image_base_path,
            build_dir=self._config.build_dir,
            out_image=self._config.verity_image,
            out_hash_tree=self._config.verity_hash_tree,
            out_root_hash=self._config.config.verity_root_hash,
            debug=self._config.debug,
        )
    
    def _setup_vm_config(self) -> None:
        """Create the virtual machine configuration file."""
        from src.core.create_vm_config import create_vm_config_file
        
        # Build VM configuration definition
        vm_config_definition = {
            "host_cpu_family": self._config.config.host_cpu_family,
            "vcpu_count": self._config.vcpu_count,
            "guest_features": self._config.config.guest_features,
            "platform_info": self._config.config.platform_info,
            "guest_policy": self._config.config.guest_policy,
            "family_id": self._config.config.family_id,
            "image_id": self._config.config.image_id,
            "min_committed_tcb": self._config.config.min_committed_tcb,
        }
        
        create_vm_config_file(
            out_path=self._config.vm_config_file,
            ovmf_path=self._config.config.ovmf,
            kernel_path=self._config.kernel_vmlinuz,
            initrd_path=self._config.initrd,
            kernel_cmdline=f"{self._config.config.cmdline} {self._config.config.verity_params}",
            vm_config=vm_config_definition,
        )
    
    def _generate_hashes(self) -> None:
        """Generate measurement inputs (hashes) from the VM configuration."""
        digest_calc_path = os.path.join(self._config.config.dirs.bin, "digest_calc")
        out_file = os.path.join(os.getcwd(), "inputs.json")
        self._command.run_command(
            f"{digest_calc_path} --vm-definition {self._config.vm_config_file} > {out_file}"
        )
    
    def _snp_packages_exist(self) -> bool:
        """Check if SNP packages have been built."""
        build_dir = self._config.build_dir
        snp_release_dir = os.path.join(build_dir, "snp-release")
        
        # Check for key SNP package files
        required_files = [
            os.path.join(snp_release_dir, "linux-image-6.4.0-snp-guest_6.4.0-1_amd64.deb"),
            os.path.join(snp_release_dir, "ovmf", "OVMF.fd"),
            os.path.join(snp_release_dir, "qemu-snp-build", "usr", "local", "bin", "qemu-system-x86_64")
        ]
        
        return all(os.path.exists(f) for f in required_files)