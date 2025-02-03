#!/usr/bin/env python3
"""
This module provides common functions used by the verity image creation script.
It replicates the behavior of your common.sh.
All state is stored in the module-level dictionary `ctx`.
"""

import os
import subprocess
import tempfile
import time
import sys
import re
import shutil

# Global context dictionary; keys will hold device paths, temporary folders, etc.
ctx = {}

def clean_up():
    """Cleanup function to be called on exit."""
    print("Cleaning up")
    # Unmount and remove SRC_FOLDER if it exists
    if ctx.get("SRC_FOLDER") and os.path.exists(ctx["SRC_FOLDER"]):
        print("Unmounting", ctx["SRC_FOLDER"])
        subprocess.run(["sudo", "umount", "-q", ctx["SRC_FOLDER"]], check=False)
        shutil.rmtree(ctx["SRC_FOLDER"], ignore_errors=True)
    # Unmount and remove DST_FOLDER if it exists
    if ctx.get("DST_FOLDER") and os.path.exists(ctx["DST_FOLDER"]):
        print("Unmounting", ctx["DST_FOLDER"])
        subprocess.run(["sudo", "umount", "-q", ctx["DST_FOLDER"]], check=False)
        shutil.rmtree(ctx["DST_FOLDER"], ignore_errors=True)
    # Close mapper device if present
    if os.path.exists("/dev/mapper/snpguard_root"):
        print("Closing mapper device")
        subprocess.run(["sudo", "cryptsetup", "luksClose", "snpguard_root"], check=False)
    unmount_lvm_device()
    need_sleep = 0
    if ctx.get("SRC_DEVICE") and os.path.exists(ctx["SRC_DEVICE"]):
        print("Disconnecting", ctx["SRC_DEVICE"])
        subprocess.run(["sudo", "qemu-nbd", "--disconnect", ctx["SRC_DEVICE"]], check=False)
        need_sleep = 1
    if ctx.get("DST_DEVICE") and os.path.exists(ctx["DST_DEVICE"]):
        print("Disconnecting", ctx["DST_DEVICE"])
        subprocess.run(["sudo", "qemu-nbd", "--disconnect", ctx["DST_DEVICE"]], check=False)
        need_sleep = 1
    if need_sleep:
        time.sleep(2)
    subprocess.run(["sudo", "modprobe", "-r", "nbd"], check=False)

def find_root_fs_device():
    """
    Identifies the device containing the root filesystem.
    First, it calls get_lvm_device(); if none is found, it parses fdisk output.
    In interactive mode, it asks the user to confirm or provide an alternative.
    """
    get_lvm_device()
    if ctx.get("SRC_ROOT_FS_DEVICE"):
        return

    try:
        result = subprocess.run(["sudo", "fdisk", ctx["SRC_DEVICE"], "-l"],
                                check=True, capture_output=True, text=True)
        for line in result.stdout.splitlines():
            if "Linux filesystem" in line:
                parts = line.split()
                if parts:
                    ctx["SRC_ROOT_FS_DEVICE"] = parts[0]
                    break
    except Exception as e:
        print("Error running fdisk:", e)

    if ctx.get("NON_INTERACTIVE"):
        return

    # Show fdisk output to the user
    subprocess.run(["sudo", "fdisk", ctx["SRC_DEVICE"], "-l"])
    if ctx.get("SRC_ROOT_FS_DEVICE"):
        print("Found the following filesystem:", ctx["SRC_ROOT_FS_DEVICE"])
        choice = input("Do you confirm that this is correct? (y/n): ")
        if choice.lower() != "y":
            ctx["SRC_ROOT_FS_DEVICE"] = input("Enter device containing the root filesystem: ")
            if not os.path.exists(ctx["SRC_ROOT_FS_DEVICE"]):
                print("Could not find root filesystem.")
                sys.exit(1)
    else:
        print("Failed to identify root filesystem.")
        ctx["SRC_ROOT_FS_DEVICE"] = input("Enter device containing the root filesystem: ")
        if not os.path.exists(ctx["SRC_ROOT_FS_DEVICE"]):
            print("Could not find root filesystem.")
            sys.exit(1)

def check_lvm():
    """Warn if any LVM filesystem is already in use on the host."""
    try:
        result = subprocess.run(["sudo", "lvdisplay"], check=True,
                                capture_output=True, text=True)
        count = len([line for line in result.stdout.splitlines() if "LV Path" in line])
        if count > 0:
            print("Warning: a LVM filesystem is currently in use on your system.")
            print("If your guest VM image uses LVM as well, this script might not work as intended.")
            time.sleep(2)
    except subprocess.CalledProcessError:
        pass

def get_lvm_device():
    """
    Store the number of LVM devices present before mounting the VM image.
    Then, if new LVM devices appear afterward, assume the image uses LVM.
    """
    try:
        result = subprocess.run(["sudo", "lvdisplay"],
                                check=True, capture_output=True, text=True)
        ctx["__LVM_DEVICES"] = len([line for line in result.stdout.splitlines() if "LV Path" in line])
    except subprocess.CalledProcessError:
        ctx["__LVM_DEVICES"] = 0

    # Check for any warnings
    try:
        result = subprocess.run(["sudo", "lvdisplay"],
                                check=False, capture_output=True, text=True)
        if "WARNING" in result.stderr:
            print("Error: seems like the guest VM had a LVM filesystem that could not be mounted")
            print("Cannot continue. Try creating a new VM using our guide.")
            print("Log from lvdisplay:")
            print(result.stderr)
            sys.exit(1)
    except Exception:
        pass

    try:
        result = subprocess.run(["sudo", "lvdisplay"],
                                check=True, capture_output=True, text=True)
        current_lvm = len([line for line in result.stdout.splitlines() if "LV Path" in line])
        if current_lvm > ctx.get("__LVM_DEVICES", 0):
            lv_paths = [line for line in result.stdout.splitlines() if "LV Path" in line]
            ctx["SRC_ROOT_FS_DEVICE"] = lv_paths[-1].split()[-1]
            print("Found LVM2 filesystem:", ctx["SRC_ROOT_FS_DEVICE"])
    except Exception:
        pass

def unmount_lvm_device():
    """Unmount any LVM devices that appeared after mounting the VM image."""
    try:
        result = subprocess.run(["sudo", "lvdisplay"],
                                check=True, capture_output=True, text=True)
        current_lvm = len([line for line in result.stdout.splitlines() if "LV Path" in line])
        if current_lvm > ctx.get("__LVM_DEVICES", 0):
            print("Unmounting LVM device")
            lv_paths = [line for line in result.stdout.splitlines() if "LV Path" in line]
            lvm_path = lv_paths[-1].split()[-1]
            vg_name = ""
            for line in result.stdout.splitlines():
                if "VG Name" in line:
                    vg_name = line.split()[-1]
            subprocess.run(["sudo", "lvchange", "-an", lvm_path], check=False)
            subprocess.run(["sudo", "vgchange", "-an", vg_name], check=False)
    except Exception:
        pass

def initialize_nbd():
    """
    Loads the NBD module and connects the source and destination images
    to their respective NBD devices.
    """
    check_lvm()
    subprocess.run(["sudo", "modprobe", "nbd", "max_part=8"], check=True)
    subprocess.run(["sudo", "qemu-nbd", "--connect=" + ctx["SRC_DEVICE"], ctx["SRC_IMAGE"]],
                   check=True)
    subprocess.run(["sudo", "qemu-nbd", "--connect=" + ctx["DST_DEVICE"], ctx["DST_IMAGE"]],
                   check=True)

def create_output_image():
    """
    Creates the destination image using the size (virtual size) of the source image.
    """
    try:
        result = subprocess.run(["qemu-img", "info", ctx["SRC_IMAGE"]],
                                check=True, capture_output=True, text=True)
        size = None
        for line in result.stdout.splitlines():
            if "virtual size:" in line:
                m = re.search(r'virtual size:\s+([\d\.]+)([GMK])', line)
                if m:
                    size = m.group(1) + m.group(2)
                    break
        if not size:
            print("Failed to determine image size.")
            sys.exit(1)
        subprocess.run(["qemu-img", "create", "-f", "qcow2", ctx["DST_IMAGE"], size], check=True)
    except Exception as e:
        print("Error creating output image:", e)
        sys.exit(1)

def copy_filesystem():
    """
    Uses rsync to copy the contents from SRC_FOLDER/ to DST_FOLDER/.
    The trailing slash ensures that only the content is copied.
    """
    subprocess.run(["sudo", "rsync", "-axHAWXS", "--numeric-ids", "--info=progress2",
                    ctx["SRC_FOLDER"] + "/", ctx["DST_FOLDER"] + "/"], check=True)
