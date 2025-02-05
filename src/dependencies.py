#!/usr/bin/env python3
import os
import sys
import subprocess
import time
import shutil
import traceback

# ANSI color definitions
COLOR_OFF = '\033[0m'
BBLACK = '\033[1;30m'
BRED   = '\033[1;31m'
BGREEN = '\033[1;32m'
BYELLOW= '\033[1;33m'
BBLUE  = '\033[1;34m'
BWHITE = '\033[1;37m'

def wait_for_enter():
    """Wait until the user presses ENTER."""
    try:
        input()
    except KeyboardInterrupt:
        sys.exit(1)

def check_root():
    """Ensure the script is not run as root."""
    if os.geteuid() == 0:
        warn("Please do not run this script as root")
        sys.exit(1)

def check_sudo():
    """Check that sudo exists and that the current user can run it."""
    if shutil.which("sudo") is None:
        warn("'sudo' is not installed on the machine. Please log in as 'root' and run 'apt-get update && apt-get install sudo'")
        sys.exit(1)
    try:
        subprocess.run("sudo ls", shell=True,
                       stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL,
                       check=True)
    except subprocess.CalledProcessError:
        warn("It seems like you don't have root privileges. Please make sure you are added to the 'sudo' group.")
        sys.exit(1)

def check_distro():
    """Warn if not running Ubuntu or Debian."""
    try:
        with open("/etc/os-release", "r") as f:
            os_info = f.read()
    except Exception:
        os_info = ""
    if ('NAME="Ubuntu"' in os_info) or ('NAME="Debian GNU/Linux"' in os_info):
        return
    else:
        print(f"{BYELLOW}It seems like you are running a different OS than Ubuntu or Debian, which this script does not support.")
        print("If you think this is an error or if you want to continue anyway, press ENTER, otherwise exit with CTRL-C")
        print(COLOR_OFF, end="")
        wait_for_enter()

def start(force):
    """Display welcome and force-mode messages then wait for confirmation."""
    print(f"{BWHITE}Welcome! This script will install all the required dependencies to run our artifacts.{COLOR_OFF}")
    if not force:
        print("By default, this script will *not* attempt to install components that are already installed.")
        print("This means that if you have outdated versions installed, you *might* encounter problems when running the artifacts.")
        print("If you want to install up-to-date packages, run this script with '-f' instead.")
    else:
        print("You are running the script in *force* mode: any existing dependencies will be replaced with up-to-date versions.")
        print("If you do *not* want to overwrite the current packages, run this script without '-f' instead.")
    print(f"{BGREEN}Press ENTER to continue, or CTRL-C to exit{COLOR_OFF}")
    wait_for_enter()

def err_report(line):
    """Print an error report message."""
    print(f"{BRED}Could not install all dependencies correctly due to an error on line {line}")
    print("Running the artifacts with the current setup might cause errors.")
    print("We recommend fixing the error and then running this script again to complete the installation.")
    print(COLOR_OFF)

def print_section(section_name):
    """Print a section header."""
    print()
    print(f"{BYELLOW}### Installing {section_name} ###{COLOR_OFF}")

def success():
    """Print a success message."""
    print()
    print(f"{BGREEN}Success! Your machine is now set up correctly for running the artifacts.")
    print("You may need to reload your shell to use certain components.")
    print(COLOR_OFF)

def info(message):
    """Print an informational message."""
    print(f"{BBLUE}{message}{COLOR_OFF}")

def warn(message):
    """Print a warning message."""
    print(f"{BYELLOW}{message}{COLOR_OFF}")

def run_command(command, ignore_errors=False):
    """Run a shell command and exit on error (unless ignore_errors is True)."""
    print(f"Running: {command}")
    try:
        subprocess.run(command, shell=True, check=True)
    except subprocess.CalledProcessError as e:
        if not ignore_errors:
            tb = traceback.extract_tb(sys.exc_info()[2])
            line_no = tb[-1].lineno if tb else "unknown"
            err_report(line_no)
            sys.exit(e.returncode)

def install_dependencies(force=False):
    """
    Install all required dependencies.
    
    :param force: If True, force reinstallation of components even if already installed.
    """
    try:
        check_distro()
        check_root()
        check_sudo()
        start(force)

        # Install apt dependencies
        print_section("apt dependencies")
        run_command("sudo apt update")
        apt_install_cmd = (
            "sudo apt install -y git curl wget make whois pv genisoimage "
            "qemu-utils pkg-config gcc libssl-dev cpio kmod fdisk rsync cryptsetup jq"
        )
        run_command(apt_install_cmd)

        # Docker installation
        print_section("Docker")
        if shutil.which("docker") is None or force:
            info("Uninstalling old versions (if present)...")
            packages = ["docker.io", "docker-doc", "docker-compose", "podman-docker", "containerd", "runc"]
            for pkg in packages:
                run_command(f"sudo apt-get remove -y {pkg}", ignore_errors=True)
            info("Getting Docker. Note: you may see a warning from the Docker script; it can be safely ignored.")
            time.sleep(5)
            run_command("curl -fsSL https://get.docker.com -o get-docker.sh")
            run_command("sudo sh ./get-docker.sh")
            if os.path.exists("get-docker.sh"):
                os.remove("get-docker.sh")
            user = os.environ.get("USER")
            run_command(f"sudo usermod -aG docker {user}")
        else:
            print("Seems like Docker is already installed, skipping.")

        # Rust toolchain installation
        print_section("Rust toolchain")
        if shutil.which("cargo") is None or force:
            info("Getting Rust toolchain. We recommend choosing the default install option.")
            time.sleep(5)
            run_command("curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh")
            run_command(". \"$HOME/.cargo/env\"")
        else:
            print("Seems like Rust is already installed, skipping.")

        # Install libslirp 4.7.0 packages
        print_section("libslirp 4.7.0 (Needed to enable user networking in QEMU)")
        libslirp_vers = subprocess.getoutput("dpkg -l | grep libslirp0 | awk '{print $3}'").strip()
        libslirp_dev_vers = subprocess.getoutput("dpkg -l | grep libslirp-dev | awk '{print $3}'").strip()

        if not libslirp_vers.startswith("4.7.0"):
            info("Installing libslirp0 4.7.0")
            run_command("wget -nv http://ftp.de.debian.org/debian/pool/main/libs/libslirp/libslirp0_4.7.0-1_amd64.deb -O libslirp0.deb")
            run_command("sudo dpkg -i libslirp0.deb")
            run_command("rm -rf libslirp0.deb")
        else:
            print("Seems like libslirp0 4.7.0 is already installed, skipping.")

        if not libslirp_dev_vers.startswith("4.7.0"):
            info("Installing libslirp-dev 4.7.0")
            run_command("wget -nv http://ftp.de.debian.org/debian/pool/main/libs/libslirp/libslirp-dev_4.7.0-1_amd64.deb -O libslirp-dev.deb")
            run_command("sudo dpkg -i libslirp-dev.deb")
            run_command("rm -rf libslirp-dev.deb")
        else:
            print("Seems like libslirp-dev 4.7.0 is already installed, skipping.")

        success()
    except Exception:
        traceback.print_exc()
        sys.exit(1)

# When run directly, parse command-line arguments to set force mode.
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="Install dependencies required for running the artifacts."
    )
    parser.add_argument(
        "-f", "--force", action="store_true", help="Force reinstallation of dependencies."
    )
    args = parser.parse_args()
    install_dependencies(force=args.force)
