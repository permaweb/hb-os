#!/usr/bin/env python3
"""
SNP Component Builder

Core functionality for building SNP components (kernel, OVMF, QEMU).
Converted from convert/common.sh and build.sh shell scripts.
"""

import os
import shutil
import subprocess
import multiprocessing
from pathlib import Path
from typing import List, Optional, Dict, Tuple
from datetime import datetime

from src.utils.snp_config import SNPConfigManager
from src.utils import run_command, run_command_silent, ensure_directory, HyperBeamError


class SNPBuildError(HyperBeamError):
    """Exception raised when SNP component build fails."""
    
    def __init__(self, message: str, component: str, phase: str = "build", cause: Exception = None):
        super().__init__(message, "snp_build", cause)
        self.component = component
        self.phase = phase


class SNPComponentBuilder:
    """Builder for individual SNP components."""
    
    def __init__(self, config_manager: Optional[SNPConfigManager] = None):
        self.config = config_manager or SNPConfigManager()
        self.cpu_count = multiprocessing.cpu_count()
    
    def _run_cmd(self, cmd: str, cwd: Optional[str] = None, silent: bool = False) -> str:
        """Execute command with error handling."""
        print(f"Running: {cmd}")
        try:
            if silent:
                return run_command_silent(cmd, cwd=cwd)
            else:
                return run_command(cmd, cwd=cwd)
        except Exception as e:
            raise SNPBuildError(f"Command failed: {cmd}", "general", "command", e)
    
    def _setup_git_repo(self, repo_dir: str, git_url: str, branch: str, 
                       remote_name: str = "current") -> str:
        """Setup or update git repository."""
        repo_path = Path(repo_dir)
        
        if repo_path.exists():
            # Update existing repository
            try:
                # Check if remote exists and update URL
                get_url_cmd = f"git remote get-url {remote_name}"
                self._run_cmd(get_url_cmd, cwd=repo_dir, silent=True)
                # Remote exists, update it
                self._run_cmd(f"git remote set-url {remote_name} {git_url}", cwd=repo_dir)
            except:
                # Remote doesn't exist, add it
                self._run_cmd(f"git remote add {remote_name} {git_url}", cwd=repo_dir)
        else:
            # Clone new repository
            self._run_cmd(f"git clone --single-branch -b {branch} {git_url} {repo_dir}")
            self._run_cmd(f"git remote add {remote_name} {git_url}", cwd=repo_dir)
        
        # Fetch and checkout
        self._run_cmd(f"git fetch {remote_name}", cwd=repo_dir)
        self._run_cmd(f"git checkout {remote_name}/{branch}", cwd=repo_dir)
        
        # Get current commit hash
        import subprocess
        result = subprocess.run(
            "git log --format='%h' -1 HEAD", 
            shell=True, 
            cwd=repo_dir, 
            capture_output=True, 
            text=True, 
            check=True
        )
        return result.stdout.strip().strip("'")
    
    def _safe_copytree(self, src: str, dst: str) -> None:
        """
        Safely copy directory tree, handling missing files and broken symlinks.
        
        Args:
            src: Source directory path
            dst: Destination directory path
        """
        def _ignore_missing_files(src_dir, names):
            """Ignore function that skips files that don't exist or can't be accessed."""
            ignored = []
            for name in names:
                src_path = os.path.join(src_dir, name)
                try:
                    # Check if file/directory exists and is accessible
                    if os.path.islink(src_path):
                        # For symlinks, check if target exists
                        if not os.path.exists(src_path):
                            ignored.append(name)
                    elif not os.path.exists(src_path):
                        ignored.append(name)
                except (OSError, IOError):
                    # If we can't even check the file, ignore it
                    ignored.append(name)
            return ignored
        
        try:
            shutil.copytree(src, dst, ignore=_ignore_missing_files)
        except Exception as e:
            print(f"Warning: Some files could not be copied during copytree: {e}")
            # Try a simpler approach - copy what we can
            self._run_cmd(f"cp -r {src}/* {dst}/ 2>/dev/null || true", silent=True)
    
    def _configure_kernel(self, kernel_dir: str, kernel_type: str, commit: str) -> None:
        """Configure kernel with SNP-specific options."""
        config_path = self.config.get_kernel_config_path(kernel_type)
        
        print(f"Using {config_path} as template kernel configuration.")
        
        # Copy base config
        self._run_cmd(f"cp {config_path} .config", cwd=kernel_dir)
        
        # Set version string
        version_suffix = f"-snp-{kernel_type}-{commit}"
        self._run_cmd(f"./scripts/config --set-str LOCALVERSION '{version_suffix}'", cwd=kernel_dir)
        self._run_cmd("./scripts/config --disable LOCALVERSION_AUTO", cwd=kernel_dir)
        
        # Apply SNP-specific configuration options
        for option, action in self.config.kernel.config_options.items():
            if action == "enable":
                self._run_cmd(f"./scripts/config --enable {option}", cwd=kernel_dir)
            elif action == "disable":
                self._run_cmd(f"./scripts/config --disable {option}", cwd=kernel_dir)
            elif action == "module":
                self._run_cmd(f"./scripts/config --module {option}", cwd=kernel_dir)
            elif action.isdigit():
                self._run_cmd(f"./scripts/config --set-val {option} {action}", cwd=kernel_dir)
        
        # Run olddefconfig to finalize configuration
        self._run_cmd("yes '' | make olddefconfig", cwd=kernel_dir)
    
    def build_kernel(self, kernel_type: Optional[str] = None, build_dir: str = ".") -> List[str]:
        """
        Build SNP-enabled kernel(s).
        
        Args:
            kernel_type: 'host', 'guest', or None for both
            build_dir: Directory to build in
            
        Returns:
            List of built package files
        """
        print(f"===> Building SNP kernel ({kernel_type or 'both'})")
        
        linux_dir = os.path.join(build_dir, "linux")
        ensure_directory(linux_dir)
        
        built_packages = []
        kernel_types = [kernel_type] if kernel_type else ["guest", "host"]
        
        for ktype in kernel_types:
            if ktype not in ["guest", "host"]:
                raise SNPBuildError(f"Invalid kernel type: {ktype}", "kernel", "validation")
            
            kernel_dir = os.path.join(linux_dir, ktype)
            
            # Setup repository
            if not os.path.exists(kernel_dir):
                if ktype == "guest":
                    # Clone guest repo
                    branch = self.config.get_kernel_branch("guest")
                    commit = self._setup_git_repo(kernel_dir, self.config.repository.kernel_git_url, branch)
                else:
                    # Copy guest repo as host repo base
                    guest_dir = os.path.join(linux_dir, "guest")
                    if not os.path.exists(guest_dir):
                        raise SNPBuildError("Guest kernel must be built before host kernel", "kernel", "dependency")
                    self._safe_copytree(guest_dir, kernel_dir)
            
            # Update repository for this kernel type
            branch = self.config.get_kernel_branch(ktype)
            commit = self._setup_git_repo(kernel_dir, self.config.repository.kernel_git_url, branch)
            
            # Clean previous builds
            make_cmd = f"make -j {self.cpu_count} LOCALVERSION="
            self._run_cmd(f"{make_cmd} distclean", cwd=kernel_dir)
            
            # Configure kernel
            self._configure_kernel(kernel_dir, ktype, commit)
            
            # Build kernel
            print(f"Building {ktype} kernel...")
            self._run_cmd(make_cmd, cwd=kernel_dir, silent=True)
            
            # Build packages
            import platform
            if self._is_debian_based():
                # Clean any previous debian build artifacts
                debian_dir = os.path.join(kernel_dir, "debian")
                if os.path.exists(debian_dir):
                    shutil.rmtree(debian_dir)
                
                try:
                    self._run_cmd(f"{make_cmd} bindeb-pkg", cwd=kernel_dir)
                except Exception as e:
                    print(f"Warning: Package build had issues but may have still succeeded: {e}")
                    # Continue to look for packages anyway
                
                # Find built .deb packages
                pattern = f"linux-*-snp-{ktype}*.deb"
                packages = list(Path(linux_dir).glob(pattern))
                print(f"Found {len(packages)} packages for {ktype}: {[p.name for p in packages]}")
            else:
                rpm_opts = '--define "_rpmdir ."'
                self._run_cmd(f"{make_cmd} RPMOPTS='{rpm_opts}' binrpm-pkg", cwd=kernel_dir)
                self._run_cmd(f"mv {kernel_dir}/x86_64/*.rpm {linux_dir}/", cwd=kernel_dir)
                packages = list(Path(linux_dir).glob("kernel-*.rpm"))
            
            built_packages.extend([str(p) for p in packages])
            
            # Save commit info
            commit_file = os.path.join(build_dir, f"source-commit.kernel.{ktype}")
            with open(commit_file, 'w') as f:
                f.write(commit)
        
        print(f"✅ Kernel build completed. Built packages: {built_packages}")
        return built_packages
    
    def build_ovmf(self, install_dir: str, build_dir: str = ".") -> str:
        """
        Build and install OVMF firmware.
        
        Args:
            install_dir: Directory to install OVMF files
            build_dir: Directory to build in
            
        Returns:
            Path to built OVMF file
        """
        print("===> Building OVMF firmware")
        
        ovmf_dir = os.path.join(build_dir, "ovmf") 
        
        # Setup repository
        commit = self._setup_git_repo(
            ovmf_dir, 
            self.config.repository.ovmf_git_url,
            self.config.repository.ovmf_branch
        )
        
        # Initialize submodules
        self._run_cmd("git submodule update --init --recursive", cwd=ovmf_dir)
        
        # Build base tools
        self._run_cmd(f"make -C BaseTools clean", cwd=ovmf_dir)
        self._run_cmd(f"make -C BaseTools -j {self.cpu_count}", cwd=ovmf_dir)
        
        # Setup build environment and build OVMF
        # Note: edksetup.sh must be sourced in the same shell as the build command
        self._run_cmd("touch OvmfPkg/AmdSev/Grub/grub.efi", cwd=ovmf_dir)
        
        # Determine GCC version for build
        gcc_version = self._get_gcc_version()
        
        # Build OVMF - combine environment setup with build in single command
        build_args = [
            "nice", "build",
            *self.config.ovmf.build_args,
            f"-n {self.cpu_count}",
            f"-t {gcc_version}",
        ]
        
        build_cmd = " ".join(build_args)
        combined_cmd = f". ./edksetup.sh --reconfig && {build_cmd}"
        self._run_cmd(combined_cmd, cwd=ovmf_dir)
        
        # Install built firmware
        ensure_directory(install_dir)
        built_ovmf = f"Build/AmdSev/DEBUG_{gcc_version}/FV/OVMF.fd"
        dest_ovmf = os.path.join(install_dir, "DIRECT_BOOT_OVMF.fd")
        
        self._run_cmd(f"cp -f {built_ovmf} {dest_ovmf}", cwd=ovmf_dir)
        
        # Save commit info
        commit_file = os.path.join(build_dir, "source-commit.ovmf")
        with open(commit_file, 'w') as f:
            f.write(commit)
        
        print(f"✅ OVMF build completed: {dest_ovmf}")
        return dest_ovmf
    
    def build_qemu(self, install_dir: str, build_dir: str = ".") -> str:
        """
        Build and install QEMU.
        
        Args:
            install_dir: Directory to install QEMU
            build_dir: Directory to build in
            
        Returns:
            Path to QEMU installation
        """
        print("===> Building QEMU")
        
        qemu_dir = os.path.join(build_dir, "qemu")
        
        # Setup repository
        commit = self._setup_git_repo(
            qemu_dir,
            self.config.repository.qemu_git_url, 
            self.config.repository.qemu_branch
        )
        
        # Configure QEMU build
        configure_args = [*self.config.qemu.configure_args, f"--prefix={install_dir}"]
        configure_cmd = "./configure " + " ".join(configure_args)
        self._run_cmd(configure_cmd, cwd=qemu_dir)
        
        # Build and install
        make_cmd = f"make -j {self.cpu_count} LOCALVERSION="
        self._run_cmd(make_cmd, cwd=qemu_dir)
        self._run_cmd(f"{make_cmd} install", cwd=qemu_dir)
        
        # Save commit info
        commit_file = os.path.join(build_dir, "source-commit.qemu")
        with open(commit_file, 'w') as f:
            f.write(commit)
        
        print(f"✅ QEMU build completed: {install_dir}")
        return install_dir
    
    def create_kvm_config(self, output_path: str) -> str:
        """Create KVM configuration file."""
        content = self.config.kvm.to_conf_content()
        
        with open(output_path, 'w') as f:
            f.write(content)
        
        print(f"✅ KVM config created: {output_path}")
        return output_path
    
    def _is_debian_based(self) -> bool:
        """Check if running on Debian-based system."""
        try:
            with open('/etc/os-release', 'r') as f:
                content = f.read()
                return 'ID=debian' in content or 'ID_LIKE=debian' in content
        except:
            return False
    
    def _get_gcc_version(self) -> str:
        """Get GCC version string for OVMF build."""
        try:
            result = subprocess.run(['gcc', '-v'], capture_output=True, text=True, stderr=subprocess.STDOUT)
            output_lines = result.stdout.strip().split('\n')
            version_line = output_lines[-1]  # Last line contains version
            
            version = version_line.split()[-1]  # Extract version number
            major, minor = version.split('.')[:2]
            
            if major == "4":
                return f"GCC{major}{minor}"
            else:
                return "GCC5"
        except:
            return "GCC5"  # Default fallback


class SNPBuildOrchestrator:
    """High-level orchestrator for SNP component builds."""
    
    def __init__(self, config_manager: Optional[SNPConfigManager] = None):
        self.config = config_manager or SNPConfigManager()
        self.builder = SNPComponentBuilder(config_manager)
    
    def build_all_components(self, install_dir: str, build_dir: str = ".", 
                           kernel_type: Optional[str] = None) -> Dict[str, any]:
        """
        Build all SNP components.
        
        Args:
            install_dir: Directory to install components
            build_dir: Directory to build in  
            kernel_type: Specific kernel type or None for both
            
        Returns:
            Dictionary with build results
        """
        print("🚀 Starting SNP component build process")
        
        results = {}
        
        try:
            # Build QEMU
            results['qemu'] = self.builder.build_qemu(install_dir, build_dir)
            
            # Build OVMF (install to share/qemu subdirectory)
            ovmf_install_dir = os.path.join(install_dir, "share", "qemu")
            results['ovmf'] = self.builder.build_ovmf(ovmf_install_dir, build_dir)
            
            # Build kernel(s)  
            results['kernel_packages'] = self.builder.build_kernel(kernel_type, build_dir)
            
            # Create KVM config
            kvm_config_path = os.path.join(build_dir, "kvm.conf")
            results['kvm_config'] = self.builder.create_kvm_config(kvm_config_path)
            
            print("🎉 All SNP components built successfully!")
            return results
            
        except Exception as e:
            print(f"❌ SNP build failed: {e}")
            raise
    
    def create_release_package(self, build_dir: str = ".", install_dir: str = None) -> str:
        """
        Create release package tarball.
        
        Args:
            build_dir: Build directory containing components
            install_dir: Installation directory
            
        Returns:
            Path to created tarball
        """
        if not install_dir:
            install_dir = os.path.join(build_dir, "usr", "local")
        
        print("📦 Creating SNP release package")
        
        # Create release directory structure
        release_date = datetime.now().strftime("%Y-%m-%d")
        output_dir = f"snp-release-{release_date}"
        output_path = os.path.join(build_dir, output_dir)
        
        if os.path.exists(output_path):
            shutil.rmtree(output_path)
        
        # Create directory structure
        ensure_directory(os.path.join(output_path, "linux", "guest"))
        ensure_directory(os.path.join(output_path, "linux", "host"))
        ensure_directory(os.path.join(output_path, "usr"))
        
        # Copy installation files
        if os.path.exists(install_dir):
            self.builder._safe_copytree(install_dir, os.path.join(output_path, "usr", "local"))
        
        # Copy source commit files
        for commit_file in Path(build_dir).glob("source-commit.*"):
            shutil.copy2(commit_file, output_path)
        
        # Copy stable-commits as source-config
        stable_commits_path = os.path.join(build_dir, "stable-commits")
        if os.path.exists(stable_commits_path):
            shutil.copy2(stable_commits_path, os.path.join(output_path, "source-config"))
        
        # Copy kernel packages
        if self.builder._is_debian_based():
            # Copy .deb packages
            for deb_file in Path(build_dir).glob("linux/linux-*-guest-*.deb"):
                shutil.copy2(deb_file, os.path.join(output_path, "linux", "guest"))
            for deb_file in Path(build_dir).glob("linux/linux-*-host-*.deb"):
                shutil.copy2(deb_file, os.path.join(output_path, "linux", "host"))
        else:
            # Copy .rpm packages
            for rpm_file in Path(build_dir).glob("linux/kernel-*.rpm"):
                shutil.copy2(rpm_file, os.path.join(output_path, "linux"))
        
        # Copy additional files if they exist
        # Copy install.sh from scripts directory
        scripts_install_sh = "scripts/install.sh"
        if os.path.exists(scripts_install_sh):
            copied_install_sh = os.path.join(output_path, "install.sh")
            shutil.copy2(scripts_install_sh, output_path)
            # Make install.sh executable
            os.chmod(copied_install_sh, 0o755)
        
        # Copy kvm.conf from build directory if it exists
        kvm_conf_path = os.path.join(build_dir, "kvm.conf")
        if os.path.exists(kvm_conf_path):
            shutil.copy2(kvm_conf_path, output_path)
        
        # Create tarball
        tarball_path = f"{output_path}.tar.gz"
        run_command(f"tar zcf {tarball_path} -C {build_dir} {output_dir}")
        
        print(f"✅ Release package created: {tarball_path}")
        return tarball_path

