#!/usr/bin/env python3
import os
import sys
import argparse
from typing import Optional
from pathlib import Path
from src.utils import (
    run_command, run_command_silent, ensure_directory, remove_directory,
    CommandBuilder
)
from src.services import docker_service


def validate_initramfs_inputs(kernel_dir: str, init_script: str) -> None:
    """
    Validate required input paths for initramfs build.
    
    Args:
        kernel_dir: Path to the kernel directory
        init_script: Path to the init script
        
    Raises:
        ValueError: If any required path is invalid
    """
    if not os.path.isdir(kernel_dir):
        print(f"Error: Can't locate kernel modules directory '{kernel_dir}'")
        raise ValueError(f"Invalid kernel directory: {kernel_dir}")
    if not os.path.isfile(init_script):
        print(f"Error: Can't locate init script '{init_script}'")
        raise ValueError(f"Invalid init script: {init_script}")


def prepare_initramfs_directories(build_dir: str) -> str:
    """
    Prepare working directories for initramfs build.
    
    Args:
        build_dir: Base build directory
        
    Returns:
        Path to the initramfs working directory
    """
    print("Preparing directories..")
    initrd_dir = os.path.join(build_dir, "initramfs")
    remove_directory(initrd_dir)
    ensure_directory(initrd_dir)
    return initrd_dir


def build_and_export_container(dockerfile: str, context_dir: str) -> str:
    """
    Build Docker image and export container filesystem.
    
    Args:
        dockerfile: Path to the Dockerfile
        context_dir: Build context directory
        
    Returns:
        Container name for further processing
    """
    docker_img = "nano-vm-rootfs"
    container_name = "nano-vm-rootfs"
    print("Building Docker image..")

    # If dockerfile is a file (i.e. a Dockerfile), use its parent as context.
    if os.path.isfile(dockerfile):
        context_dir = os.path.dirname(dockerfile)
        dockerfile_arg = os.path.basename(dockerfile)

    # Build Docker image using Docker service
    docker_service.build_image(context_dir, dockerfile_arg, docker_img)

    # Run container
    container = docker_service.run_container(docker_img, container_name)
    
    return container_name


def copy_initramfs_components(kernel_dir: str, build_dir: str, init_script: str, 
                            init_patch: Optional[str], initrd_dir: str) -> None:
    """
    Copy kernel modules, binaries, and init script to the initramfs directory.
    
    Args:
        kernel_dir: Path to kernel directory containing modules
        build_dir: Build directory containing binaries
        init_script: Path to init script
        init_patch: Path to init patch file (optional)
        initrd_dir: Target initramfs directory
    """
    # Copy kernel modules (assumes kernel_dir contains a "lib" directory).
    print("Copying kernel modules..")
    src_lib = os.path.join(kernel_dir, "lib")
    dest_usr = os.path.join(initrd_dir, "usr")
    ensure_directory(dest_usr)
    run_command(f"cp -r {src_lib} {dest_usr}")

    # Copy binaries from build_dir/bin into the container filesystem.
    print("Copying binaries..")
    src_bin = os.path.join(build_dir, "bin")
    run_command(f"cp -r {src_bin} {dest_usr}")

    # Copy the init script.
    print("Copying init script..")
    dest_init = os.path.join(initrd_dir, "init")
    import shutil
    shutil.copy2(init_script, dest_init)

    # If an init patch is provided (and exists), patch the init script.
    if init_patch is not None and os.path.isfile(init_patch):
        print("Patching init script..")
        # Re-copy the original init script first
        shutil.copy2(init_script, dest_init)
        run_command(f"patch {dest_init} {init_patch}")


def cleanup_initramfs_filesystem(initrd_dir: str) -> None:
    """
    Remove unnecessary files and fix permissions in the initramfs filesystem.
    
    Args:
        initrd_dir: Path to the initramfs directory
    """
    # Remove unnecessary files and directories.
    print("Removing unnecessary files and directories..")
    dirs_to_remove = ["dev", "proc", "sys", "boot", "home", "media", "mnt",
                        "opt", "root", "srv", "tmp"]
    files_to_remove = [".dockerenv"]
    
    # Remove directories
    for d in dirs_to_remove:
        path = os.path.join(initrd_dir, d)
        if os.path.exists(path):
            remove_directory(path)
    
    # Remove files
    for f in files_to_remove:
        path = os.path.join(initrd_dir, f)
        if os.path.exists(path):
            print(f"  🗑️  Removing file: {f}")
            os.remove(path)

    # Change permissions on binaries (clearing "s" permission bits).
    print("Changing permissions..")
    bin_usr = os.path.join(initrd_dir, "usr", "bin")
    run_command_silent(f"sudo chmod -st {bin_usr}/*")


def create_initramfs_archive(initrd_dir: str, output_path: str) -> None:
    """
    Create the final initramfs archive from the prepared filesystem.
    
    Args:
        initrd_dir: Path to the prepared initramfs directory
        output_path: Path for the output archive
    """
    print("Repackaging initrd..")
    # Create a cpio archive in newc format, pipe through pv and gzip
    repack_cmd = (f"(cd {initrd_dir} && " +
                  CommandBuilder("find", ".")
                  .arg("-print0")
                  .pipe("cpio", "--null", "-ov", "--format=newc", "2>/dev/null")
                  .pipe("pv")
                  .pipe("gzip", "-1")
                  .build() +
                  f" > {output_path})")
    run_command(repack_cmd)


def build_initramfs(kernel_dir: str, init_script: str, dockerfile: str, context_dir: str, 
                   build_dir: str, init_patch: Optional[str] = None, out: Optional[str] = None) -> None:
    """
    Build an initramfs image by exporting a Docker container filesystem,
    copying kernel modules, binaries, and an init script (optionally patching it),
    then repackaging the result.

    This function coordinates the entire initramfs build process:
    1. Validate inputs
    2. Prepare directories  
    3. Build and export Docker container
    4. Copy components (kernel modules, binaries, init script)
    5. Clean up filesystem
    6. Create final archive
    7. Clean up resources

    Parameters:
      kernel_dir (str): Path to the kernel directory. Must exist and contain a "lib" subdirectory.
      init_script (str): Path to the init script. Must exist.
      dockerfile (str): Path to the Dockerfile for the initramfs image.
      context_dir (str): Build context directory (usually dockerfile parent)
      build_dir (str): Directory where all files will be written
      init_patch (str, optional): Path to a patch file for the init script. If provided and exists, it is applied.
      out (str, optional): Output file path for the generated initramfs image.
                           Defaults to "<build_dir>/initramfs.cpio.gz".
                           
    Raises:
        ValueError: If required input paths are invalid
        DockerError: If Docker operations fail
        CommandExecutionError: If shell commands fail
    """
    # Validate input arguments
    if not kernel_dir or not isinstance(kernel_dir, str):
        raise ValueError("kernel_dir must be a non-empty string")
    if not init_script or not isinstance(init_script, str):
        raise ValueError("init_script must be a non-empty string")
    if not dockerfile or not isinstance(dockerfile, str):
        raise ValueError("dockerfile must be a non-empty string")
    if not context_dir or not isinstance(context_dir, str):
        raise ValueError("context_dir must be a non-empty string")
    if not build_dir or not isinstance(build_dir, str):
        raise ValueError("build_dir must be a non-empty string")
    
    # Set default output path if not provided
    if out is None:
        out = os.path.join(build_dir, "initramfs.cpio.gz")

    # Step 1: Validate inputs
    validate_initramfs_inputs(kernel_dir, init_script)

    # Step 2: Prepare directories
    initrd_dir = prepare_initramfs_directories(build_dir)

    # Step 3: Build and export Docker container
    container_name = build_and_export_container(dockerfile, context_dir)

    try:
        # Export the container's filesystem into initrd_dir
        print("Exporting filesystem..")
        docker_service.export_filesystem(container_name, initrd_dir)

        # Step 4: Copy components
        copy_initramfs_components(kernel_dir, build_dir, init_script, init_patch, initrd_dir)

        # Step 5: Clean up filesystem
        cleanup_initramfs_filesystem(initrd_dir)

        # Step 6: Create final archive
        create_initramfs_archive(initrd_dir, out)

    finally:
        # Step 7: Clean up resources
        print("Cleaning up..")
        docker_service.stop_container(container_name)

    print(f"Done! New initrd can be found at {out}")


if __name__ == "__main__":
    # Command-line interface for standalone usage
    parser = argparse.ArgumentParser(description="Build initramfs image from Docker container")
    parser.add_argument("kernel_dir", help="Path to kernel directory")
    parser.add_argument("init_script", help="Path to init script")
    parser.add_argument("dockerfile", help="Path to Dockerfile")
    parser.add_argument("--context-dir", help="Build context directory")
    parser.add_argument("--build-dir", default="build", help="Build directory")
    parser.add_argument("--init-patch", help="Path to init script patch")
    parser.add_argument("--out", help="Output path for initramfs")
    
    args = parser.parse_args()
    
    build_initramfs(
        args.kernel_dir, 
        args.init_script, 
        args.dockerfile, 
        args.context_dir or os.path.dirname(args.dockerfile),
        args.build_dir, 
        args.init_patch, 
        args.out
    )
