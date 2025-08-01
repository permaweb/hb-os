import glob
import os
import re
import shutil
from typing import Optional, Dict, Any
from src.utils import run_command

def create_vm_config_file(out_path: str, ovmf_path: str, kernel_path: str, initrd_path: str, 
                         kernel_cmdline: str, vm_config: Dict[str, Any]) -> None:
    """
    Creates a new VM configuration file in the following format (without comments):

    host_cpu_family = "Milan"
    vcpu_count = 1
    ovmf_file = "<ovmf_path>"
    guest_features = 0x1
    kernel_file = "<kernel_path>"
    initrd_file = "<initrd_path>"
    kernel_cmdline = "<kernel_cmdline>"
    platform_info = 0x3
    guest_policy = 0x30000
    family_id = "00000000000000000000000000000000"
    image_id = "00000000000000000000000000000000"
    [min_commited_tcb]
    bootloader = 4
    tee = 0
    snp = 22
    microcode = 213
    _reserved = [0, 0, 0, 0]

    Parameters:
      out_path (str): Path to the output config file.
      ovmf_path (str): Path to the OVMF binary.
      kernel_path (str): Path to the kernel file.
      initrd_path (str): Path to the initrd file.
      kernel_cmdline (str): Kernel command-line parameters.
      vm_config (dict): Dictionary containing additional VM configuration options.
          Expected keys (with defaults):
            host_cpu_family: "Milan"
            vcpu_count: 1
            guest_features: "0x1"
            platform_info: "0x3"
            guest_policy: "0x30000"
            family_id: "00000000000000000000000000000000"
            image_id: "00000000000000000000000000000000"
            min_commited_tcb: dict with keys:
                bootloader: 4
                tee: 0
                snp: 22
                microcode: 213
                _reserved: [0, 0, 0, 0]
    """

    if "*" in kernel_path:
        matches = glob.glob(kernel_path)
        if matches:
            kernel_path = matches[0]
        else:
            print(f"Warning: No files found matching {kernel_path}")

    # If the kernel_cmdline contains a cat command referring to ${build_verity}, evaluate it.
    if "cat" in kernel_cmdline:
        match = re.search(r"verity_roothash='([^']+)'", kernel_cmdline)
        if match:
            cmd_str = match.group(1)
            try:
                result = run_command(cmd_str, capture_output=True)
                output = result.stdout.strip() if result.stdout else ""
            except Exception as e:
                output = ""
                print(f"Warning: command '{cmd_str}' failed with error: {e}")
            kernel_cmdline = re.sub(r"verity_roothash='[^']+'",
                                    f'verity_roothash={output}',
                                    kernel_cmdline)


    with open(out_path, "w") as f:
        f.write(f'host_cpu_family = "{vm_config.get("host_cpu_family", "Milan")}"\n')
        f.write(f'vcpu_count = {vm_config.get("vcpu_count", 1)}\n')
        f.write(f'ovmf_file = "{ovmf_path}"\n')
        f.write(f'guest_features = {vm_config.get("guest_features", "0x1")}\n')
        f.write(f'kernel_file = "{kernel_path}"\n')
        f.write(f'initrd_file = "{initrd_path}"\n')
        f.write(f'kernel_cmdline = "{kernel_cmdline}"\n')
        f.write(f'platform_info = {vm_config.get("platform_info", "0x3")}\n')
        f.write(f'guest_policy = {vm_config.get("guest_policy", "0x30000")}\n')
        f.write(f'family_id = "{vm_config.get("family_id", "00000000000000000000000000000000")}"\n')
        f.write(f'image_id = "{vm_config.get("image_id", "00000000000000000000000000000000")}"\n')
        f.write("[min_commited_tcb]\n")
        
        tcb = vm_config.get("min_committed_tcb", {})
        f.write(f"bootloader = {tcb.get('bootloader', 4)}\n")
        f.write(f"tee = {tcb.get('tee', 0)}\n")
        f.write(f"snp = {tcb.get('snp', 22)}\n")
        f.write(f"microcode = {tcb.get('microcode', 213)}\n")
        reserved_list = tcb.get('_reserved', [0, 0, 0, 0])
        f.write(f"_reserved = {reserved_list}\n")
    
    print(f"Written config to {out_path}")