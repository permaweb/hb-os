#!/bin/bash

# GPU Passthrough Setup Script
# This script configures NVIDIA GPU passthrough for virtual machines

set -e  # Exit on any error

echo "=== GPU Passthrough Setup ==="

# Function to check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        echo "This script must be run as root (use sudo)"
        exit 1
    fi
}

# Function to detect NVIDIA GPUs
detect_nvidia_gpu() {
    echo "Detecting NVIDIA GPUs..."

    # Get NVIDIA GPU PCI addresses
    NVIDIA_GPUS=$(lspci -d 10de: | awk '/NVIDIA/{print $1}')

    if [ -z "$NVIDIA_GPUS" ]; then
        echo "No NVIDIA GPUs found"
        return 1
    fi

    echo "Found NVIDIA GPU(s):"
    echo "$NVIDIA_GPUS"
    return 0
}

# Function to enable VFIO-PCI driver
enable_vfio_pci() {
    echo "Enabling VFIO-PCI driver..."

    # Load VFIO-PCI module
    modprobe vfio-pci

    # Check if module loaded successfully
    if lsmod | grep -q vfio_pci; then
        echo "VFIO-PCI driver loaded successfully"
    else
        echo "Failed to load VFIO-PCI driver"
        return 1
    fi
}

# Function to check if GPU is already bound to VFIO-PCI
is_gpu_bound_to_vfio() {
    local gpu_address=$1

    # Check if GPU is already bound to VFIO-PCI
    if [ -d "/sys/bus/pci/drivers/vfio-pci/0000:$gpu_address" ]; then
        return 0  # Already bound
    else
        return 1  # Not bound
    fi
}

# Function to check if vendor/device ID is already registered with VFIO-PCI
is_device_id_registered() {
    local vendor_id=$1
    local device_id=$2

    # Check if any device with this vendor/device ID is bound to vfio-pci
    # This is a more reliable way than checking new_id file which is write-only
    if [ -d "/sys/bus/pci/drivers/vfio-pci" ]; then
        for device_dir in /sys/bus/pci/drivers/vfio-pci/0000:*; do
            if [ -d "$device_dir" ]; then
                device_path=$(basename "$device_dir")
                device_addr=${device_path#0000:}

                # Get the vendor:device ID for this bound device
                bound_vendor_device=$(lspci -n -s "$device_addr" 2>/dev/null | awk '{print $3}')
                if [ "$bound_vendor_device" = "$vendor_id:$device_id" ]; then
                    return 0  # Device with this ID is already bound
                fi
            fi
        done
    fi
    return 1  # Not registered/bound
}

# Function to configure GPU passthrough for a specific GPU
configure_gpu_passthrough() {
    local gpu_address=$1

    echo "Configuring passthrough for GPU: $gpu_address"

    # Check if GPU is already bound to VFIO-PCI
    if is_gpu_bound_to_vfio "$gpu_address"; then
        echo "GPU $gpu_address is already bound to VFIO-PCI - skipping"
        return 0
    fi

    # Get vendor and device ID
    local vendor_device=$(lspci -n -s "$gpu_address" | awk '{print $3}')
    local vendor_id=$(echo "$vendor_device" | cut -d: -f1)
    local device_id=$(echo "$vendor_device" | cut -d: -f2)

    echo "Vendor ID: $vendor_id, Device ID: $device_id"

    # Try to register device ID first, then bind directly if registration fails
    device_registered=false
    if is_device_id_registered "$vendor_id" "$device_id"; then
        echo "Device ID $vendor_id:$device_id is already registered with VFIO-PCI"
        device_registered=true
    else
        echo "Registering device ID $vendor_id:$device_id with VFIO-PCI..."
        if echo "$vendor_id $device_id" > /sys/bus/pci/drivers/vfio-pci/new_id 2>/dev/null; then
            echo "Device ID registered successfully"
            device_registered=true
        else
            echo "Device ID registration failed (may already be registered), trying direct bind..."
        fi
    fi

    # If device is not bound yet, try direct binding
    if [ ! -d "/sys/bus/pci/drivers/vfio-pci/0000:$gpu_address" ]; then
        echo "Attempting direct bind of GPU $gpu_address to VFIO-PCI..."
        if echo "0000:$gpu_address" > /sys/bus/pci/drivers/vfio-pci/bind 2>/dev/null; then
            echo "GPU bound successfully via direct bind"
        else
            echo "Direct bind failed"
        fi
    fi

    # Verify final binding status
    if [ -d "/sys/bus/pci/drivers/vfio-pci/0000:$gpu_address" ]; then
        echo "✓ GPU $gpu_address successfully bound to VFIO-PCI"
    else
        echo "✗ GPU $gpu_address failed to bind to VFIO-PCI"
        return 1
    fi
}

# Function to unbind GPU from current driver
unbind_gpu() {
    local gpu_address=$1

    echo "Unbinding GPU $gpu_address from current driver..."

    # Find current driver
    local current_driver_path="/sys/bus/pci/devices/0000:$gpu_address/driver"

    if [ -L "$current_driver_path" ]; then
        local current_driver=$(basename $(readlink "$current_driver_path"))
        echo "Current driver: $current_driver"

        # Unbind from current driver
        echo "0000:$gpu_address" > "/sys/bus/pci/drivers/$current_driver/unbind"
        echo "Unbound from $current_driver"
    else
        echo "No driver currently bound to GPU $gpu_address"
    fi
}

# Function to show GPU status
show_gpu_status() {
    echo "=== GPU Status ==="

    echo "NVIDIA GPUs detected:"
    lspci -d 10de: | grep NVIDIA

    echo ""
    echo "VFIO-PCI driver status:"
    if lsmod | grep -q vfio_pci; then
        echo "✓ VFIO-PCI driver is loaded"
    else
        echo "✗ VFIO-PCI driver is not loaded"
    fi

    echo ""
    echo "VFIO-PCI bound devices:"
    if [ -d "/sys/bus/pci/drivers/vfio-pci" ]; then
        bound_devices=$(ls /sys/bus/pci/drivers/vfio-pci/ | grep "0000:" 2>/dev/null || true)
        if [ -n "$bound_devices" ]; then
            for device in $bound_devices; do
                device_info=$(lspci -s "${device#0000:}" 2>/dev/null || echo "Unknown device")
                echo "  ✓ $device: $device_info"
            done
        else
            echo "  No devices currently bound to VFIO-PCI"
        fi
    else
        echo "  VFIO-PCI driver directory not found"
    fi

    echo ""
    echo "Device types registered with VFIO-PCI:"
    if [ -d "/sys/bus/pci/drivers/vfio-pci" ]; then
        bound_devices=$(ls /sys/bus/pci/drivers/vfio-pci/ | grep "0000:" 2>/dev/null || true)
        if [ -n "$bound_devices" ]; then
            declare -A seen_device_types
            for device in $bound_devices; do
                device_addr=${device#0000:}
                vendor_device=$(lspci -n -s "$device_addr" 2>/dev/null | awk '{print $3}')
                if [ -n "$vendor_device" ] && [ -z "${seen_device_types[$vendor_device]}" ]; then
                    seen_device_types[$vendor_device]=1
                    echo "  ✓ $vendor_device"
                fi
            done
        else
            echo "  No device types registered"
        fi
    else
        echo "  VFIO-PCI driver directory not found"
    fi
}

# Function to setup GPU passthrough for all NVIDIA GPUs
setup_all_gpus() {
    echo "Setting up passthrough for all NVIDIA GPUs..."

    # Enable VFIO-PCI driver
    enable_vfio_pci

    # Process each GPU
    for gpu in $NVIDIA_GPUS; do
        echo "Processing GPU: $gpu"
        configure_gpu_passthrough "$gpu"
        echo "---"
    done
}



# Main execution
main() {
    case "${1:-setup}" in
        "setup")
            check_root
            if detect_nvidia_gpu; then
                setup_all_gpus
                show_gpu_status
                echo "GPU passthrough setup completed!"
            else
                echo "No NVIDIA GPUs found. Exiting."
                exit 1
            fi
            ;;
        "status")
            show_gpu_status
            ;;
        "help"|"-h"|"--help")
            echo "Usage: $0 [setup|status|cleanup|help]"
            echo ""
            echo "Commands:"
            echo "  setup   - Configure GPU passthrough (default)"
            echo "  status  - Show current GPU status"
            echo "  help    - Show this help message"
            ;;
        *)
            echo "Unknown command: $1"
            echo "Use '$0 help' for usage information"
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"