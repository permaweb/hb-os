# config/config.py
import os

config = {
    # Debugging and KVM.
    "debug": "0",
    "enable_kvm": "1",
    
    # Image Files.
    "base_image": "base.qcow2",
    "guest_image": "guest.qcow2",
    
    # Kernel Command Line.
    "cmdline": "console=ttyS0 earlyprintk=serial root=/dev/sda",
    
    # QEMU Parameters.
    "memory": "4096",
    "hb_port": "80",
    "qemu_port": "4444",
    
    # Guest Definition.
    "host_cpu_family": "Milan",
    "vcpu_count": 1,
    "guest_features": "0x1",
    "platform_info": "0x3",
    "guest_policy": "0x30000",
    "family_id": "00000000000000000000000000000000",
    "image_id": "00000000000000000000000000000000",
    "min_committed_tcb": {
        "bootloader": 4,
        "tee": 0,
        "snp": 22,
        "microcode": 213,
        "_reserved": [0, 0, 0, 0],
    }
}


class Directories:
    def __init__(self):
        # Compute the absolute base build directory.
        self.base = os.path.realpath(os.path.join(os.path.dirname(__file__), ".."))
        self.build = os.path.realpath("build")
        self.bin = os.path.join(self.build, "bin")
        self.content = os.path.join(self.build, "content")
        self.guest = os.path.join(self.build, "guest")
        self.kernel = os.path.join(self.build, "kernel")
        self.verity = os.path.join(self.build, "verity")
        self.snp = os.path.join(self.build, "snp-release")
        self.resources = os.path.realpath("resources")
        self.config = os.path.realpath("config")


class Config:
    def __init__(self):
        # Global flag from the config dictionary.
        self.debug = config["debug"]
        self.enable_kvm = config["enable_kvm"]

        # Build directories and resources.
        self.dir = Directories()

        # VM Image Base configuration.
        self.vm_image_base_name = config["base_image"]
        self.vm_image_base_path = os.path.join(self.dir.guest, self.vm_image_base_name)
        self.vm_cloud_config = os.path.join(self.dir.guest, "config-blob.img")
        self.vm_template_user_data = os.path.join(self.dir.config, "template-user-data")

        # Kernel configuration.
        self.kernel_deb = os.path.join(self.dir.snp, "linux", "guest", "linux-image-*.deb")
        self.kernel_vmlinuz = os.path.join(self.dir.kernel, "boot", "vmlinuz-*")
        self.ovmf = os.path.join(self.dir.snp, "usr", "local", "share", "qemu", "DIRECT_BOOT_OVMF.fd")
        self.cmdline = config["cmdline"]

        # Initramfs configuration.
        self.initrd = os.path.join(self.dir.build, "initramfs.cpio.gz")
        self.initramfs_script = os.path.join(self.dir.resources, "init.sh")
        self.initramfs_dockerfile = os.path.join(self.dir.resources, "initramfs.Dockerfile")

        # Content configuration.
        self.content_dockerfile = os.path.join(self.dir.resources, "content.Dockerfile")

        # Guest (VM) definition.
        self.host_cpu_family = config["host_cpu_family"]
        self.vcpu_count = config["vcpu_count"]
        self.guest_features = config["guest_features"]
        self.platform_info = config["platform_info"]
        self.guest_policy = config["guest_policy"]
        self.family_id = config["family_id"]
        self.image_id = config["image_id"]
        self.min_committed_tcb = config["min_committed_tcb"]

        # VM configuration.
        self.vm_config_file = os.path.join(self.dir.guest, "vm-config.toml")

        # Verity configuration.
        self.verity_image = os.path.join(self.dir.verity, config["guest_image"])
        self.verity_hash_tree = os.path.join(self.dir.verity, "hash_tree.bin")
        self.verity_root_hash = os.path.join(self.dir.verity, "roothash.txt")

        # Network configuration.
        self.network_vm_host = "localhost"
        self.network_vm_port = "2222"
        self.network_vm_user = "ubuntu"
        self.ssh_hosts_file = os.path.join(self.dir.build, "known_hosts")

        # QEMU configuration.
        self.qemu_launch_script = "./launch.sh"
        self.qemu_snp_params = "-sev-snp"
        self.qemu_memory = config["memory"]
        self.qemu_hb_port = config["hb_port"]
        self.qemu_port = config["qemu_port"]
        self.qemu_ovmf = self.ovmf
        self.qemu_build_dir = self.dir.build

        # QEMU parameters defined as variables.
        self.qemu_default_params = (
            f"-default-network -log {os.path.join(self.dir.build, 'stdout.log')} "
            f"-mem {self.qemu_memory} -smp {self.vcpu_count} "
        )
        self.qemu_extra_params = f"-bios {self.qemu_ovmf} -policy {self.guest_policy}"

    @property
    def verity_params(self):
        """
        Computes the verity parameters by reading the content of the root hash file.
        If the file does not exist or an error occurs, a placeholder value is used.
        """
        try:
            with open(self.verity_root_hash, "r") as f:
                roothash = f.read().strip()
        except Exception:
            roothash = "unknown"
        return f"boot=verity verity_disk=/dev/sdb verity_roothash={roothash}"


# Create a single instance to be used throughout your project.
config = Config()
