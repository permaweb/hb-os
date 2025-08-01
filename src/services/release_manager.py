#!/usr/bin/env python3
"""
Release management functionality moved from the run script.
Contains the exact same functions without modifications.
"""

import os
import re
import shutil
import subprocess
import tarfile
import requests
from typing import Optional
from config import config
from src.utils import run_command


def package_release() -> None:
    """
    Package all files needed for starting the VM (as used in start_vm) into a release folder,
    then create a tar.gz archive of that folder using the shell tar command with verbose output.
    This function reads vm-config.toml to determine the paths for kernel_file, ovmf_file,
    and initrd_file, copies those files into the release folder, and updates the config file
    to point to the relative paths.
    """
    print("Starting package_release()...")

    # Define the release directory path relative to the current working directory.
    release_dir = os.path.join(os.getcwd(), "release")
    print(f"Release directory will be: {release_dir}")

    # Clean up the release folder if it exists.
    if os.path.exists(release_dir):
        print("Release directory exists. Removing it...")
        shutil.rmtree(release_dir)
    os.makedirs(release_dir, exist_ok=True)
    print("Created release directory.")

    # Copy verity image and hash tree into the release folder.
    files_to_copy = [config.verity_image, config.verity_hash_tree]
    for file in files_to_copy:
        print(f"Attempting to copy {file} ...")
        if os.path.exists(file):
            try:
                shutil.copy(file, release_dir)
                print(f"Copied {file} to {release_dir}")
            except PermissionError:
                print(f"Permission denied copying {file}, trying with sudo...")
                try:
                    # Use sudo to copy the file
                    dest_file = os.path.join(release_dir, os.path.basename(file))
                    run_command(f"sudo cp {file} {dest_file}")
                    # Fix permissions on the copied file
                    run_command(f"sudo chown {os.getenv('USER', 'hb')}:{os.getenv('USER', 'hb')} {dest_file}")
                    run_command(f"sudo chmod 644 {dest_file}")
                    print(f"Copied {file} to {release_dir} using sudo and fixed permissions")
                except Exception as e:
                    print(f"Error: Failed to copy {file} even with sudo: {e}")
                    print("You may need to run this script with appropriate permissions")
        else:
            print(f"Warning: {file} does not exist and cannot be copied")

    # Read the original vm-config.toml file.
    if not os.path.exists(config.vm_config_file):
        print(f"Error: {config.vm_config_file} does not exist.")
        return

    print(f"Reading configuration from {config.vm_config_file} ...")
    with open(config.vm_config_file, "r") as f:
        config_contents = f.read()
    print("Original vm-config.toml contents:")
    print(config_contents)

    # Define the keys whose file paths we want to update.
    keys = ["kernel_file", "ovmf_file", "initrd_file"]
    extra_files = {}

    # For each key, use a regex to extract the file path.
    for key in keys:
        # This regex expects lines like: key = "some_path"
        print(f"Extracting value for key '{key}' ...")
        match = re.search(rf'^\s*{key}\s*=\s*"(.*?)"\s*$', config_contents, flags=re.MULTILINE)
        if match:
            extra_files[key] = match.group(1)
            print(f"Found {key} = {extra_files[key]}")
        else:
            print(f"Warning: {key} not found in {config.vm_config_file}")

    # Copy each extra file (if it exists) into the release folder.
    for key, filepath in extra_files.items():
        print(f"Attempting to copy {key} file: {filepath} ...")
        if os.path.exists(filepath):
            shutil.copy(filepath, release_dir)
            print(f"Copied {filepath} to {release_dir}")
        else:
            print(f"Warning: {filepath} for {key} does not exist and cannot be copied")

    # Update the config contents so that the file paths for the keys point to "./release/<basename>".
    for key, filepath in extra_files.items():
        new_path = "./release/" + os.path.basename(filepath)
        print(f"Updating {key} to point to {new_path} ...")
        # Replace the line using regex; assume the key appears on a line by itself.
        config_contents = re.sub(
            rf'^\s*{key}\s*=\s*".*?"\s*$',
            f'{key} = "{new_path}"',
            config_contents,
            flags=re.MULTILINE
        )

    print("Updated vm-config.toml contents:")
    print(config_contents)

    # Write the updated config to a new file in the release folder.
    vm_config_release = os.path.join(release_dir, os.path.basename(config.vm_config_file))
    with open(vm_config_release, "w") as f:
        f.write(config_contents)
    print(f"Wrote updated config to {vm_config_release}")

    # Define the path for the tar.gz archive.
    tar_path = os.path.join(os.getcwd(), "release.tar.gz")
    print(f"Tar archive will be created at: {tar_path}")

    # Build the shell tar command.
    # -c: create archive, -v: verbose, -z: gzip, -f: filename, -C: change to directory before archiving.
    tar_cmd = f"tar -cvzf {tar_path} -C {os.path.dirname(release_dir)} {os.path.basename(release_dir)}"
    print(f"Executing tar command: {tar_cmd}")

    # Execute the tar command.
    subprocess.run(tar_cmd, shell=True, check=True)
    print(f"Packaged release folder into {tar_path}")
    print("package_release() completed successfully.")


def download_release(url: str) -> None:
    """
    Download a tar.gz release from the provided URL and extract it into the release folder.
    """
    release_dir = os.path.join(os.getcwd(), "release")
    # Remove the entire release directory if it exists.
    if os.path.exists(release_dir):
        shutil.rmtree(release_dir)

    tarball_path = os.path.join(os.getcwd(), "release_download.tar.gz")
    print(f"Downloading release from {url} ...")
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(tarball_path, "wb") as f:
            shutil.copyfileobj(r.raw, f)
    print(f"Downloaded tarball to {tarball_path}")

    print(f"Extracting {tarball_path} to {os.getcwd()} ...")
    # Extract the tar.gz file
    with tarfile.open(tarball_path, "r:gz") as tar:
        tar.extractall(path=os.getcwd())
    os.remove(tarball_path)

    digest_calc_path = os.path.join(config.dir.bin, "digest_calc")
    out_file = os.path.join(os.getcwd(), "inputs.json")
    vm_config_release = os.path.join(release_dir, os.path.basename(config.vm_config_file))
    run_command(
        f"{digest_calc_path} --vm-definition {vm_config_release} > {out_file}"
    )
    print("Extraction complete.")


def clean() -> None:
    """
    Clean up the build directory.
    """
    run_command(f"rm -rf {config.dir.build}")