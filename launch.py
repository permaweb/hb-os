#!/usr/bin/env python3

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import getpass
from pathlib import Path
import socket
import glob

def ensure_root():
    """Check if script is running as root."""
    if os.geteuid() != 0:
        print("Must be run as root!")
        sys.exit(1)

def get_cbitpos():
    """Get C-bit position directly from the hardware."""
    subprocess.run(["modprobe", "cpuid"], check=True)
    
    # Read the CPUID info to get the C-bit position
    # This is equivalent to the complex dd/tail/od command chain in the bash script
    try:
        result = subprocess.run(
            ["dd", "if=/dev/cpu/0/cpuid", "ibs=16", "count=32", "skip=134217728"],
            capture_output=True, check=True
        )
        ebx_hex = subprocess.run(
            ["tail", "-c", "16"], 
            input=result.stdout, 
            capture_output=True, 
            check=True
        )
        ebx_formatted = subprocess.run(
            ["od", "-An", "-t", "u4", "-j", "4", "-N", "4"],
            input=ebx_hex.stdout,
            capture_output=True,
            check=True,
            text=True
        )
        ebx = int(ebx_formatted.stdout.strip())
        return ebx & 0x3f
    except subprocess.CalledProcessError as e:
        print(f"Error getting CBITPOS: {e}")
        sys.exit(1)

def add_opts(qemu_cmdline, *args):
    """Add options to the QEMU command line."""
    with open(qemu_cmdline, "a") as f:
        f.write(" ".join(args) + " ")

def parse_toml_value(key, file_path):
    """Parse a simple key=value from a TOML file."""
    try:
        result = subprocess.run(
            ["grep", "-Po", f"^\\s*{key}\\s*=\\s*(?:\\\"\\K[^\\\"]*(?=\\\")|\\\K[^\\\"\\s]+)", file_path],
            capture_output=True, check=True, text=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return ""

def find_uefi_vars(base_path):
    """Search for UEFI variable file in multiple potential locations."""
    potential_paths = [
        os.path.join(base_path, "OVMF_VARS.fd"),
        os.path.join(base_path, "usr", "local", "share", "qemu", "OVMF_VARS.fd"),
        os.path.join(base_path, "share", "qemu", "OVMF_VARS.fd"),
        os.path.join("/usr", "share", "OVMF", "OVMF_VARS.fd"),
        os.path.join("/usr", "share", "edk2", "ovmf", "OVMF_VARS.fd"),
    ]
    
    for path in potential_paths:
        if os.path.exists(path):
            return path
    
    return None

def run_ssh_command(cmd, password, connection_timeout=60, host="localhost", port=2222, user="hb"):
    """Run an SSH command with password if provided."""
    ssh_cmd = ["sshpass", "-p", password, "ssh", "-t", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=" + str(connection_timeout), 
                "-o", "UserKnownHostsFile=/dev/null", "-p", str(port), f"{user}@{host}", cmd]

    try:
        subprocess.run(ssh_cmd, timeout=connection_timeout)
        return True
    except Exception as e:
        print(f"SSH command failed: {str(e)}")
        return False

def copy_files_to_vm(local_path, remote_path, password, connection_timeout=60, host="localhost", port=2222, user="hb"):
    """Copy files to VM using SCP with password if provided."""
    # Expand the wildcard pattern to get actual file paths
    full_path = os.path.join(os.getcwd(), local_path)
    matching_files = glob.glob(full_path)
    
    if not matching_files:
        print(f"Warning: No files match the pattern '{full_path}'")
        return False
    
    print(f"Found {len(matching_files)} files matching {local_path}:")
    for file in matching_files:
        print(f"  - {os.path.basename(file)}")
    
    # Copy each file individually
    for file_path in matching_files:
        print(f"Copying {file_path} to {remote_path}")
        scp_cmd = ["sshpass", "-p", password, "scp", "-o", "StrictHostKeyChecking=no", 
                  "-o", f"ConnectTimeout={connection_timeout}", 
                  "-o", "UserKnownHostsFile=/dev/null", "-P", str(port), 
                  file_path, f"{user}@{host}:{remote_path}"]
        
        try:
            subprocess.run(scp_cmd, timeout=connection_timeout)
        except Exception as e:
            print(f"SCP failed for {file_path}: {str(e)}")
            return False
    
    return True

def run_setup_with_sudo(password, host="localhost", port=2222, user="hb", connection_timeout=60):
    """Setup sudo and run commands with elevated privileges"""
    
    # First, set up passwordless sudo for the user
    setup_sudo_cmd = f"echo '{password}' | sudo -S bash -c \"echo '{user} ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/{user}\""
    
    ssh_cmd = [
        "sshpass", "-p", password, "ssh", 
        "-o", "StrictHostKeyChecking=no", 
        "-o", f"ConnectTimeout={connection_timeout}", 
        "-o", "UserKnownHostsFile=/dev/null", 
        "-p", str(port), f"{user}@{host}", 
        setup_sudo_cmd
    ]
    
    try:
        subprocess.run(ssh_cmd, timeout=connection_timeout)
        print("Passwordless sudo set up successfully")
        
        # Now run the actual setup commands without password prompt
        setup_cmd = (
            "sudo curl -fsSL https://deb.nodesource.com/setup_22.x | sudo bash - && "
            "sudo apt-get install -y nodejs && node -v && npm -v && "
            "sudo dpkg -i linux-*.deb && rm -rf linux-*.deb && "
            "sudo systemctl disable multipathd.service && sudo shutdown now"
        )
        
        run_ssh_command(setup_cmd, password, connection_timeout, host, port, user)
        return True
        
    except Exception as e:
        print(f"Setup failed: {str(e)}")
        return False

def main():
    # Set default values
    hda = ""
    hdb = ""
    mem = "2048"
    smp = "1"
    console = "serial"
    use_virtio = "1"
    discard = "none"
    use_default_network = "1"
    cpu_model = "EPYC-v4"
    monitor_path = "monitor"
    qemu_console_log = os.path.join(os.getcwd(), "stdout.log")
    certs_path = ""
    enable_id_block = ""

    sev = False
    sev_es = False
    sev_snp = False
    use_gdb = False

    sev_toolchain_path = "build/snp-release/usr/local"
    uefi_path = os.path.join(sev_toolchain_path, "share", "qemu")
    uefi_code = ""
    uefi_vars = ""

    json_file = "./inputs.json"
    ssh_user = "hb"  # Default SSH username
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Launch a QEMU VM with AMD SEV options")
    
    parser.add_argument("-sev", action="store_true", help="Launch SEV guest")
    parser.add_argument("-sev-es", action="store_true", help="Launch SEV-ES guest")
    parser.add_argument("-sev-snp", action="store_true", help="Launch SEV-SNP guest")
    parser.add_argument("-enable-discard", action="store_true", help="For SNP, discard memory after conversion")
    parser.add_argument("-bios", help="The bios to use")
    parser.add_argument("-hda", help="Hard disk file")
    parser.add_argument("-hdb", help="Second hard disk file for cloud-init config blob")
    parser.add_argument("-mem", help="Guest memory size in MB")
    parser.add_argument("-smp", help="Number of virtual CPUs")
    parser.add_argument("-cpu", help="QEMU CPU model/type to use")
    parser.add_argument("-kernel", help="Kernel to use")
    parser.add_argument("-initrd", help="Initrd to use")
    parser.add_argument("-append", help="Kernel command line arguments")
    parser.add_argument("-cdrom", help="CDROM image")
    parser.add_argument("-default-network", action="store_true", help="Enable default usermode networking")
    parser.add_argument("-monitor", help="Path to QEMU monitor socket")
    parser.add_argument("-log", help="Path to QEMU console log")
    parser.add_argument("-certs", help="Path to SNP certificate blob for guest")
    parser.add_argument("-id-block", help="Path to file with 96-byte ID Block")
    parser.add_argument("-id-auth", help="Path to file with 4096-byte ID Authentication Information")
    parser.add_argument("-host-data", help="Path to file with 32-byte HOST_DATA")
    parser.add_argument("-policy", help="Guest Policy (0x prefixed string)")
    parser.add_argument("-load-config", help="Load config from a TOML file")
    parser.add_argument("-hb-port", default="8734", help="Port for HyperBeam")
    parser.add_argument("-qemu-port", default="4444", help="Port for QEMU monitor")
    parser.add_argument("-debug", help="Enable debug mode")
    parser.add_argument("-data-disk", help="Path to the additional data volume")
    parser.add_argument("-enable-kvm", help="Enable KVM")
    parser.add_argument("-ssh-user", help="SSH username (default: hb)")
    
    args = parser.parse_args()
    
    # Set variables from command line arguments
    if args.sev_snp:
        sev_snp = True
        sev_es = True
        sev = True
    
    if args.sev_es:
        sev_es = True
        sev = True
    
    if args.sev:
        sev = True
    
    if args.enable_discard:
        discard = "both"
    
    if args.hda:
        hda = os.path.abspath(args.hda)
        if not os.path.exists(hda) and not args.kernel:
            print(f"Can't locate guest image file [{args.hda}]. Either specify image file or direct boot kernel")
            sys.exit(1)
        guest_name = os.path.basename(hda).rsplit(".", 1)[0]
    else:
        guest_name = ""
    
    if args.hdb:
        hdb = os.path.abspath(args.hdb)
    
    if args.mem:
        mem = args.mem
    
    if args.smp:
        smp = args.smp
    
    if args.cpu:
        cpu_model = args.cpu
    
    if args.bios:
        uefi_code = os.path.abspath(args.bios)
    
    kernel_file = args.kernel if args.kernel else ""
    initrd_file = args.initrd if args.initrd else ""
    append = args.append if args.append else ""
    
    if args.cdrom:
        cdrom_file = os.path.abspath(args.cdrom)
        if not os.path.exists(cdrom_file):
            print(f"Can't locate CD-Rom file [{args.cdrom}]")
            sys.exit(1)
        
        if not guest_name:
            guest_name = os.path.basename(cdrom_file).rsplit(".", 1)[0]
    else:
        cdrom_file = ""
    
    if args.monitor:
        monitor_path = args.monitor
    
    if args.log:
        qemu_console_log = args.log
    
    if args.certs:
        certs_path = args.certs
    
    if args.ssh_user:
        ssh_user = args.ssh_user
    
    hb_port = args.hb_port
    qemu_port = args.qemu_port
    data_disk = args.data_disk
    sev_policy = args.policy
    
    # Ask for SSH password
    try:
        ssh_password = getpass.getpass(f"Enter SSH password for {ssh_user} (leave empty for no password): ")
        if not ssh_password.strip():
            ssh_password = None
            print("No password provided, will use key-based authentication")
    except (KeyboardInterrupt, EOFError):
        print("\nPassword input canceled")
        ssh_password = None
    
    # Check if sshpass is installed if password is provided
    if ssh_password:
        try:
            subprocess.run(["which", "sshpass"], capture_output=True, check=True)
        except subprocess.CalledProcessError:
            print("Warning: Password provided but 'sshpass' is not installed.")
            print("Please install sshpass package, or password authentication won't work.")
            print("Continuing without password authentication...")
            ssh_password = None
    
    # Handle TOML config loading
    toml_config = args.load_config
    if toml_config and os.path.exists(toml_config):
        print("Parsing config options from file")
        
        if not args.smp:
            smp = parse_toml_value("vcpu_count", toml_config) or smp
        
        if not uefi_code:
            uefi_code = parse_toml_value("ovmf_file", toml_config) or uefi_code
        
        if not kernel_file:
            kernel_file = parse_toml_value("kernel_file", toml_config) or kernel_file
        
        if not initrd_file:
            initrd_file = parse_toml_value("initrd_file", toml_config) or initrd_file
        
        if not append:
            append = parse_toml_value("kernel_cmdline", toml_config) or append
        
        if not sev_policy:
            sev_policy = parse_toml_value("guest_policy", toml_config) or sev_policy
    
    # Logic for ID block and auth block
    use_id_and_auth = False
    if args.id_block and args.id_auth:
        use_id_and_auth = True
    elif args.id_block or args.id_auth:
        print("-id-block and -auth-block must either both be set or both unset")
        sys.exit(1)
    
    # Locate QEMU executable
    qemu_tmp = os.path.join(sev_toolchain_path, "bin", "qemu-system-x86_64")
    qemu_exe = os.path.realpath(qemu_tmp) if os.path.exists(qemu_tmp) else ""
    if not qemu_exe:
        print(f"Can't locate qemu executable [{qemu_tmp}]")
        sys.exit(1)
    
    # UEFI code and vars handling
    if not uefi_code:
        uefi_tmp = os.path.join(uefi_path, "OVMF_CODE.fd")
        if os.path.exists(uefi_tmp):
            uefi_code = os.path.realpath(uefi_tmp)
        else:
            print(f"Can't locate UEFI code file [{uefi_tmp}]")
            sys.exit(1)
    
    # Try to find the guest-specific UEFI vars file first
    if guest_name and os.path.exists(f"./{guest_name}.fd"):
        uefi_vars = os.path.realpath(f"./{guest_name}.fd")
    else:
        # If guest-specific vars file doesn't exist, look for a standard one 
        # and create a guest-specific copy
        uefi_vars_file = find_uefi_vars(os.path.dirname(uefi_code))
        
        if uefi_vars_file:
            uefi_vars = os.path.realpath(uefi_vars_file)
            if guest_name:  # Only make a copy if we have a guest name
                try:
                    shutil.copy(uefi_vars, f"./{guest_name}.fd")
                    uefi_vars = os.path.realpath(f"./{guest_name}.fd")
                except:
                    # Keep using the original if copy fails
                    print(f"Warning: Could not create custom UEFI vars file for {guest_name}")
        elif not sev_snp:
            # For SEV-SNP, the vars file might not be mandatory
            print(f"Warning: Could not find UEFI variable file")
            # Try to create an empty vars file as a fallback
            if guest_name:
                with open(f"./{guest_name}.fd", "wb") as f:
                    f.write(b"\x00" * 1024 * 1024)  # 1MB empty file
                uefi_vars = os.path.realpath(f"./{guest_name}.fd")
                print(f"Created empty UEFI vars file at ./{guest_name}.fd")
            else:
                # For non-SEV-SNP mode, this is a fatal error
                print(f"Error: UEFI variable file required.")
                sys.exit(1)
    
    # Debug settings
    if args.debug == "1":
        # This will dump all the VMCB on VM exit
        try:
            with open("/sys/module/kvm_amd/parameters/dump_all_vmcbs", "w") as f:
                f.write("1\n")
        except:
            print("Warning: Could not enable VMCB dumping (this might be normal if KVM module is not loaded)")
    
    # Create QEMU command line file
    qemu_cmdline = f"/tmp/cmdline.{os.getpid()}"
    if os.path.exists(qemu_cmdline):
        os.unlink(qemu_cmdline)
    
    # Build QEMU command line
    add_opts(qemu_cmdline, qemu_exe)
    
    # Basic virtual machine property
    if args.enable_kvm == "1":
        add_opts(qemu_cmdline, f"-enable-kvm -cpu {cpu_model} -machine q35")
    else:
        add_opts(qemu_cmdline, f"-cpu {cpu_model} -machine q35")
    
    # Add number of VCPUs
    if smp:
        add_opts(qemu_cmdline, f"-smp {smp},maxcpus=255")
    
    # Define guest memory
    add_opts(qemu_cmdline, f"-m {mem}M")
    
    # Don't reboot for SEV-ES guest
    add_opts(qemu_cmdline, "-no-reboot")
    
    # OVMF binary handling
    if sev_snp:
        add_opts(qemu_cmdline, f"-bios {uefi_code}")
        if uefi_vars:
            add_opts(qemu_cmdline, f"-drive if=pflash,format=raw,unit=0,file={uefi_vars}")
    else:
        add_opts(qemu_cmdline, f"-drive if=pflash,format=raw,unit=0,file={uefi_code},readonly")
        if uefi_vars:
            add_opts(qemu_cmdline, f"-drive if=pflash,format=raw,unit=1,file={uefi_vars}")
    
    # Add CDROM if specified
    if cdrom_file:
        add_opts(qemu_cmdline, f"-drive file={cdrom_file},media=cdrom -boot d")
    
    # Networking
    if use_default_network == "1" or args.default_network:
        add_opts(qemu_cmdline, f" -netdev user,id=vmnic,hostfwd=tcp:127.0.0.1:2222-:22,hostfwd=tcp:0.0.0.0:8734-:8734,hostfwd=tcp:0.0.0.0:{hb_port}-:10000")
        add_opts(qemu_cmdline, " -device virtio-net-pci,disable-legacy=on,iommu_platform=true,netdev=vmnic,romfile=")
    
    # Disk handling
    disks = [hda, hdb]
    for i, disk in enumerate(disks):
        if disk:
            if use_virtio == "1":
                if disk.endswith("qcow2"):
                    add_opts(qemu_cmdline, f"-drive file={disk},if=none,id=disk{i},format=qcow2")
                else:
                    add_opts(qemu_cmdline, f"-drive file={disk},if=none,id=disk{i},format=raw")
                
                add_opts(qemu_cmdline, f"-device virtio-scsi-pci,id=scsi{i},disable-legacy=on,iommu_platform=true")
                add_opts(qemu_cmdline, f"-device scsi-hd,drive=disk{i},bootindex={i+1}")
            else:
                if disk.endswith("qcow2"):
                    add_opts(qemu_cmdline, f"-drive file={disk},format=qcow2")
                else:
                    add_opts(qemu_cmdline, f"-drive file={disk},format=raw")
    
    # SEV support
    if sev:
        add_opts(qemu_cmdline, "-machine memory-encryption=sev0,vmport=off")
        cbitpos = get_cbitpos()
        
        if not sev_policy:
            print("-policy argument is mandatory")
            sys.exit(1)
        
        if not sev_policy.startswith("0x"):
            print("string passed to -policy must start with 0x")
            sys.exit(1)
        
        if sev_snp:
            add_opts(qemu_cmdline, f"-object memory-backend-memfd,id=ram1,size={mem}M,share=true,prealloc=false")
            add_opts(qemu_cmdline, "-machine memory-backend=ram1")
            
            snp_opts = f"-object sev-snp-guest,id=sev0,policy={sev_policy},cbitpos={cbitpos},reduced-phys-bits=1"
            
            if certs_path:
                snp_opts += f",certs-path={certs_path}"
            
            if use_id_and_auth:
                with open(args.id_block, 'r') as f:
                    id_block_content = f.read().strip()
                with open(args.id_auth, 'r') as f:
                    id_auth_content = f.read().strip()
                snp_opts += f",id-block={id_block_content},id-auth={id_auth_content},auth-key-enabled=true"
            
            if args.host_data:
                with open(args.host_data, 'r') as f:
                    host_data_content = f.read().strip()
                snp_opts += f",host-data={host_data_content}"
            
            if kernel_file and initrd_file:
                snp_opts += ",kernel-hashes=on"
            
            add_opts(qemu_cmdline, snp_opts)
        else:
            add_opts(qemu_cmdline, f"-object sev-guest,id=sev0,policy={sev_policy},cbitpos={cbitpos},reduced-phys-bits=1")
    
    # Kernel, initrd, and append
    if kernel_file:
        add_opts(qemu_cmdline, f"-kernel {kernel_file}")
        if append:
            add_opts(qemu_cmdline, f'-append "{append}"')
        if initrd_file:
            add_opts(qemu_cmdline, f"-initrd {initrd_file}")
    
    # Console
    if console == "serial":
        add_opts(qemu_cmdline, "-nographic")
    else:
        add_opts(qemu_cmdline, f"-vga {console}")
    
    # Monitor
    add_opts(qemu_cmdline, f"-monitor pty -monitor unix:{monitor_path},server,nowait")
    add_opts(qemu_cmdline, f"-qmp tcp:localhost:{qemu_port},server,wait=off")
    
    # Data disk handling
    if data_disk:
        data_disk = os.path.abspath(data_disk)
        if not os.path.exists(data_disk):
            print(f"Can't locate data volume file [{data_disk}]")
            sys.exit(1)
        
        add_opts(qemu_cmdline, f"-drive file={data_disk},if=none,id=dataDisk,format=qcow2")
        add_opts(qemu_cmdline, "-device virtio-scsi-pci,id=scsi_data,disable-legacy=on,iommu_platform=true")
        add_opts(qemu_cmdline, "-device scsi-hd,drive=dataDisk")
    
    # Save the command line args into log file
    with open(qemu_cmdline, 'r') as f:
        cmd_content = f.read()
    
    with open(qemu_console_log, 'w') as f:
        f.write(cmd_content + "\n\n")
    
    print(cmd_content)
    
    # Disable transparent huge pages
    print("Disabling transparent huge pages")
    try:
        with open("/sys/kernel/mm/transparent_hugepage/enabled", "w") as f:
            f.write("never")
    except:
        print("Warning: Could not disable transparent huge pages (this might be normal on some systems)")
    
    # Launch QEMU
    if toml_config:
        print("Launching QEMU as a background service...")
        
        # Run the QEMU command
        with open(qemu_cmdline, 'r') as f:
            cmd = f.read()
        
        proc = subprocess.Popen(
            cmd, 
            shell=True,
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT,
            start_new_session=True  # This detaches the process
        )
        
        if args.debug == "0":
            print("Waiting for QEMU to start...")
            time.sleep(5)
            
            # Check if guest is ready
            attempt = 1
            max_attempts = 10
            
            while attempt <= max_attempts:
                print(f"Attempt {attempt}: Sending GET request to http://localhost:{hb_port}/~meta@1.0/info to check if Guest is ready...")
                
                try:
                    curl_result = subprocess.run(
                        ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", f"http://localhost:{hb_port}/~meta@1.0/info"],
                        capture_output=True, text=True, check=True
                    )
                    response = int(curl_result.stdout.strip())
                    
                    if response == 200:
                        print("Received 200 response. Proceeding to send POST request...")
                        break
                    else:
                        print(f"Received {response} response. Retrying in 5 seconds...")
                except:
                    print("Failed to connect. Retrying in 5 seconds...")
                
                time.sleep(5)
                attempt += 1
            
            if attempt > max_attempts:
                print("Max attempts reached. Guest is not ready.")
                os.unlink(qemu_cmdline)
                sys.exit(1)
            
            # Process JSON file
            if os.path.exists(json_file):
                try:
                    with open(json_file, 'r') as f:
                        json_data = json.load(f)
                    
                    # Remove expected_hash from the wrapped JSON
                    wrapped_json = {"snp_hashes": {k: v for k, v in json_data.items() if k != "expected_hash"}}
                    
                    # Send POST request
                    subprocess.run(
                        ["curl", "-X", "POST", "-H", "Content-Type: application/json", 
                         "-d", json.dumps(wrapped_json), f"http://localhost:{hb_port}/~snp@1.0/init"],
                        check=True
                    )
                    
                    # Print final configuration
                    print("Final configuration:")
                    fields = ["kernel", "initrd", "append", "firmware", "vcpus", 
                             "vcpu_type", "vmm_type", "guest_features", "expected_hash"]
                    config_output = {k: json_data.get(k) for k in fields if k in json_data}
                    print(json.dumps(config_output, indent=4))
                    
                except Exception as e:
                    print(f"Error processing JSON file: {e}")
    else:
        print("Launching VM normally...")
        print(f"  {qemu_cmdline}")
        print("Launching QEMU as a background service...")
        
        # Run the QEMU command
        with open(qemu_cmdline, 'r') as f:
            cmd = f.read()
        
        proc = subprocess.Popen(
            cmd, 
            shell=True,
            stdout=open(qemu_console_log, 'a'),
            stderr=subprocess.STDOUT,
            start_new_session=True  # This detaches the process from parent
        )
        # Don't wait for the process to complete
        print(f"QEMU started as background process with PID: {proc.pid}")
        print(f"Console output being logged to: {qemu_console_log}")
                
        # Wait for SSH to become available
        time.sleep(5)
        
        # SSH commands - use our helper functions with password
        subprocess.run(["ssh-keygen", "-f", "~/.ssh/known_hosts", "-R", "[localhost]:2222"])
        
        # Copy package files to VM
        copy_files_to_vm(
            "build/snp-release/linux/guest/*.deb", 
            ".", 
            ssh_password,
            connection_timeout=500,
            host="localhost",
            port=2222,
            user=ssh_user,
        )
        
        # Run setup commands
        run_setup_with_sudo(
            ssh_password, 
            host="localhost", 
            port=2222, 
            user=ssh_user, 
            connection_timeout=500)
    
    # Clean up
    if os.path.exists(qemu_cmdline):
        os.unlink(qemu_cmdline)

if __name__ == "__main__":
    # Check if running as root
    ensure_root()
    main() 