#!/usr/bin/env python3
"""
Core initialization functionality moved from the run script.
Contains the exact same functions without modifications.
"""

import os
import shutil
import requests
from typing import Optional
from config import config
from src.services import install_dependencies
from src.utils import run_command, ensure_directory


def init(snp_release_path: Optional[str] = None) -> None:
    """
    Initialize the build environment:
      - Create necessary directories.
      - Install dependencies.
      - Download and extract SNP release (or use provided path).
      - Build attestation server and digest calculator.
      
    Args:
        snp_release_path: Optional path to pre-built SNP release directory or tarball
    """

    # Go thru all config.dir and create the directories if they don't exist
    for d in config.dir.__dict__.values():
        if isinstance(d, str):
            ensure_directory(d)

    # Install dependencies.
    install_dependencies(force=False)

    # Handle SNP release - either use provided path or download default
    if snp_release_path:
        print(f"Using provided SNP release: {snp_release_path}")
        
        if os.path.isfile(snp_release_path) and snp_release_path.endswith('.tar.gz'):
            # Extract provided tarball
            print("Extracting provided SNP release tarball...")
            run_command(f"tar -xf {snp_release_path} -C {config.dir.build}")
        elif os.path.isdir(snp_release_path):
            # Copy provided directory
            print("Copying provided SNP release directory...")
            dest_dir = os.path.join(config.dir.build, "snp-release")
            if os.path.exists(dest_dir):
                shutil.rmtree(dest_dir)
            shutil.copytree(snp_release_path, dest_dir)
        else:
            raise ValueError(f"Invalid SNP release path: {snp_release_path}")
    else:
        # Download and extract default SNP release tarball.
        tarball = os.path.join(config.dir.build, "snp-release.tar.gz")
        print("Downloading SNP release...")
        url = config.snp.release_url
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            with open(tarball, "wb") as f:
                shutil.copyfileobj(r.raw, f)
        run_command(f"tar -xf {tarball} -C {config.dir.build}")
        run_command(f"rm {tarball}")
    
    # Download the GPU admin tools
    gpu_admin_tools_dir = os.path.join(config.dir.build, "gpu-admin-tools")
    if os.path.exists(gpu_admin_tools_dir):
        print("GPU admin tools already exist, updating...")
        run_command(f"cd {gpu_admin_tools_dir} && git pull")
    else:
        print("Cloning GPU admin tools...")
        run_command(f"cd {config.dir.build} && git clone {config.build.gpu_admin_tools_repo}")

    # Build attestation server binaries.
    run_command("cargo build --manifest-path=tools/attestation_server/Cargo.toml")
    for binary in [
        "server",
        "client",
        "get_report",
        "idblock-generator",
        "sev-feature-info",
        "verify_report",
    ]:
        src = os.path.join("tools", "attestation_server", "target", "debug", binary)
        run_command(f"cp {src} {config.dir.bin}")

    # Build digest calculator binary.
    run_command("cargo build --manifest-path=tools/digest_calc/Cargo.toml")
    run_command(f"cp ./tools/digest_calc/target/debug/digest_calc {config.dir.bin}")
    setup_host()
    if config.build.enable_gpu:
        setup_gpu()
        os.environ["GPU_SETUP"] = "1"


def setup_host() -> None:
    """
    Set up the host system using the SNP release installer.
    """
    snp_release_dir = os.path.join(config.dir.build, "snp-release")
    run_command(f"cd {snp_release_dir} && sudo ./install.sh")

def setup_gpu() -> None:
    """
    Setup the GPU CC for the host system and configure GPU passthrough.
    """
    gpu_admin_tools_dir = os.path.join(config.dir.build, "gpu-admin-tools")

    # Enable GPU CC mode
    print("Setting up GPU Confidential Computing mode...")
    run_command(f"cd {gpu_admin_tools_dir} && sudo python3 ./nvidia_gpu_tools.py --devices gpus --set-cc-mode=on --reset-after-cc-mode-switch")

    # Configure GPU passthrough using the dedicated script
    print("Configuring GPU passthrough...")
    passthrough_script = os.path.join(os.getcwd(), "scripts", "gpu_passthrough.sh")
    run_command(f"sudo {passthrough_script} setup")