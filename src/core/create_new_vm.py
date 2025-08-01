#!/usr/bin/env python3
import os
import sys
import subprocess
import shutil
import getpass
import tempfile
import re
import crypt
from typing import Optional
from pathlib import Path
from src.utils import ensure_directory, run_command

def create_vm_image(new_vm: str, build_dir: str, template_user_data: str, size: int = 20, 
                   owner_pubkey_path: Optional[str] = None, server_privkey: Optional[str] = None) -> None:
    """
    Create a new VM disk image based on the Ubuntu cloud image and build a cloud-init config blob.
    
    Parameters:
      new_vm (str): Mandatory. The filename (ending with .qcow2) for the new VM disk image.
      build_dir (str): Optional. Directory where files will be written (default: ".")
      size (int): Optional. The size (in GB) to which the disk image is to be resized (default: 20)
      owner_pubkey_path (str): Optional. Path to the SSH public key to be added as the VM owner's key.
                               If not provided, a new ed25519 keypair is generated.
      server_privkey (str): Optional. Path to the SSH private key used by the OpenSSH server.
                            If not provided, a new ecdsa keypair is generated.
                            (The corresponding public key is assumed to be the private key path with ".pub" appended.)
    """
    # Check that new_vm is provided.
    if not new_vm:
        raise ValueError("The 'new_vm' parameter (image name) is mandatory.")

    # Resolve and create the build directory.
    build_dir = os.path.realpath(build_dir)
    ensure_directory(build_dir)
    if not os.path.isdir(build_dir):
        raise ValueError(f"Invalid build directory: {build_dir}")

    # Set base image location and download URL.
    base_disk = "/tmp/jammy-server-base.qcow2"
    base_image_url = "https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img"

    # Download the base image if it does not exist.
    if not os.path.exists(base_disk):
        print(f"Downloading base image to {base_disk} …")
        run_command(f"wget -O {base_disk} {base_image_url}")
    else:
        print(f"Base image {base_disk} already exists.")

    # Create a copy in the build directory with the new VM name.
    new_vm_path = os.path.join(build_dir, new_vm)
    print(f"Copying base image to {new_vm_path} …")
    # Remove the existing file if it exists.
    if os.path.exists(new_vm_path):
        os.remove(new_vm_path)
    shutil.copy2(base_disk, new_vm_path)

    # Resize the new VM disk image using qemu-img.
    print(f"Resizing {new_vm_path} to {size}G …")
    run_command(f"qemu-img resize {new_vm_path} {size}G")

    # Prepare the keys directory.
    keys_path = os.path.join(build_dir, "keys")
    ensure_directory(keys_path)

    # Generate owner key pair if not provided.
    if not owner_pubkey_path:
        default_owner_key = os.path.join(keys_path, "ssh-key-vm-owner")
        print(f"No owner public SSH key provided. Generating a new keypair at {default_owner_key} …")
        run_command(f"ssh-keygen -t ed25519 -N '' -f {default_owner_key}")
        owner_pubkey_path = default_owner_key + ".pub"
    else:
        owner_pubkey_path = os.path.realpath(owner_pubkey_path)

    # Generate server key pair if not provided.
    if not server_privkey:
        default_server_key = os.path.join(keys_path, "ssh-server-key-vm")
        print(f"No server SSH key provided. Generating a new keypair at {default_server_key} …")
        run_command(f"ssh-keygen -t ecdsa -N '' -f {default_server_key}")
        server_privkey = default_server_key
        server_pubkey = default_server_key + ".pub"
    else:
        server_privkey = os.path.realpath(server_privkey)
        server_pubkey = server_privkey + ".pub"

    # Query username and password from the user.
    username = input("Enter username: ")
    password = getpass.getpass("Enter Password: ")

    # Create a password hash using SHA-512 with 4096 rounds.
    try:
        salt = crypt.mksalt(crypt.METHOD_SHA512, rounds=4096)
    except TypeError:
        salt = crypt.mksalt(crypt.METHOD_SHA512)
    pwhash = crypt.crypt(password, salt)

    # Create cloud-init configuration.
    config_path = os.path.join(build_dir, "config")
    ensure_directory(config_path)
    user_data_path = os.path.join(config_path, "user-data")

    # Determine the directory of this script (assumes the template is here).
    if not os.path.exists(template_user_data):
        raise FileNotFoundError(f"Template file not found: {template_user_data}")

    # Copy the template to the user-data file.
    shutil.copy2(template_user_data, user_data_path)

    # Perform substitutions in the user-data file.
    with open(user_data_path, "r") as f:
        user_data = f.read()

    user_data = user_data.replace("<USER>", username)
    user_data = user_data.replace("<PWDHASH>", pwhash)

    # Insert owner public key.
    with open(owner_pubkey_path, "r") as f:
        owner_pubkey = f.read().strip()
    user_data = user_data.replace("<USER_PUBKEY>", owner_pubkey)

    # Write updated user-data.
    with open(user_data_path, "w") as f:
        f.write(user_data)

    # Insert server private key (indented) after the line that starts with "ecdsa_private: |"
    with open(user_data_path, "r") as f:
        lines = f.readlines()
    with open(server_privkey, "r") as f:
        server_priv_lines = f.readlines()
    indented_server_priv = ["    " + line for line in server_priv_lines]

    new_lines = []
    inserted = False
    pattern = re.compile(r'^\s*ecdsa_private:\s*\|')
    for line in lines:
        new_lines.append(line)
        if not inserted and pattern.match(line):
            new_lines.extend(indented_server_priv)
            inserted = True

    with open(user_data_path, "w") as f:
        f.writelines(new_lines)

    # Replace <SERVER_PUBKEY> placeholder with server public key content.
    with open(server_pubkey, "r") as f:
        server_pubkey_content = f.read().strip()
    with open(user_data_path, "r") as f:
        user_data = f.read()
    user_data = user_data.replace("<SERVER_PUBKEY>", server_pubkey_content)
    with open(user_data_path, "w") as f:
        f.write(user_data)

    # Prepare to build the config blob.
    out_cfg_blob = os.path.join(build_dir, "config-blob.img")
    # Create empty meta-data and network-config files.
    meta_data_path = os.path.join(config_path, "meta-data")
    network_config_path = os.path.join(config_path, "network-config")
    Path(meta_data_path).touch()
    Path(network_config_path).touch()

    # Build the config blob using genisoimage.
    geniso_cmd = (
        f"genisoimage -output {out_cfg_blob} -volid cidata -rational-rock -joliet "
        f"{user_data_path} {meta_data_path} {network_config_path}"
    )
    print("Creating config blob …")
    run_command(geniso_cmd)
    print(f"Config blob written to {out_cfg_blob}")

