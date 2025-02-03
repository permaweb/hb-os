#!/usr/bin/env python3
"""
This module implements the dm-verity image creation workflow.
It is a Python conversion of the original verity.sh script.
All common helper functions are imported from common.py.
The primary functionality is exposed via the build_verity_image(config) function.
"""

import os
import sys
import subprocess
import tempfile
import shutil
import time
import atexit
import re

from src.common import (clean_up, copy_filesystem, create_output_image,
                    initialize_nbd, find_root_fs_device, ctx)

def prepare_verity_fs():
    """
    Prepares the destination filesystem for dm-verity by “hardening” it.
    This includes disabling SSH and TTY services, modifying GRUB, renaming directories,
    and re-creating new ones.
    """
    dst_folder = ctx["DST_FOLDER"]

    # Remove SSH host keys (they will be regenerated later)
    subprocess.run("sudo rm -rf {}/*.sh".format(os.path.join(dst_folder, "etc/ssh/ssh_host_*")),
                   shell=True)

    if ctx.get("DEBUG", "0") == "0":
        print("Disabling SSH service...")
        subprocess.run(["sudo", "chroot", dst_folder, "systemctl", "disable", "ssh.service"], check=True)
        subprocess.run(["sudo", "chroot", dst_folder, "systemctl", "mask", "ssh.service"], check=True)

        print("Disabling login for all users except root...")
        passwd_file = os.path.join(dst_folder, "etc/passwd")
        with open(passwd_file, "r") as f:
            lines = f.readlines()
        new_lines = []
        for line in lines:
            if re.search(r":/bin/bash\s*$", line):
                line = re.sub(r"/bin/bash\s*$", "/usr/sbin/nologin", line)
            new_lines.append(line)
        with open(passwd_file, "w") as f:
            f.writelines(new_lines)

        print("Disabling all TTY services...")
        for i in range(1, 7):
            subprocess.run(["sudo", "chroot", dst_folder, "systemctl", "disable", f"getty@tty{i}.service"], check=True)
            subprocess.run(["sudo", "chroot", dst_folder, "systemctl", "mask", f"getty@tty{i}.service"], check=True)

        print("Disabling serial console (ttyS0)...")
        subprocess.run(["sudo", "chroot", dst_folder, "systemctl", "disable", "serial-getty@ttyS0.service"], check=True)
        subprocess.run(["sudo", "chroot", dst_folder, "systemctl", "mask", "serial-getty@ttyS0.service"], check=True)

        grub_file = os.path.join(dst_folder, "etc/default/grub")
        if os.path.exists(grub_file):
            print("Removing TTY kernel console configuration from GRUB...")
            subprocess.run(["sudo", "sed", "-i", "s/console=.*//g", grub_file], check=True)
            subprocess.run(["sudo", "sed", "-i", 's/^GRUB_CMDLINE_LINUX_DEFAULT="\(.*\)"/GRUB_CMDLINE_LINUX_DEFAULT="\\1 console=none"/', grub_file], check=True)

        print("Disabling TTY devices...")
        tty_devices = ["tty", "tty0", "tty1", "tty2", "tty3", "tty4", "tty5", "tty6", "ttyS0"]
        for dev in tty_devices:
            dev_path = os.path.join(dst_folder, "dev", dev)
            if os.path.exists(dev_path):
                try:
                    os.rename(dev_path, os.path.join(dst_folder, "dev", f"{dev}_disabled"))
                except Exception:
                    pass

        print("Disabling kernel messages to console...")
        subprocess.run(["sudo", "chroot", dst_folder, "dmesg", "--console-off"], check=False)
        print("Black box preparation complete. No TTY or console interfaces are accessible.")
    else:
        print("Debug mode enabled. Skipping black box preparation.")

    # Remove any data in the tmp folder
    subprocess.run(["sudo", "rm", "-rf", os.path.join(dst_folder, "tmp")], check=True)

    # Rename home, etc, var directories (e.g. rename root to root_ro)
    for d in ["root", "etc", "var"]:
        src_dir = os.path.join(dst_folder, d)
        if os.path.exists(src_dir):
            os.rename(src_dir, os.path.join(dst_folder, f"{d}_ro"))
    # Create new home, etc, var, and tmp directories
    for d in ["home", "etc", "var", "tmp"]:
        os.makedirs(os.path.join(dst_folder, d), exist_ok=True)

    # Copy the contents of root_ro back into the new root directory
    root_ro = os.path.join(dst_folder, "root_ro")
    if os.path.exists(root_ro):
        subprocess.run(["sudo", "cp", "-r", root_ro, os.path.join(dst_folder, "root")], check=True)

def setup_guest_image(image, out_image, out_hash_tree, out_root_hash, debug):
    """
    Builds a dm-verity image using the provided configuration dictionary.
    
    Expected configuration keys include:
      - image: Path to the source VM image.
      - out_image: (Optional) Output path to the verity image (default: "image.qcow2").
      - out_hash_tree: (Optional) Output path to the device hash tree (default: "hash_tree.bin").
      - out_root_hash: (Optional) Output path to the root hash file (default: "roothash.txt").
      - debug: (Optional) Debug flag (default: "0").
      - non_interactive: (Optional) Boolean flag for non-interactive mode.
    """
    # Set up global context values.
    ctx["SRC_DEVICE"] = "/dev/nbd0"
    ctx["DST_DEVICE"] = "/dev/nbd1"
    ctx["SRC_FOLDER"] = tempfile.mkdtemp()
    ctx["DST_FOLDER"] = tempfile.mkdtemp()
    ctx["SRC_IMAGE"] = image
    ctx["DST_IMAGE"] = out_image
    ctx["HASH_TREE"] = out_hash_tree
    ctx["ROOT_HASH"] = out_root_hash
    ctx["NON_INTERACTIVE"] = True
    ctx["DEBUG"] = debug

    # Determine the script path and build directory (assuming relative location)
    script_path = os.path.realpath(os.path.dirname(__file__))
    ctx["BUILD_DIR"] = os.path.join(script_path, "..", "..", "build")

    # Register cleanup to run on exit.
    atexit.register(clean_up)

    print("Creating output image..")
    create_output_image()

    print("Initializing NBD module..")
    initialize_nbd()

    print("Finding root filesystem..")
    find_root_fs_device()
    print("Rootfs device selected:", ctx.get("SRC_ROOT_FS_DEVICE", "Not found"))

    print("Creating ext4 partition on output image..")
    subprocess.run(["sudo", "mkfs.ext4", ctx["DST_DEVICE"]], check=True)

    print("Mounting images..")
    subprocess.run(["sudo", "mount", ctx.get("SRC_ROOT_FS_DEVICE"), ctx["SRC_FOLDER"]], check=True)
    subprocess.run(["sudo", "mount", ctx["DST_DEVICE"], ctx["DST_FOLDER"]], check=True)

    print("Copying files (this may take some time)..")
    copy_filesystem()

    print("Copying HyperBEAM..")
    subprocess.run(["sudo", "rsync", "-axHAWXS", "--numeric-ids", "--info=progress2",
                    f"{ctx['BUILD_DIR']}/hb/hb",
                    os.path.join(ctx["DST_FOLDER"], "root")],
                   check=True)
    print("Copying HyperBEAM service..")
    subprocess.run(["sudo", "rsync", "-axHAWXS", "--numeric-ids", "--info=progress2",
                    f"{ctx['BUILD_DIR']}/hb/hyperbeam.service",
                    os.path.join(ctx["DST_FOLDER"], "etc", "systemd", "system", "hyperbeam.service")],
                   check=True)
    print("Enabling HyperBEAM service..")
    subprocess.run(["sudo", "chroot", ctx["DST_FOLDER"], "systemctl", "enable", "hyperbeam.service"],
                   check=True)
    print("Copying CU..")
    subprocess.run(["sudo", "rsync", "-axHAWXS", "--numeric-ids", "--info=progress2",
                    f"{ctx['BUILD_DIR']}/hb/cu",
                    os.path.join(ctx["DST_FOLDER"], "root")],
                   check=True)
    print("Copying CU service..")
    subprocess.run(["sudo", "rsync", "-axHAWXS", "--numeric-ids", "--info=progress2",
                    f"{ctx['BUILD_DIR']}/hb/cu.service",
                    os.path.join(ctx["DST_FOLDER"], "etc", "systemd", "system", "cu.service")],
                   check=True)
    print("Enabling CU service..")
    subprocess.run(["sudo", "chroot", ctx["DST_FOLDER"], "systemctl", "enable", "cu.service"],
                   check=True)

    print("Preparing output filesystem for dm-verity..")
    prepare_verity_fs()

    print("Unmounting images..")
    subprocess.run(["sudo", "umount", "-q", ctx["SRC_FOLDER"]], check=True)
    subprocess.run(["sudo", "umount", "-q", ctx["DST_FOLDER"]], check=True)

    print("Computing hash tree..")
    try:
        result = subprocess.run(["sudo", "veritysetup", "format", ctx["DST_DEVICE"], ctx["HASH_TREE"]],
                                check=True, capture_output=True, text=True)
        root_hash = None
        for line in result.stdout.splitlines():
            if line.startswith("Root"):
                parts = line.split()
                if len(parts) >= 2:
                    root_hash = parts[1]
                    break
        if root_hash:
            with open(ctx["ROOT_HASH"], "w") as f:
                f.write(root_hash)
            print("Root hash:", root_hash)
        else:
            print("Failed to extract root hash.")
    except Exception as e:
        print("Error computing hash tree:", e)
        sys.exit(1)

    print("All done!")
