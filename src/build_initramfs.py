#!/usr/bin/env python3
import os
import sys
import subprocess
import shutil
import argparse

def build_initramfs(kernel_dir, init_script, dockerfile, context_dir, build_dir, init_patch=None, out=None):
    """
    Build an initramfs image by exporting a Docker container filesystem,
    copying kernel modules, binaries, and an init script (optionally patching it),
    then repackaging the result.

    Parameters:
      kernel_dir (str): Path to the kernel directory. Must exist and contain a “lib” subdirectory.
      init_script (str): Path to the init script. Must exist.
      dockerfile (str): Path to the Dockerfile for the initramfs image.
      init_patch (str, optional): Path to a patch file for the init script. If provided and exists, it is applied.
      out (str, optional): Output file path for the generated initramfs image.
                           Defaults to "<build_dir>/initramfs.cpio.gz".
      build_dir (str, optional): Directory where all files will be written (default: "build").
    """

    # Validate required paths.
    if not os.path.isdir(kernel_dir):
        print(f"Error: Can't locate kernel modules directory '{kernel_dir}'")
        raise ValueError(f"Invalid kernel directory: {kernel_dir}")
    if not os.path.isfile(init_script):
        print(f"Error: Can't locate init script '{init_script}'")
        raise ValueError(f"Invalid init script: {init_script}")

    # Prepare the working directory.
    print("Preparing directories..")
    initrd_dir = os.path.join(build_dir, "initramfs")
    if os.path.exists(initrd_dir):
        shutil.rmtree(initrd_dir)
    os.makedirs(initrd_dir, exist_ok=True)

    # Build the Docker image.
    docker_img = "nano-vm-rootfs"
    print("Building Docker image..")

    # If dockerfile is a file (i.e. a Dockerfile), use its parent as context.
    if os.path.isfile(dockerfile):
        context_dir = os.path.dirname(dockerfile)
        dockerfile_arg = os.path.basename(dockerfile)

    # Save the current directory so we can return to it.
    old_dir = os.getcwd()
    os.chdir(context_dir)
    try:
        # Note: In the command below the build context is ".", because we already cd'ed.
        if dockerfile_arg:
            build_cmd = f"docker build -t {docker_img} -f {dockerfile_arg} ."
        print("Running command:", build_cmd)
        subprocess.run(build_cmd, shell=True, check=True)
    finally:
        os.chdir(old_dir)

    # Run the container (stop any previous container of the same name first).
    print("Running container..")
    subprocess.run(f"docker stop {docker_img}", shell=True, check=False)
    subprocess.run(f"docker run --rm -d --name {docker_img} {docker_img} sleep 3600",
                   shell=True, check=True)

    # Export the container’s filesystem into initrd_dir.
    print("Exporting filesystem..")
    subprocess.run(f"docker export {docker_img} | tar xpf - -C {initrd_dir}",
                   shell=True, check=True)

    # Copy kernel modules (assumes kernel_dir contains a "lib" directory).
    print("Copying kernel modules..")
    src_lib = os.path.join(kernel_dir, "lib")
    dest_usr = os.path.join(initrd_dir, "usr")
    os.makedirs(dest_usr, exist_ok=True)
    subprocess.run(f"cp -r {src_lib} {dest_usr}", shell=True, check=True)

    # Copy binaries from build_dir/bin into the container filesystem.
    print("Copying binaries..")
    src_bin = os.path.join(build_dir, "bin")
    subprocess.run(f"cp -r {src_bin} {dest_usr}", shell=True, check=True)

    # Copy the init script.
    print("Copying init script..")
    dest_init = os.path.join(initrd_dir, "init")
    shutil.copy2(init_script, dest_init)

    # If an init patch is provided (and exists), patch the init script.
    if init_patch is not None and os.path.isfile(init_patch):
        print("Patching init script..")
        # (Re-copy the original init script, if desired.)
        shutil.copy2(init_script, dest_init)
        subprocess.run(f"patch {dest_init} {init_patch}", shell=True, check=True)

    # Remove unnecessary files and directories.
    print("Removing unnecessary files and directories..")
    dirs_to_remove = ["dev", "proc", "sys", "boot", "home", "media", "mnt",
                        "opt", "root", "srv", "tmp", ".dockerenv"]
    for d in dirs_to_remove:
        path = os.path.join(initrd_dir, d)
        if os.path.exists(path):
            shutil.rmtree(path, ignore_errors=True)

    # Change permissions on binaries (clearing "s" permission bits).
    print("Changing permissions..")
    bin_usr = os.path.join(initrd_dir, "usr", "bin")
    subprocess.run(f"sudo chmod -st {bin_usr}/*", shell=True, check=False)

    # Repackage the initrd.
    print("Repackaging initrd..")
    # The command changes directory into initrd_dir, then creates a new cpio archive in newc format,
    # pipes it through pv (if installed) and gzip, and writes it to the output file.
    repack_cmd = f"(cd {initrd_dir} && find . -print0 | cpio --null -ov --format=newc 2>/dev/null | pv | gzip -1 > {out})"
    subprocess.run(repack_cmd, shell=True, check=True)

    # Clean up: stop the container.
    print("Cleaning up..")
    subprocess.run(f"docker stop {docker_img}", shell=True, check=False)

    print(f"Done! New initrd can be found at {out}")
