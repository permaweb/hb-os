#!/usr/bin/env python3
"""
Guest setup functionality for dm-verity preparation.

Refactored from global state to class-based approach with proper resource management.
This module handles NBD device mounting, file copying, and dm-verity hash tree computation.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from src.utils import run_command, run_command_silent, CommandBuilder, HyperBeamError


class GuestSetupError(HyperBeamError):
    """Custom exception for guest setup operations."""
    
    def __init__(self, message: str, operation: str = None, cause: Exception = None):
        super().__init__(f"Guest setup failed: {message}", error_code=9, cause=cause)
        self.operation = operation


class GuestSetup:
    """
    Manages guest VM image setup for dm-verity with proper resource cleanup.
    
    This class encapsulates all the state and provides context management
    for safe resource handling (NBD devices, mount points, temp directories).
    """
    
    def __init__(self, src_image, build_dir, out_image, out_hash_tree, out_root_hash,
                 debug="0", non_interactive=False, device=None):
        """
        Initialize guest setup configuration.
        
        Args:
            src_image (str): Path to the source VM image
            build_dir (str): Build directory containing required content
            out_image (str): Output verity image path
            out_hash_tree (str): Output path for the device hash tree
            out_root_hash (str): Output path for the root hash
            debug (str): Debug mode flag ("0" for normal, other for debug)
            non_interactive (bool): If True, don't prompt for user confirmation
            device (str, optional): NBD device to use
        """
        # Core configuration
        self.src_image = src_image
        self.build_dir = build_dir
        self.dst_image = out_image
        self.hash_tree = out_hash_tree
        self.root_hash = out_root_hash
        self.debug = debug
        self.non_interactive = non_interactive
        self.fs_device = device
        
        # Device and folder configuration
        self.src_device = "/dev/nbd0"
        self.dst_device = "/dev/nbd1"
        self.src_folder = None  # Will be created in __enter__
        self.dst_folder = None  # Will be created in __enter__
        
        # Dynamic state
        self.src_root_fs_device = ""
        self.initial_lvm_devices = 0
        self.resources_initialized = False
    
    def __enter__(self):
        """Context manager entry - set up resources."""
        try:
            self.src_folder = tempfile.mkdtemp(prefix="src_folder_")
            self.dst_folder = tempfile.mkdtemp(prefix="dst_folder_")
            self.resources_initialized = True
            return self
        except Exception as e:
            self._cleanup()
            raise GuestSetupError(f"Failed to initialize resources: {e}")
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - clean up all resources."""
        self._cleanup()
        
    def _cleanup(self):
        """Comprehensive cleanup of all resources."""
        if not self.resources_initialized:
            return
            
        print("Cleaning up guest setup resources...")
        
        # Unmount and remove folders
        if self.src_folder and os.path.exists(self.src_folder):
            print(f"Unmounting {self.src_folder}")
            run_command_silent(["sudo", "umount", "-q", self.src_folder])
            shutil.rmtree(self.src_folder, ignore_errors=True)
        
        if self.dst_folder and os.path.exists(self.dst_folder):
            print(f"Unmounting {self.dst_folder}")
            run_command_silent(["sudo", "umount", "-q", self.dst_folder])
            shutil.rmtree(self.dst_folder, ignore_errors=True)
        
        # Close mapper device
        if os.path.exists("/dev/mapper/snpguard_root"):
            print("Closing mapper device")
            run_command_silent(["sudo", "cryptsetup", "luksClose", "snpguard_root"])
        
        # Unmount any LVM devices we discovered
        self._unmount_lvm_device()
        
        # Disconnect NBD devices
        need_sleep = False
        if os.path.exists(self.src_device):
            print(f"Disconnecting {self.src_device}")
            run_command_silent(["sudo", "qemu-nbd", "--disconnect", self.src_device])
            need_sleep = True
        
        if os.path.exists(self.dst_device):
            print(f"Disconnecting {self.dst_device}")
            run_command_silent(["sudo", "qemu-nbd", "--disconnect", self.dst_device])
            need_sleep = True
        
        if need_sleep:
            time.sleep(2)
        
        # Remove NBD module
        run_command_silent(["sudo", "modprobe", "-r", "nbd"])

    # ===================== LVM Management Methods =====================
    
    def _check_lvm(self):
        """Store the number of LVM devices and warn if any are present on the host."""
        try:
            result = subprocess.run(["sudo", "lvdisplay"],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    universal_newlines=True,
                                    check=True)
        except subprocess.CalledProcessError:
            result = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        
        # Count the number of lines that contain "LV Path"
        self.initial_lvm_devices = result.stdout.count("LV Path")
        if self.initial_lvm_devices > 0:
            print("Warning: a LVM filesystem is currently in use on your system.")
            print("If your guest VM image uses LVM as well, this script might not work as intended.")
            time.sleep(2)
    
    def _get_lvm_device(self):
        """If the VM image uses LVM, set src_root_fs_device accordingly."""
        # Run lvdisplay and check for warnings
        proc = subprocess.run(["sudo", "lvdisplay"],
                              stdout=subprocess.DEVNULL,
                              stderr=subprocess.PIPE,
                              universal_newlines=True)
        if "WARNING" in proc.stderr:
            raise GuestSetupError(
                "Guest VM LVM filesystem could not be mounted. "
                "Cannot continue. Try creating a new VM using our guide.\n"
                f"Log from lvdisplay: {proc.stderr}"
            )
        
        # Get current LVM device count and if increased, take the last one
        proc2 = subprocess.run(["sudo", "lvdisplay"],
                               stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL,
                               universal_newlines=True)
        count = proc2.stdout.count("LV Path")
        if count > self.initial_lvm_devices:
            lines = proc2.stdout.splitlines()
            lv_lines = [line for line in lines if "LV Path" in line]
            if lv_lines:
                # The original awk uses the third token
                tokens = lv_lines[-1].split()
                if len(tokens) >= 3:
                    self.src_root_fs_device = tokens[2]
                    print("Found LVM2 filesystem: " + self.src_root_fs_device)
    
    def _unmount_lvm_device(self):
        """Unmount any new LVM devices that were discovered after mounting the image."""
        proc = subprocess.run(["sudo", "lvdisplay"],
                              stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL,
                              universal_newlines=True)
        count = proc.stdout.count("LV Path")
        if count > self.initial_lvm_devices:
            print("Unmounting LVM device")
            lines = proc.stdout.splitlines()
            lv_lines = [line for line in lines if "LV Path" in line]
            if lv_lines:
                tokens = lv_lines[-1].split()
                if len(tokens) >= 3:
                    lvm_path = tokens[2]
                else:
                    lvm_path = ""
            vg_lines = [line for line in lines if "VG Name" in line]
            if vg_lines:
                vg_tokens = vg_lines[-1].split()
                if len(vg_tokens) >= 3:
                    vg_name = vg_tokens[2]
                else:
                    vg_name = ""
            if lvm_path and vg_name:
                subprocess.run(["sudo", "lvchange", "-an", lvm_path], check=False)
                subprocess.run(["sudo", "vgchange", "-an", vg_name], check=False)

    # ===================== Image and Device Management Methods =====================
    
    def _initialize_nbd(self):
        """Initialize the NBD module and connect both source and destination images."""
        self._check_lvm()
        run_command(["sudo", "modprobe", "nbd", "max_part=8"], shell=False)
        run_command(["sudo", "qemu-nbd", "--connect=" + self.src_device, self.src_image], shell=False)
        run_command(["sudo", "qemu-nbd", "--connect=" + self.dst_device, self.dst_image], shell=False)
    
    def _create_output_image(self):
        """Create a new output image based on the virtual size of the source image."""
        try:
            info = subprocess.check_output(["qemu-img", "info", self.src_image],
                                           universal_newlines=True)
        except subprocess.CalledProcessError:
            raise GuestSetupError("Error getting qemu-img info for source image")
        
        size = None
        for line in info.splitlines():
            if "virtual size:" in line:
                # Expecting something like: virtual size: 10G (10737418240 bytes)
                # The original awk command prints the third token and appends "G"
                tokens = line.split()
                if len(tokens) >= 3:
                    size = tokens[2] + "G"
                break
        
        if size is None:
            raise GuestSetupError("Could not determine image size from qemu-img info")
        
        run_command(["qemu-img", "create", "-f", "qcow2", self.dst_image, size], shell=False)
    
    def _copy_filesystem(self):
        """Copy the contents of the source folder to the destination folder using rsync."""
        try:
            subprocess.run([
                "sudo", "rsync", "-axHAWXS", "--numeric-ids", "--info=progress2",
                self.src_folder + "/", self.dst_folder + "/"
            ], check=True)
        except subprocess.CalledProcessError as e:
            raise GuestSetupError(f"Failed to copy filesystem: {e}")
    
    def _find_root_fs_device(self):
        """Determine the device containing the root filesystem from the source image."""
        self._get_lvm_device()
        
        if self.src_root_fs_device:
            return
        
        # Use fdisk to list partitions and extract the first Linux filesystem device
        try:
            fdisk_output = subprocess.check_output(
                ["sudo", "fdisk", self.src_device, "-l"],
                universal_newlines=True)
        except subprocess.CalledProcessError:
            raise GuestSetupError("Error running fdisk on source device")
        
        # Use regex search (case-insensitive) for a line with "Linux filesystem"
        match = re.search(r"(/dev/\S+).*Linux filesystem", fdisk_output, re.IGNORECASE)
        if match:
            self.src_root_fs_device = match.group(1)
        else:
            self.src_root_fs_device = ""
        
        if self.non_interactive:
            return
        
        # Show fdisk output to user for confirmation
        print(fdisk_output)
        root_fs_found = ""
        if self.src_root_fs_device and os.path.exists(self.src_root_fs_device):
            print(f"Found the following filesystem: {self.src_root_fs_device}")
            root_fs_found = "1"
            # Interactive confirmation disabled - could be added back if needed
        else:
            print(f"Failed to identify root filesystem {self.src_root_fs_device}.")
            root_fs_found = "0"
        
        if root_fs_found == "0":
            device_input = input("Enter device containing the root filesystem: ").strip()
            if not os.path.exists(device_input):
                raise GuestSetupError("Could not find specified root filesystem device")
            self.src_root_fs_device = device_input

    # ===================== Filesystem Preparation Methods =====================
    
    def _prepare_verity_fs(self):
        """Prepare the destination filesystem for dm-verity."""
        # Remove SSH keys (they will be regenerated later)
        ssh_path = os.path.join(self.dst_folder, "etc", "ssh", "ssh_host_*")
        subprocess.run("sudo rm -rf " + ssh_path, shell=True)
        
        if self.debug == "0":
            self._configure_secure_mode()
        else:
            self._configure_debug_mode()
        
        # Common filesystem preparations
        self._finalize_filesystem_structure()
    
    def _configure_secure_mode(self):
        """Configure filesystem for secure (black box) mode."""
        print("Configuring secure mode - disabling access interfaces...")
        
        # Disable SSH service
        print("Disabling SSH service...")
        subprocess.run(["sudo", "chroot", self.dst_folder, "systemctl", "disable", "ssh.service"], check=True)
        subprocess.run(["sudo", "chroot", self.dst_folder, "systemctl", "mask", "ssh.service"], check=True)
        
        # Disable login for all users except root by editing /etc/passwd
        passwd_file = os.path.join(self.dst_folder, "etc", "passwd")
        sed_cmd = ("sudo sed -i '/^[^:]*:[^:]*:[^:]*:[^:]*:[^:]*:[^:]*:\\/bin\\/bash$/ s/\\/bin\\/bash/\\/usr\\/sbin\\/nologin/' " + passwd_file)
        subprocess.run(sed_cmd, shell=True, check=True)
        
        # Disable all TTY services (tty1 through tty6)
        print("Disabling all TTY services...")
        for i in range(1, 7):
            subprocess.run(["sudo", "chroot", self.dst_folder, "systemctl", "disable", f"getty@tty{i}.service"], check=True)
            subprocess.run(["sudo", "chroot", self.dst_folder, "systemctl", "mask", f"getty@tty{i}.service"], check=True)
        
        # Disable serial console (ttyS0)
        print("Disabling serial console (ttyS0)...")
        subprocess.run(["sudo", "chroot", self.dst_folder, "systemctl", "disable", "serial-getty@ttyS0.service"], check=True)
        subprocess.run(["sudo", "chroot", self.dst_folder, "systemctl", "mask", "serial-getty@ttyS0.service"], check=True)
        
        # Remove TTY kernel console configuration from GRUB if the file exists
        grub_path = os.path.join(self.dst_folder, "etc", "default", "grub")
        if os.path.isfile(grub_path):
            print("Removing TTY kernel console configuration from GRUB...")
            subprocess.run("sudo sed -i 's/console=.*//g' " + grub_path, shell=True, check=True)
            subprocess.run("sudo sed -i 's/^GRUB_CMDLINE_LINUX_DEFAULT=\"\\(.*\\)\"/GRUB_CMDLINE_LINUX_DEFAULT=\"\\1 console=none\"/' " + grub_path,
                           shell=True, check=True)
        
        # Ensure no TTY devices are active at runtime
        print("Disabling TTY devices...")
        for dev in ["tty", "tty0", "tty1", "tty2", "tty3", "tty4", "tty5", "tty6", "ttyS0"]:
            dev_path = os.path.join(self.dst_folder, "dev", dev)
            if os.path.exists(dev_path):
                new_path = os.path.join(self.dst_folder, "dev", f"{dev}_disabled")
                subprocess.run(["sudo", "mv", dev_path, new_path], check=False)
        
        # Disable kernel messages to console (dmesg --console-off might fail; ignore error)
        print("Disabling kernel messages to console...")
        subprocess.run(["sudo", "chroot", self.dst_folder, "dmesg", "--console-off"], check=False)
        print("Black box preparation complete. No TTY or console interfaces are accessible.")
    
    def _configure_debug_mode(self):
        """Configure filesystem for debug mode with root access."""
        print("Debug mode enabled. Configuring root user...")
        
        # Set root password in the chroot environment
        print("Setting root password...")
        subprocess.run(["sudo", "chroot", self.dst_folder, "sh", "-c", "echo 'root:hb' | chpasswd"], check=True)
        
        # Update sshd_config to allow root login and password authentication
        sshd_config_path = os.path.join(self.dst_folder, "etc", "ssh", "sshd_config")
        print("Updating SSH configuration...")
        subprocess.run([
            "sudo", "sed", "-i", "-E",
            "-e", "s/^\\s*#?\\s*PermitRootLogin\\s+.*/PermitRootLogin yes/",
            "-e", "s/^\\s*#?\\s*PasswordAuthentication\\s+.*/PasswordAuthentication yes/",
            sshd_config_path
        ], check=True)
        
        # Enable and start SSH service in the chroot environment
        print("Enabling SSH service...")
        subprocess.run(["sudo", "chroot", self.dst_folder, "systemctl", "enable", "ssh.service"], check=True)
        
        print("Debug mode configuration complete.")
    
    def _finalize_filesystem_structure(self):
        """Finalize the filesystem structure for dm-verity."""
        # Remove any data in tmp folder
        subprocess.run(["sudo", "rm", "-rf", os.path.join(self.dst_folder, "tmp")], check=True)
        
        # Rename directories: root, etc, and var
        subprocess.run(["sudo", "mv", os.path.join(self.dst_folder, "root"), os.path.join(self.dst_folder, "root_ro")], check=True)
        subprocess.run(["sudo", "mv", os.path.join(self.dst_folder, "etc"), os.path.join(self.dst_folder, "etc_ro")], check=True)
        subprocess.run(["sudo", "mv", os.path.join(self.dst_folder, "var"), os.path.join(self.dst_folder, "var_ro")], check=True)
        
        # Create new directories (home, etc, var, tmp)
        subprocess.run(["sudo", "mkdir", "-p",
                        os.path.join(self.dst_folder, "home"),
                        os.path.join(self.dst_folder, "etc"),
                        os.path.join(self.dst_folder, "var"),
                        os.path.join(self.dst_folder, "tmp")],
                       check=True)
        
        # Copy the contents of the old root folder to the new root directory
        subprocess.run(["sudo", "cp", "-r",
                        os.path.join(self.dst_folder, "root_ro"),
                        os.path.join(self.dst_folder, "root")],
                       check=True)

    # ===================== Public Interface =====================
    
    def setup(self):
        """
        Execute the complete guest image setup process for dm-verity.
        
        This is the main public method that orchestrates the entire process:
        1. Create output image
        2. Initialize NBD devices
        3. Find root filesystem
        4. Mount and copy files
        5. Copy HyperBEAM components
        6. Prepare filesystem for dm-verity
        7. Compute hash tree
        
        Returns:
            str: The root hash value
            
        Raises:
            GuestSetupError: If any step of the setup process fails
        """
        try:
            print("Creating output image...")
            self._create_output_image()
            
            print("Initializing NBD module...")
            self._initialize_nbd()
            
            print("Finding root filesystem...")
            self._find_root_fs_device()
            print(f"Rootfs device selected: {self.src_root_fs_device}")
            
            print("Creating ext4 partition on output image...")
            subprocess.run(["sudo", "mkfs.ext4", self.dst_device], check=True)
            
            print("Mounting images...")
            subprocess.run(["sudo", "mount", self.src_root_fs_device, self.src_folder], check=True)
            subprocess.run(["sudo", "mount", self.dst_device, self.dst_folder], check=True)
            
            print("Copying files (this may take some time)...")
            self._copy_filesystem()
            
            print("Copying HyperBEAM...")
            self._copy_hyperbeam_components()
            
            print("Preparing output filesystem for dm-verity...")
            self._prepare_verity_fs()
            
            print("Unmounting images...")
            subprocess.run(["sudo", "umount", "-q", self.src_folder], check=True)
            subprocess.run(["sudo", "umount", "-q", self.dst_folder], check=True)
            
            print("Computing hash tree...")
            root_hash_value = self._compute_hash_tree()
            
            print("Root hash: " + root_hash_value)
            print("Guest setup complete!")
            
            return root_hash_value
            
        except subprocess.CalledProcessError as e:
            raise GuestSetupError(f"Command failed during setup: {e}")
        except Exception as e:
            raise GuestSetupError(f"Setup failed: {e}")
    
    def _copy_hyperbeam_components(self):
        """Copy HyperBEAM components to the destination filesystem."""
        hb_src = os.path.join(self.build_dir, "content", "hb")
        hb_dst = os.path.join(self.dst_folder, "root")
        subprocess.run(["sudo", "rsync", "-axHAWXS", "--numeric-ids", "--info=progress2",
                        hb_src, hb_dst], check=True)
        
        if self.debug == "0":
            print("Copying HyperBEAM service...")
            hb_service_src = os.path.join(self.build_dir, "content", "hyperbeam.service")
            hb_service_dst = os.path.join(self.dst_folder, "etc", "systemd", "system", "hyperbeam.service")
            subprocess.run(["sudo", "rsync", "-axHAWXS", "--numeric-ids", "--info=progress2",
                            hb_service_src, hb_service_dst], check=True)
            
            print("Enabling HyperBEAM service...")
            subprocess.run(["sudo", "chroot", self.dst_folder, "systemctl", "enable", "hyperbeam.service"], check=True)
        else:
            print("Debug mode enabled. Skipping HyperBEAM service copy.")
    
    def _compute_hash_tree(self):
        """Compute the dm-verity hash tree and return the root hash."""
        cmd = (CommandBuilder("sudo", "veritysetup", "format", self.dst_device, self.hash_tree)
               .pipe("grep", "Root")
               .pipe("cut", "-f2")
               .build())
        
        try:
            root_hash_value = subprocess.check_output(cmd, shell=True, universal_newlines=True)
        except subprocess.CalledProcessError as e:
            raise GuestSetupError(f"Error computing hash tree: {e}")
        
        # Remove extra whitespace and any trailing '%' characters
        root_hash_value = root_hash_value.strip().rstrip('%')
        
        with open(self.root_hash, "w") as f:
            f.write(root_hash_value)
        
        return root_hash_value


# ===================== Backward Compatibility Function =====================

def setup_guest(src_image, build_dir, out_image, out_hash_tree, out_root_hash,
                debug, non_interactive=False, device=None):
    """
    Set up a guest image for dm-verity (backward compatibility function).
    
    Args:
        src_image (str): Path to the source VM image
        build_dir (str): Build directory containing required content  
        out_image (str): Output verity image path
        out_hash_tree (str): Output path for the device hash tree
        out_root_hash (str): Output path for the root hash
        debug (str): Debug mode flag ("0" means normal mode)
        non_interactive (bool): If True, don't prompt for confirmation
        device (str, optional): NBD device to use
        
    Returns:
        str: The root hash value
        
    Raises:
        GuestSetupError: If setup fails
    """
    with GuestSetup(src_image, build_dir, out_image, out_hash_tree, out_root_hash,
                    debug, non_interactive, device) as guest_setup:
        return guest_setup.setup()
