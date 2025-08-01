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


def init() -> None:
    """
    Initialize the build environment:
      - Create necessary directories.
      - Install dependencies.
      - Download and extract SNP release.
      - Build attestation server and digest calculator.
    """

    # Go thru all config.dir and create the directories if they don't exist
    for d in config.dir.__dict__.values():
        if isinstance(d, str):
            ensure_directory(d)

    # Install dependencies.
    install_dependencies(force=False)

    # Download and extract SNP release tarball.
    tarball = os.path.join(config.dir.build, "snp-release.tar.gz")
    url = "https://github.com/SNPGuard/snp-guard/releases/download/v0.1.2/snp-release.tar.gz"
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(tarball, "wb") as f:
            shutil.copyfileobj(r.raw, f)
    run_command(f"tar -xf {tarball} -C {config.dir.build}")
    run_command(f"rm {tarball}")

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


def setup_host() -> None:
    """
    Set up the host system using the SNP release installer.
    """
    snp_release_dir = os.path.join(config.dir.build, "snp-release")
    run_command(f"cd {snp_release_dir} && sudo ./install.sh")