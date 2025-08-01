#!/usr/bin/env python3
"""
Build orchestration functionality moved from the run script.
Contains the exact same functions without modifications.
"""

import os
from typing import Optional
from config import config
from .create_new_vm import create_vm_image
from .build_initramfs import build_initramfs
from .build_content import build_guest_content
from .create_vm_config import create_vm_config_file
from .setup_guest import setup_guest
from src.utils import run_command, QEMUCommandBuilder


def create_vm() -> None:
    """
    Create a new virtual machine image using the provided template.
    """
    guest_dir = config.dir.guest
    image_name = config.vm_image_base_name
    template_user_data = config.vm_template_user_data
    create_vm_image(
        new_vm=image_name, build_dir=guest_dir, template_user_data=template_user_data
    )


def unpack_kernel() -> None:
    """
    Unpack the kernel package from a .deb file.
    """
    kernel_dir = config.dir.kernel
    kernel_deb = config.kernel_deb
    run_command(f"rm -rf {kernel_dir}")
    run_command(f"dpkg -x {kernel_deb} {kernel_dir}")


def initramfs_build() -> None:
    """
    Build the initramfs image using the provided script and Dockerfile.
    """
    build_dir = config.dir.build
    resource_dir = config.dir.resources
    kernel_dir = config.dir.kernel
    init_script = config.initramfs_script
    initrd = config.initrd
    dockerfile = config.initramfs_dockerfile

    build_initramfs(
        kernel_dir=kernel_dir,
        init_script=init_script,
        dockerfile=dockerfile,
        context_dir=resource_dir,
        out=initrd,
        build_dir=build_dir,
    )


def setup_vm_config() -> None:
    """
    Create the virtual machine configuration file with the required parameters.
    """
    # Build a guest definition dictionary from the flattened config.
    vm_config_definition = {
        "host_cpu_family": config.host_cpu_family,
        "vcpu_count": config.vcpu_count,
        "guest_features": config.guest_features,
        "platform_info": config.platform_info,
        "guest_policy": config.guest_policy,
        "family_id": config.family_id,
        "image_id": config.image_id,
        "min_committed_tcb": config.min_committed_tcb,
    }
    create_vm_config_file(
        out_path=config.vm_config_file,
        ovmf_path=config.ovmf,
        kernel_path=config.kernel_vmlinuz,
        initrd_path=config.initrd,
        kernel_cmdline=f"{config.cmdline} {config.verity_params}",
        vm_config=vm_config_definition,
    )


def get_hashes() -> None:
    """
    Generate measurement inputs (hashes) from the VM configuration.
    """
    digest_calc_path = os.path.join(config.dir.bin, "digest_calc")
    out_file = os.path.join(os.getcwd(), "inputs.json")
    run_command(
        f"{digest_calc_path} --vm-definition {config.vm_config_file} > {out_file}"
    )


def build_base_image() -> None:
    """
    Build the base VM image by:
      1. Unpacking the kernel.
      2. Building the initramfs.
      3. Creating the VM image.
      4. Running QEMU setup.
    """
    print("===> Building base image")
    unpack_kernel()
    initramfs_build()
    create_vm()
    run_setup()


def build_guest_image() -> None:
    """
    Build the guest image by:
      1. Building guest content.
      2. Setting up verity.
      3. Creating VM configuration.
      4. Generating hash measurements.
    """
    print("===> Building guest image")
    build_content()
    setup_verity()
    setup_vm_config()
    get_hashes()


def build_content() -> None:
    """
    Build the guest content using the provided Dockerfile.
    """
    build_guest_content(
        out_dir=config.dir.content, 
        dockerfile=config.content_dockerfile, 
        hb_branch=config.hb_branch,
        ao_branch=config.ao_branch
    )


def setup_verity() -> None:
    """
    Set up verity by running the verity setup shell script.
    """
    setup_guest(
        src_image=config.vm_image_base_path,
        build_dir=config.dir.build,
        out_image=config.verity_image,
        out_hash_tree=config.verity_hash_tree,
        out_root_hash=config.verity_root_hash,
        debug=config.debug,
    )


def run_setup() -> None:
    """
    Run QEMU with the base image configuration.
    """
    cmd = (QEMUCommandBuilder(config.qemu_launch_script)
           .args(*config.qemu_default_params.split())
           .args(*config.qemu_extra_params.split())
           .hda(config.vm_image_base_path)
           .hdb(config.vm_cloud_config)
           .hb_port(config.qemu_hb_port)
           .qemu_port(config.qemu_port)
           .debug(config.debug)
           .enable_kvm(config.enable_kvm)
           .enable_tpm(config.enable_tpm)
           .build())
    
    run_command(cmd)