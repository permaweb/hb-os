#!/usr/bin/env python3
"""
CLI handling functionality moved from the run script.
Contains the exact same functions without modifications.
"""

import os
import sys
import argparse
from typing import Optional, NoReturn
from config import config
from src.core import init, setup_host, setup_gpu, build_snp_packages, build_base_image, build_guest_image, start_vm, start_release_vm, ssh_vm
from src.services import package_release, download_release, clean
from src.utils import HyperBeamError


def show_help() -> None:
    """
    Display detailed help information about available commands.
    """
    help_text = """
HyperBEAM VM Automation Tool
============================

USAGE: 
  ./run COMMAND [OPTIONS]
  ./run COMMAND --help    (for command-specific help)

COMMANDS:
  init                Initialize the build environment (install dependencies, download SNP release)
    Options:
      --snp-release PATH     Use pre-built SNP release directory or tarball (optional)
  setup_host          Set up the host system using the SNP release installer
  build_snp_release   Build SNP release package (kernel, OVMF, QEMU) from source
  build_base          Build the base VM image (unpack kernel, build initramfs, create VM)
  
  build_guest         Build the guest image (build content, set up verity, create VM config)
    Options:
      --hb-branch BRANCH     HyperBEAM branch to use
      --ao-branch BRANCH     AO branch to use
  
  start               Start the VM using QEMU with the guest image configuration
    Options:
      --data-disk PATH       Path to data disk image
      --enableSSL            Enable SSL port forwarding (443)
  
  start_release       Start the VM in release mode using files from the release folder
    Options:
      --data-disk PATH       Path to data disk image
      --enableSSL            Enable SSL port forwarding (443)
  
  package_release     Package all files needed for starting the VM into a release folder
  
  download_release    Download a tar.gz release from the provided URL
    Options:
      --url URL              URL to a tar.gz release file (required)
  
  ssh                 SSH into the virtual machine
  clean               Clean up the build directory
  help                Display this help information

EXAMPLES:
  ./run init
  ./run init --snp-release /path/to/snp-release.tar.gz
  ./run build_snp_release
  ./run build_base
  ./run build_guest --hb-branch main --ao-branch v1.0
  ./run start --data-disk /path/to/disk.img
  ./run start --data-disk /path/to/disk.img --enableSSL
  ./run start_release --data-disk /path/to/disk.img
  ./run start_release --data-disk /path/to/disk.img --enableSSL
  ./run download_release --url https://example.com/release.tar.gz
    """
    print(help_text)


def create_argument_parser() -> argparse.ArgumentParser:
    """
    Create and configure the command-line argument parser with all subcommands.
    
    Returns:
        argparse.ArgumentParser: Configured argument parser
    """
    # Create the main parser
    parser = argparse.ArgumentParser(
        description="HyperBEAM VM Automation Tool"
    )
    
    # Create subparsers for each command
    subparsers = parser.add_subparsers(dest="target", help="Target task to execute")
    
    # Help command
    help_parser = subparsers.add_parser("help", help="Display detailed help information")
    
    # Init command
    init_parser = subparsers.add_parser("init", help="Initialize the build environment")
    init_parser.add_argument(
        "--snp-release",
        metavar="PATH",
        help="Path to pre-built SNP release directory or tarball (optional)"
    )
    
    # Setup host command
    setup_host_parser = subparsers.add_parser("setup_host", help="Set up the host system")

    # Setup GPU command
    setup_gpu_parser = subparsers.add_parser("setup_gpu", help="Setup the GPU CC for the host system")
    
    # Build SNP release command
    build_snp_release_parser = subparsers.add_parser("build_snp_release", help="Build SNP release package from source")
    
    # Build base command
    build_base_parser = subparsers.add_parser("build_base", help="Build the base VM image")
    
    # Build guest command
    build_guest_parser = subparsers.add_parser("build_guest", help="Build the guest image")
    build_guest_parser.add_argument(
        "--hb-branch",
        help="HyperBEAM branch to use"
    )
    build_guest_parser.add_argument(
        "--ao-branch",
        help="AO branch to use"
    )
    
    # Start command
    start_parser = subparsers.add_parser("start", help="Start the VM")
    start_parser.add_argument(
        "--data-disk",
        help="Path to data disk image"
    )
    start_parser.add_argument(
        "--enableSSL",
        action="store_true",
        help="Enable SSL port forwarding (443)"
    )

    
    # Start release command
    start_release_parser = subparsers.add_parser("start_release", help="Start the VM in release mode")
    start_release_parser.add_argument(
        "--data-disk",
        help="Path to data disk image"
    )
    start_release_parser.add_argument(
        "--enableSSL",
        action="store_true",
        help="Enable SSL port forwarding (443)"
    )


    # Package release command
    package_release_parser = subparsers.add_parser("package_release", help="Package files for release")
    
    # Download release command
    download_release_parser = subparsers.add_parser("download_release", help="Download a release")
    download_release_parser.add_argument(
        "--url",
        required=True,
        help="URL to a tar.gz release file (required)"
    )
    
    # SSH command
    ssh_parser = subparsers.add_parser("ssh", help="SSH into the virtual machine")
    
    # Clean command
    clean_parser = subparsers.add_parser("clean", help="Clean up the build directory")
    
    return parser


def process_arguments(args: argparse.Namespace) -> bool:
    """
    Process and validate parsed arguments, handling special cases and configuration.
    
    Args:
        args: Parsed command-line arguments
        
    Returns:
        bool: True if processing should continue, False if program should exit
    """
    # Show help if no target is provided
    if not args.target:
        show_help()
        sys.exit(0)
        
    # Handle help command
    if args.target == "help":
        show_help()
        sys.exit(0)
    
    # Set configuration values for build_guest with validation
    if args.target == "build_guest":
        if hasattr(args, 'hb_branch') and args.hb_branch:
            if not isinstance(args.hb_branch, str) or not args.hb_branch.strip():
                raise ValueError("HyperBEAM branch must be a non-empty string")
            config.build.hb_branch = args.hb_branch.strip()
        if hasattr(args, 'ao_branch') and args.ao_branch:
            if not isinstance(args.ao_branch, str) or not args.ao_branch.strip():
                raise ValueError("AO branch must be a non-empty string")
            config.build.ao_branch = args.ao_branch.strip()
    
    # Handle download_release as a special case (immediate execution)
    if args.target == "download_release":
        # Validate URL argument
        if not hasattr(args, 'url') or not args.url:
            raise ValueError("URL is required for download_release command")
        if not isinstance(args.url, str) or not args.url.strip():
            raise ValueError("URL must be a non-empty string")
        if not (args.url.startswith('http://') or args.url.startswith('https://')):
            raise ValueError("URL must start with http:// or https://")
        
        try:
            download_release(args.url.strip())
            sys.exit(0)
        except HyperBeamError as e:
            print(f"Error: {e.message}", file=sys.stderr)
            sys.exit(e.error_code)
        except Exception as e:
            print(f"Unexpected error during download: {e}", file=sys.stderr)
            sys.exit(255)
    
    return True


def dispatch_command(args: argparse.Namespace) -> None:
    """
    Dispatch the appropriate command based on the target argument.
    
    Args:
        args: Parsed command-line arguments
        
    Raises:
        HyperBeamError: If command execution fails
    """
    # Note: Modern facade-based approach for complex operations:
    # from src.core.service_factory import get_service_container
    # from src.core.facade_interfaces import IHyperBeamFacade
    # container = get_service_container()
    # hyperbeam = container.resolve(IHyperBeamFacade)
    # hyperbeam.quick_setup() or hyperbeam.development_workflow()
    
    # For now, using legacy functions that delegate to the DI system internally:
    if args.target == "init":
        init(args.snp_release)
    elif args.target == "setup_host":
        setup_host()
    elif args.target == "setup_gpu":
        setup_gpu()
    elif args.target == "build_snp_release":
        build_snp_packages(config)
    elif args.target == "build_base":
        build_base_image()
    elif args.target == "build_guest":
        build_guest_image()
    elif args.target == "start":
        start_vm(args.data_disk, getattr(args, 'enableSSL', False))
    elif args.target == "start_release":
        start_release_vm(args.data_disk, getattr(args, 'enableSSL', False))
    elif args.target == "package_release":
        package_release()
    elif args.target == "ssh":
        ssh_vm()
    elif args.target == "clean":
        clean()
    else:
        print(f"Unknown target: {args.target}")
        show_help()
        sys.exit(1)


def main() -> NoReturn:
    """
    Main entry point: parse arguments, process them, and dispatch commands with error handling.
    
    Note: This function never returns normally - it always exits via sys.exit()
    """
    # Create and use argument parser
    parser = create_argument_parser()
    args = parser.parse_args()
    
    # Process arguments (handles help, config, and special cases)
    process_arguments(args)
    
    # Execute the appropriate function based on target with proper error handling
    try:
        dispatch_command(args)
    
    except HyperBeamError as e:
        # Handle standardized HyperBEAM errors
        print(f"Error: {e.message}", file=sys.stderr)
        if e.cause and hasattr(e, 'stdout') and e.stdout:
            print(f"Command output: {e.stdout}", file=sys.stderr)
        if e.cause and hasattr(e, 'stderr') and e.stderr:
            print(f"Command error: {e.stderr}", file=sys.stderr)
        sys.exit(e.error_code)
    
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.", file=sys.stderr)
        sys.exit(130)  # Standard exit code for SIGINT
    
    except Exception as e:
        # Handle unexpected errors
        print(f"Unexpected error: {e}", file=sys.stderr)
        print("This may be a bug. Please report it with the full error message.", file=sys.stderr)
        sys.exit(255)