#!/usr/bin/env python3
import os
import re
import sys
import json
import shlex
import argparse
import subprocess

from src.dependencies import install_dependencies
from src.create_new_vm import create_vm_image
from src.build_initramfs import build_initramfs
from src.build_content import build_guest_content
from src.create_vm_config import create_vm_config_file
from src.setup_guest import setup_guest_image

def load_config(config_file="config.json"):
    # Load the raw JSON config
    with open(config_file, "r") as f:
        config = json.load(f)
    
    config["DIRECTORIES"]["build"] = os.path.realpath(config["DIRECTORIES"]["build"])

    # Update directories to repalce ${build} with the build directory
    for key, value in config["DIRECTORIES"].items():
        config["DIRECTORIES"][key] = value.replace("${build}", config["DIRECTORIES"]["build"])

    # First, convert all directory values (in the DIRECTORIES section) to absolute paths.
    if "DIRECTORIES" in config:
        for key, value in config["DIRECTORIES"].items():
            config["DIRECTORIES"][key] = os.path.realpath(value)
    
    # Define a helper function to interpolate strings with placeholders like ${key}
    def interpolate_string(value, directories):
        # Regular expression to match ${...} patterns
        pattern = re.compile(r"\$\{([^}]+)\}")
        
        def replace(match):
            key = match.group(1)
            # Replace with the absolute directory value if present; otherwise, leave the placeholder unchanged.
            return directories.get(key, match.group(0))
        
        return pattern.sub(replace, value)
    
    # Define a recursive function to process dicts, lists, and strings.
    def recursive_interpolate(obj, directories):
        if isinstance(obj, dict):
            return {k: recursive_interpolate(v, directories) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [recursive_interpolate(item, directories) for item in obj]
        elif isinstance(obj, str):
            return interpolate_string(obj, directories)
        else:
            return obj
    
    # Retrieve the directories mapping (now with absolute paths)
    directories = config.get("DIRECTORIES", {})
    # Recursively interpolate all placeholders in the config
    processed_config = recursive_interpolate(config, directories)

    return processed_config

def run_command(cmd):
    """Run a shell command and exit if it fails."""
    print(f"Running: {cmd}")
    try:
        subprocess.run(cmd, shell=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Command failed: {cmd}")
        sys.exit(e.returncode)

def init(config):
    print("===> Initializing")
    # Ensure all required directories exist
    for d in [
        config["DIRECTORIES"]["build"],
        config["DIRECTORIES"]["build_bin"],
        config["DIRECTORIES"]["build_guest"]
    ]:
        os.makedirs(d, exist_ok=True)
        print(f"Ensured directory exists: {d}")
    
    # Install dependencies
    install_dependencies(force=False)
    
    # Download SNP release
    build_dir = config["DIRECTORIES"]["build"]
    tarball = os.path.join(build_dir, "snp-release.tar.gz")
    run_command(f"wget https://github.com/SNPGuard/snp-guard/releases/download/v0.1.2/snp-release.tar.gz -O {tarball}")
    run_command(f"tar -xf {tarball} -C {build_dir}")
    run_command(f"rm {tarball}")
    
    # Build attestation server
    bin_dir = config["DIRECTORIES"]["build_bin"]
    run_command("cargo build --manifest-path=tools/attestation_server/Cargo.toml")
    for binary in ["server", "client", "get_report", "idblock-generator", "sev-feature-info", "verify_report"]:
        src = os.path.join("tools", "attestation_server", "target", "debug", binary)
        run_command(f"cp {src} {bin_dir}")
    
    # Build digest calculator
    run_command("cargo build --manifest-path=tools/digest_calc/Cargo.toml")
    run_command(f"cp ./tools/digest_calc/target/debug/digest_calc {bin_dir}")

def create_vm(config):
    guest_dir = config["DIRECTORIES"]["build_guest"]
    image_name = config["BASE_IMAGE"]["name"]
    template_user_data = config["BASE_IMAGE"]["template_user_data"]
    create_vm_image(
        new_vm=image_name,
        build_dir=guest_dir,
        template_user_data=template_user_data
    )

def unpack_kernel(config):
    kernel_dir = config["DIRECTORIES"]["build_kernel"]
    kernel_deb = config["KERNEL"]["deb"]
    run_command(f"rm -rf {kernel_dir}")
    run_command(f"dpkg -x {kernel_deb} {kernel_dir}")

def initramfs(config):
    build_dir = config["DIRECTORIES"]["build"]
    resource_dir = config["DIRECTORIES"]["resources"]
    kernel_dir = config["DIRECTORIES"]["build_kernel"]
    init_script = config["INIT"]["script"]
    initrd = config["INIT"]["initrd"]
    build_initramfs(
        kernel_dir=kernel_dir,
        init_script=init_script,
        dockerfile=config["INIT"]["docker"],
        context_dir=resource_dir,
        out=initrd,
        build_dir=build_dir
    )

def run_setup(config):
    build_dir = config["DIRECTORIES"]["build"]
    qemu_launch_script = config["QEMU"]["launch_script"]
    memory = config["QEMU"]["memory"]
    cpus = config["VM_CONFIG"]["vcpu_count"]
    hb_port = config["QEMU"]["hb_port"]
    qemu_port = config["QEMU"]["qemu_port"]
    debug = config["DEBUG"]
    ovmf = config["KERNEL"]["ovmf"]
    policy = config["VM_CONFIG"]["guest_policy"]
    image_path = config["BASE_IMAGE"]["path"]
    cloud_config = config["BASE_IMAGE"]["cloud_config"]

    qemu_def_params = f"-default-network -log {os.path.join(build_dir, 'stdout.log')} -mem {memory} -smp {cpus}"
    qemu_extra_params = f"-bios {ovmf} -policy {policy}"
    cmd = (
        f"sudo -E {qemu_launch_script} {qemu_def_params} {qemu_extra_params} "
        f"-hda {image_path} -hdb {cloud_config} -hb-port {hb_port} -qemu-port {qemu_port} -debug {debug}"
    )
    run_command(cmd)

def build_base_image(config):
    print("===> Building base image")
    unpack_kernel(config)
    initramfs(config)
    create_vm(config)
    run_setup(config)

def build_content(config):
    out_dir = config["DIRECTORIES"]["build_content"]
    dockerfile = config["CONTENT"]["docker"]
    build_guest_content(out_dir, dockerfile)

def setup_verity(config):
    image = config["BASE_IMAGE"]["image"]
    verity_image = config["VERITY"]["image"]
    verity_hash_tree = config["VERITY"]["hash_tree"]
    verity_root_hash = config["VERITY"]["root_hash"]
    debug = config["DEBUG"]

    setup_guest_image(image, verity_image, verity_hash_tree, verity_root_hash, debug)

def setup_vm_config(config):
    kernel = config["KERNEL"]["vmlinuz"]
    initrd = config["INIT"]["initrd"]
    ovmf = config["KERNEL"]["ovmf"]
    out = config["VM"]["config_file"]
    kernel_cmdline = config["KERNEL"]["cmdline"] + " " + config["VERITY"]["params"]
    vm_config = config["VM_CONFIG"]

    create_vm_config_file(
        out_path=out, 
        ovmf_path=ovmf, 
        kernel_path=kernel, 
        initrd_path=initrd, 
        kernel_cmdline=kernel_cmdline, 
        vm_config=vm_config)

def get_hashes(config):
    bin_dir = config["DIRECTORIES"]["build_bin"]
    vm_config_file = config["VM"]["config_file"]
    build_dir = config["DIRECTORIES"]["build"]
    run_command(f"{os.path.join(bin_dir, 'digest_calc')} --vm-definition {vm_config_file} > {os.path.join(build_dir, 'measurement-inputs.json')}")

def build_guest_image(config):
    print("===> Building guest image")
    build_content(config)
    setup_verity(config)
    setup_vm_config(config)
    get_hashes(config)

def run_vm(config):
    build_dir = config["DIRECTORIES"]["build"]
    hb_port = config["QEMU"]["hb_port"]
    qemu_port = config["QEMU"]["qemu_port"]
    debug = config["DEBUG"]
    memory = config["QEMU"]["memory"]
    cpus = config["VM_CONFIG"]["cpus"]
    qemu_launch_script = config["QEMU"]["launch_script"]
    qemu_snp_params = config["QEMU"]["snp_params"]

    qemu_def_params = f"-default-network -log {os.path.join(build_dir, 'stdout.log')} -mem {memory} -smp {cpus}"
    verity_image = config["VERITY"]["image"]
    verity_hash_tree = config["VERITY"]["hash_tree"]
    vm_config_file = config["VM"]["config_file"]

    cmd = (
        f"sudo -E {qemu_launch_script} {qemu_def_params} {qemu_snp_params} "
        f"-hda {verity_image} -hdb {verity_hash_tree} -load-config {vm_config_file} "
        f"-hb-port {hb_port} -qemu-port {qemu_port} -debug {debug}"
    )
    run_command(cmd)

def setup_host(config):
    snp_release_dir = os.path.join(config["DIRECTORIES"]["build"], "snp-release")
    run_command(f"cd {snp_release_dir} && sudo ./install.sh")

def ssh_vm(config):
    vm_port = config["NETWORK"]["vm_port"]
    ssh_hosts_file = config["NETWORK"]["ssh_hosts_file"]
    vm_user = config["NETWORK"]["vm_user"]
    vm_host = config["NETWORK"]["vm_host"]
    run_command(f"ssh -p {vm_port} -o UserKnownHostsFile={ssh_hosts_file} {vm_user}@{vm_host}")


def clean(config):
    run_command(f"rm -rf {config['DIRECTORIES']['build']}")

def main():
    parser = argparse.ArgumentParser(description="Automation tool equivalent to the Makefile")
    parser.add_argument("target", choices=["init", "build_base_image", "build_guest_image", "run", "run_release",
                                           "setup_host", "attest_verity_vm", "ssh", "package_base", "package_guest",
                                             "clean", "build_content", "setup_vm_config", "get_hashes", "setup_verity"],
                        help="Target task to execute")
    parser.add_argument("--config", default="config/config.json", help="Path to the JSON configuration file")
    args = parser.parse_args()

    print(f"Config file: {args.config}")
    config = load_config(args.config)

    # Map target to function
    targets = {
        "init": init,
        "build_base_image": build_base_image,
        "build_guest_image": build_guest_image,
        "run": run_vm,
        "setup_host": setup_host,
        "ssh": ssh_vm,
        "clean": clean,

        "build_content": build_content,
        "setup_vm_config": setup_vm_config,
        "get_hashes": get_hashes,
        "setup_verity": setup_verity
    }

    task = targets.get(args.target)
    if task:
        task(config)
    else:
        print(f"Unknown target: {args.target}")
        sys.exit(1)

if __name__ == "__main__":
    main()
