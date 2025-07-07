#!/usr/bin/env python3
"""
setup_verity.py

This script reproduces the functionality of the two Bash scripts (setup_verity.sh and common.sh).
It connects to NBD devices, mounts images, copies files via rsync, prepares the filesystem for dm-verity,
and computes the verity hash tree.
"""

import atexit
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

# Global variables (matching the Bash script defaults)
SRC_DEVICE = "/dev/nbd0"
DST_DEVICE = "/dev/nbd1"
SRC_FOLDER = tempfile.mkdtemp(prefix="src_folder_")
DST_FOLDER = tempfile.mkdtemp(prefix="dst_folder_")
SRC_IMAGE = ""
DST_IMAGE = ""
HASH_TREE = ""
ROOT_HASH = ""
NON_INTERACTIVE = False
BUILD_DIR = ""
DEBUG = "0"            # Use "0" for normal mode, nonzero for debug mode.
FS_DEVICE = None       # Not used in this script but available per original usage.
SRC_ROOT_FS_DEVICE = ""  # To be determined later.
__LVM_DEVICES = 0      # Number of LVM devices that existed before mounting the image

# ----------------- Common Functions (from common.sh) ----------------- #

def clean_up():
    """Cleanup function that is called upon script exit."""
    print("Cleaning up")
    # Unmount and remove SRC_FOLDER if it exists
    if SRC_FOLDER and os.path.exists(SRC_FOLDER):
        print(f"Unmounting {SRC_FOLDER}")
        subprocess.run(["sudo", "umount", "-q", SRC_FOLDER], stderr=subprocess.DEVNULL)
        shutil.rmtree(SRC_FOLDER, ignore_errors=True)

    # Unmount and remove DST_FOLDER if it exists
    if DST_FOLDER and os.path.exists(DST_FOLDER):
        print(f"Unmounting {DST_FOLDER}")
        subprocess.run(["sudo", "umount", "-q", DST_FOLDER], stderr=subprocess.DEVNULL)
        shutil.rmtree(DST_FOLDER, ignore_errors=True)

    # Close mapper device if it exists
    if os.path.exists("/dev/mapper/snpguard_root"):
        print("Closing mapper device")
        subprocess.run(["sudo", "cryptsetup", "luksClose", "snpguard_root"],
                       stderr=subprocess.DEVNULL)

    unmount_lvm_device()

    need_sleep = False
    if os.path.exists(SRC_DEVICE):
        print(f"Disconnecting {SRC_DEVICE}")
        subprocess.run(["sudo", "qemu-nbd", "--disconnect", SRC_DEVICE],
                       stderr=subprocess.DEVNULL)
        need_sleep = True

    if os.path.exists(DST_DEVICE):
        print(f"Disconnecting {DST_DEVICE}")
        subprocess.run(["sudo", "qemu-nbd", "--disconnect", DST_DEVICE],
                       stderr=subprocess.DEVNULL)
        need_sleep = True

    if need_sleep:
        time.sleep(2)

    subprocess.run(["sudo", "modprobe", "-r", "nbd"], stderr=subprocess.DEVNULL)

def check_lvm():
    """Store the number of LVM devices and warn if any are present on the host."""
    global __LVM_DEVICES
    try:
        result = subprocess.run(["sudo", "lvdisplay"],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                universal_newlines=True,
                                check=True)
    except subprocess.CalledProcessError:
        result = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
    # Count the number of lines that contain "LV Path"
    __LVM_DEVICES = result.stdout.count("LV Path")
    if __LVM_DEVICES > 0:
        print("Warning: a LVM filesystem is currently in use on your system.")
        print("If your guest VM image uses LVM as well, this script might not work as intended.")
        time.sleep(2)

def get_lvm_device():
    """If the VM image uses LVM, set SRC_ROOT_FS_DEVICE accordingly."""
    global SRC_ROOT_FS_DEVICE, __LVM_DEVICES
    # Run lvdisplay and check for warnings
    proc = subprocess.run(["sudo", "lvdisplay"],
                          stdout=subprocess.DEVNULL,
                          stderr=subprocess.PIPE,
                          universal_newlines=True)
    if "WARNING" in proc.stderr:
        print("Error: seems like the guest VM had a LVM filesystem that could not be mounted")
        print("Cannot continue. Try creating a new VM using our guide.")
        print("Log from lvdisplay:")
        print(proc.stderr)
        sys.exit(1)

    # Get current LVM device count and if increased, take the last one
    proc2 = subprocess.run(["sudo", "lvdisplay"],
                           stdout=subprocess.PIPE,
                           stderr=subprocess.DEVNULL,
                           universal_newlines=True)
    count = proc2.stdout.count("LV Path")
    if count > __LVM_DEVICES:
        lines = proc2.stdout.splitlines()
        lv_lines = [line for line in lines if "LV Path" in line]
        if lv_lines:
            # The original awk uses the third token
            tokens = lv_lines[-1].split()
            if len(tokens) >= 3:
                SRC_ROOT_FS_DEVICE = tokens[2]
                print("Found LVM2 filesystem: " + SRC_ROOT_FS_DEVICE)

def unmount_lvm_device():
    """Unmount any new LVM devices that were discovered after mounting the image."""
    proc = subprocess.run(["sudo", "lvdisplay"],
                          stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL,
                          universal_newlines=True)
    count = proc.stdout.count("LV Path")
    if count > __LVM_DEVICES:
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

def initialize_nbd():
    """Initialize the NBD module and connect both source and destination images."""
    check_lvm()
    subprocess.run(["sudo", "modprobe", "nbd", "max_part=8"], check=True)
    subprocess.run(["sudo", "qemu-nbd", "--connect=" + SRC_DEVICE, SRC_IMAGE], check=True)
    subprocess.run(["sudo", "qemu-nbd", "--connect=" + DST_DEVICE, DST_IMAGE], check=True)

def create_output_image():
    """Create a new output image based on the virtual size of the source image."""
    # Get the size using qemu-img info and use awk-like processing.
    try:
        info = subprocess.check_output(["qemu-img", "info", SRC_IMAGE],
                                       universal_newlines=True)
    except subprocess.CalledProcessError as e:
        print("Error getting qemu-img info")
        sys.exit(1)
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
        print("Could not determine image size.")
        sys.exit(1)
    subprocess.run(["qemu-img", "create", "-f", "qcow2", DST_IMAGE, size], check=True)

def copy_filesystem():
    """Copy the contents of the source folder to the destination folder using rsync."""
    subprocess.run([
        "sudo", "rsync", "-axHAWXS", "--numeric-ids", "--info=progress2",
        SRC_FOLDER + "/", DST_FOLDER + "/"
    ], check=True)

def find_root_fs_device():
    """Determine the device containing the root filesystem from the source image."""
    global SRC_ROOT_FS_DEVICE
    get_lvm_device()

    if SRC_ROOT_FS_DEVICE:
        return

    # Use fdisk to list partitions and extract the first Linux filesystem device.
    try:
        fdisk_output = subprocess.check_output(
            ["sudo", "fdisk", SRC_DEVICE, "-l"],
            universal_newlines=True)
    except subprocess.CalledProcessError:
        print("Error running fdisk")
        sys.exit(1)

    # Use regex search (case-insensitive) for a line with "Linux filesystem"
    match = re.search(r"(/dev/\S+).*Linux filesystem", fdisk_output, re.IGNORECASE)
    if match:
        SRC_ROOT_FS_DEVICE = match.group(1)
    else:
        SRC_ROOT_FS_DEVICE = ""

    if NON_INTERACTIVE:
        return

    # Show fdisk output to user for confirmation
    print(fdisk_output)
    root_fs_found = ""
    if SRC_ROOT_FS_DEVICE and os.path.exists(SRC_ROOT_FS_DEVICE):
        print(f"Found the following filesystem: {SRC_ROOT_FS_DEVICE}")
        root_fs_found = "1"
        # while root_fs_found == "":
        #     choice = input("Do you confirm that this is correct? (y/n): ").strip().lower()
        #     if choice == "y":
        #         root_fs_found = "1"
        #     elif choice == "n":
        #         root_fs_found = "0"
        #     else:
        #         print("Invalid choice. Please enter 'y' or 'n'.")
    else:
        print(f"Failed to identify root filesystem {SRC_ROOT_FS_DEVICE}.")
        root_fs_found = "0"

    if root_fs_found == "0":
        SRC_ROOT_FS_DEVICE = input("Enter device containing the root filesystem: ").strip()
        if not os.path.exists(SRC_ROOT_FS_DEVICE):
            print("Could not find root filesystem.")
            sys.exit(1)

# ----------------- Script-specific Function (from setup_verity.sh) ----------------- #

def prepare_verity_fs():
    """Prepare the destination filesystem for dm-verity."""
    # Remove SSH keys (they will be regenerated later)
    ssh_path = os.path.join(DST_FOLDER, "etc", "ssh", "ssh_host_*")
    subprocess.run("sudo rm -rf " + ssh_path, shell=True)

    if DEBUG == "0":
        # Disable SSH service
        print("Disabling SSH service...")
        subprocess.run(["sudo", "chroot", DST_FOLDER, "systemctl", "disable", "ssh.service"], check=True)
        subprocess.run(["sudo", "chroot", DST_FOLDER, "systemctl", "mask", "ssh.service"], check=True)

        # Disable login for all users except root by editing /etc/passwd
        passwd_file = os.path.join(DST_FOLDER, "etc", "passwd")
        sed_cmd = ("sudo sed -i '/^[^:]*:[^:]*:[^:]*:[^:]*:[^:]*:[^:]*:\\/bin\\/bash$/ s/\\/bin\\/bash/\\/usr\\/sbin\\/nologin/' " + passwd_file)
        subprocess.run(sed_cmd, shell=True, check=True)

        # Disable all TTY services (tty1 through tty6)
        print("Disabling all TTY services...")
        for i in range(1, 7):
            subprocess.run(["sudo", "chroot", DST_FOLDER, "systemctl", "disable", f"getty@tty{i}.service"], check=True)
            subprocess.run(["sudo", "chroot", DST_FOLDER, "systemctl", "mask", f"getty@tty{i}.service"], check=True)

        # Disable serial console (ttyS0)
        print("Disabling serial console (ttyS0)...")
        subprocess.run(["sudo", "chroot", DST_FOLDER, "systemctl", "disable", "serial-getty@ttyS0.service"], check=True)
        subprocess.run(["sudo", "chroot", DST_FOLDER, "systemctl", "mask", "serial-getty@ttyS0.service"], check=True)

        # Remove TTY kernel console configuration from GRUB if the file exists
        grub_path = os.path.join(DST_FOLDER, "etc", "default", "grub")
        if os.path.isfile(grub_path):
            print("Removing TTY kernel console configuration from GRUB...")
            subprocess.run("sudo sed -i 's/console=.*//g' " + grub_path, shell=True, check=True)
            subprocess.run("sudo sed -i 's/^GRUB_CMDLINE_LINUX_DEFAULT=\"\\(.*\\)\"/GRUB_CMDLINE_LINUX_DEFAULT=\"\\1 console=none\"/' " + grub_path,
                           shell=True, check=True)

        # Ensure no TTY devices are active at runtime
        print("Disabling TTY devices...")
        for dev in ["tty", "tty0", "tty1", "tty2", "tty3", "tty4", "tty5", "tty6", "ttyS0"]:
            dev_path = os.path.join(DST_FOLDER, "dev", dev)
            if os.path.exists(dev_path):
                new_path = os.path.join(DST_FOLDER, "dev", f"{dev}_disabled")
                subprocess.run(["sudo", "mv", dev_path, new_path], check=False)

        # Disable kernel messages to console (dmesg --console-off might fail; ignore error)
        print("Disabling kernel messages to console...")
        subprocess.run(["sudo", "chroot", DST_FOLDER, "dmesg", "--console-off"], check=False)
        print("Black box preparation complete. No TTY or console interfaces are accessible.")
    else:
        print("Debug mode enabled. Configuring root user...")
        
        # Set root password in the chroot environment
        print("Setting root password...")
        subprocess.run(["sudo", "chroot", DST_FOLDER, "sh", "-c", "echo 'root:hb' | chpasswd"], check=True)
        
        # Update sshd_config to allow root login and password authentication
        sshd_config_path = os.path.join(DST_FOLDER, "etc", "ssh", "sshd_config")
        print("Updating SSH configuration...")
        subprocess.run([
            "sudo", "sed", "-i", "-E",
            "-e", "s/^\\s*#?\\s*PermitRootLogin\\s+.*/PermitRootLogin yes/",
            "-e", "s/^\\s*#?\\s*PasswordAuthentication\\s+.*/PasswordAuthentication yes/",
            sshd_config_path
        ], check=True)
        
        # Enable and start SSH service in the chroot environment
        print("Enabling SSH service...")
        subprocess.run(["sudo", "chroot", DST_FOLDER, "systemctl", "enable", "ssh.service"], check=True)
        
        print("Debug mode configuration complete.")

    # Remove any data in tmp folder
    subprocess.run(["sudo", "rm", "-rf", os.path.join(DST_FOLDER, "tmp")], check=True)

    # Rename directories: root, etc, and var
    subprocess.run(["sudo", "mv", os.path.join(DST_FOLDER, "root"), os.path.join(DST_FOLDER, "root_ro")], check=True)
    subprocess.run(["sudo", "mv", os.path.join(DST_FOLDER, "etc"), os.path.join(DST_FOLDER, "etc_ro")], check=True)
    subprocess.run(["sudo", "mv", os.path.join(DST_FOLDER, "var"), os.path.join(DST_FOLDER, "var_ro")], check=True)

    # Create new directories (home, etc, var, tmp)
    subprocess.run(["sudo", "mkdir", "-p",
                    os.path.join(DST_FOLDER, "home"),
                    os.path.join(DST_FOLDER, "etc"),
                    os.path.join(DST_FOLDER, "var"),
                    os.path.join(DST_FOLDER, "tmp")],
                   check=True)

    # Copy the contents of the old root folder to the new root directory
    subprocess.run(["sudo", "cp", "-r",
                    os.path.join(DST_FOLDER, "root_ro"),
                    os.path.join(DST_FOLDER, "root")],
                   check=True)

# ----------------- Main Script ----------------- #

def setup_guest(src_image, build_dir, out_image,
                out_hash_tree, out_root_hash,
                debug, non_interactive=False, device=None):
    """
    Set up a guest image for dm-verity.
    
    Parameters:
      src_image     - Path to the source VM image.
      build_dir     - Build directory containing required content.
      out_image     - Output verity image path (default: "image.qcow2").
      out_hash_tree - Output path for the device hash tree (default: "hash_tree.bin").
      out_root_hash - Output path for the root hash (default: "roothash.txt").
      debug         - Debug mode flag as a string ("0" means normal mode).
      non_interactive - Boolean flag; if True, do not prompt for confirmation.
      device        - Optional NBD device to use.
    """
    global SRC_IMAGE, DST_IMAGE, HASH_TREE, ROOT_HASH, NON_INTERACTIVE, BUILD_DIR, DEBUG, FS_DEVICE
    NON_INTERACTIVE = non_interactive
    SRC_IMAGE = src_image
    if device:
        FS_DEVICE = device
    DST_IMAGE = out_image
    HASH_TREE = out_hash_tree
    ROOT_HASH = out_root_hash
    BUILD_DIR = build_dir
    DEBUG = debug

    # Register the cleanup handler.
    atexit.register(clean_up)

    print("Creating output image..")
    create_output_image()

    print("Initializing NBD module..")
    initialize_nbd()

    print("Finding root filesystem..")
    find_root_fs_device()
    print(f"Rootfs device selected: {SRC_ROOT_FS_DEVICE}")

    print("Creating ext4 partition on output image..")
    subprocess.run(["sudo", "mkfs.ext4", DST_DEVICE], check=True)

    print("Mounting images..")
    subprocess.run(["sudo", "mount", SRC_ROOT_FS_DEVICE, SRC_FOLDER], check=True)
    subprocess.run(["sudo", "mount", DST_DEVICE, DST_FOLDER], check=True)

    print("Copying files (this may take some time)..")
    copy_filesystem()

    print("Copying HyperBEAM..")
    hb_src = os.path.join(BUILD_DIR, "content", "hb")
    hb_dst = os.path.join(DST_FOLDER, "root")
    subprocess.run(["sudo", "rsync", "-axHAWXS", "--numeric-ids", "--info=progress2",
                    hb_src, hb_dst], check=True)

    if DEBUG == "0":
        print("Copying HyperBEAM service..")
        hb_service_src = os.path.join(BUILD_DIR, "content", "hyperbeam.service")
        hb_service_dst = os.path.join(DST_FOLDER, "etc", "systemd", "system", "hyperbeam.service")
        subprocess.run(["sudo", "rsync", "-axHAWXS", "--numeric-ids", "--info=progress2",
                        hb_service_src, hb_service_dst], check=True)

        print("Copy HyperBEAM service..")
        hb_service_src = os.path.join(BUILD_DIR, "content", "hyperbeam.service")
        hb_service_dst = os.path.join(DST_FOLDER, "etc", "systemd", "system", "hyperbeam.service")
        subprocess.run(["sudo", "rsync", "-axHAWXS", "--numeric-ids", "--info=progress2",
                        hb_service_src, hb_service_dst], check=True)

        print("Enabling HyperBEAM service..")
        subprocess.run(["sudo", "chroot", DST_FOLDER, "systemctl", "enable", "hyperbeam.service"], check=True)
    else:
        print("Debug mode enabled. Skipping HyperBEAM service copy.")

    # print("Copying CU..")
    # cu_src = os.path.join(BUILD_DIR, "content", "cu")
    # cu_dst = os.path.join(DST_FOLDER, "root")
    # subprocess.run(["sudo", "rsync", "-axHAWXS", "--numeric-ids", "--info=progress2",
    #                 cu_src, cu_dst], check=True)

    # print("Copy CU service..")
    # cu_service_src = os.path.join(BUILD_DIR, "content", "cu.service")
    # cu_service_dst = os.path.join(DST_FOLDER, "etc", "systemd", "system", "cu.service")
    # subprocess.run(["sudo", "rsync", "-axHAWXS", "--numeric-ids", "--info=progress2",
    #                 cu_service_src, cu_service_dst], check=True)

    # print("Enabling CU service..")
    # subprocess.run(["sudo", "chroot", DST_FOLDER, "systemctl", "enable", "cu.service"], check=True)

    print("Preparing output filesystem for dm-verity..")
    prepare_verity_fs()

    print("Unmounting images..")
    subprocess.run(["sudo", "umount", "-q", SRC_FOLDER], check=True)
    subprocess.run(["sudo", "umount", "-q", DST_FOLDER], check=True)

    print("Computing hash tree..")
    cmd = "sudo veritysetup format {} {} | grep Root | cut -f2".format(DST_DEVICE, HASH_TREE)
    try:
        root_hash_value = subprocess.check_output(cmd, shell=True, universal_newlines=True)
    except subprocess.CalledProcessError:
        print("Error computing hash tree.")
        sys.exit(1)

    # Remove extra whitespace and any trailing '%' characters.
    root_hash_value = root_hash_value.strip().rstrip('%')
    with open(ROOT_HASH, "w") as f:
        f.write(root_hash_value)
    print("Root hash: " + root_hash_value)
    print("All done!")

