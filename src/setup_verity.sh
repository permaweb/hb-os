#!/bin/bash

set -e

SRC_DEVICE=/dev/nbd0
SRC_FOLDER=$(mktemp -d)
DST_DEVICE=/dev/nbd1
DST_FOLDER=$(mktemp -d)

SRC_IMAGE=
DST_IMAGE=image.qcow2
HASH_TREE=hash_tree.bin
ROOT_HASH=roothash.txt

NON_INTERACTIVE=""

SCRIPT_PATH=$(realpath `dirname $0`)
. $SCRIPT_PATH/common.sh

BUILD_DIR=$SCRIPT_PATH/../../build

trap clean_up EXIT


prepare_verity_fs() {
	# removing SSH keys: they will be regenerated later
	sudo rm -rf $DST_FOLDER/etc/ssh/ssh_host_*

    # If debug mode is disabled, perform black box preparation else print skipped message
	if [ "$DEBUG" == "0" ]; then

		# Disable SSH service
		echo "Disabling SSH service..."
		sudo chroot $DST_FOLDER systemctl disable ssh.service
		sudo chroot $DST_FOLDER systemctl mask ssh.service

		# Disable login for all users except root
		echo "Disabling login for all users except root..."
		sudo sed -i '/^[^:]*:[^:]*:[^:]*:[^:]*:[^:]*:[^:]*:\/bin\/bash$/ s/\/bin\/bash/\/usr\/sbin\/nologin/' $DST_FOLDER/etc/passwd

		# Disable all TTY services (tty1 through tty6)
		echo "Disabling all TTY services..."
		for i in {1..6}; do
			sudo chroot $DST_FOLDER systemctl disable getty@tty$i.service
			sudo chroot $DST_FOLDER systemctl mask getty@tty$i.service
		done

		# Disable serial console (ttyS0)
		echo "Disabling serial console (ttyS0)..."
		sudo chroot $DST_FOLDER systemctl disable serial-getty@ttyS0.service
		sudo chroot $DST_FOLDER systemctl mask serial-getty@ttyS0.service

		# Remove TTY kernel console configuration (GRUB)
		if [ -f "$DST_FOLDER/etc/default/grub" ]; then
			echo "Removing TTY kernel console configuration from GRUB..."
			sudo sed -i 's/console=.*//g' $DST_FOLDER/etc/default/grub
			sudo sed -i 's/^GRUB_CMDLINE_LINUX_DEFAULT="\(.*\)"/GRUB_CMDLINE_LINUX_DEFAULT="\1 console=none"/' $DST_FOLDER/etc/default/grub
		fi

		# Ensure no TTY devices are active at runtime
		echo "Disabling TTY devices..."
		for dev in tty tty0 tty1 tty2 tty3 tty4 tty5 tty6 ttyS0; do
			if [ -e "$DST_FOLDER/dev/$dev" ]; then
				sudo mv $DST_FOLDER/dev/$dev $DST_FOLDER/dev/${dev}_disabled || true
			fi
		done

		# Disable kernel messages to console
		echo "Disabling kernel messages to console..."
		sudo chroot $DST_FOLDER dmesg --console-off || true
		echo "Black box preparation complete. No TTY or console interfaces are accessible."
	else
		echo "Debug mode enabled. Skipping black box preparation."
	fi

	# remove any data in tmp folder
	sudo rm -rf $DST_FOLDER/tmp

	# rename home, etc, var dirs
	# sudo mv $DST_FOLDER/home $DST_FOLDER/home_ro
	sudo mv $DST_FOLDER/root $DST_FOLDER/root_ro
	sudo mv $DST_FOLDER/etc $DST_FOLDER/etc_ro
	sudo mv $DST_FOLDER/var $DST_FOLDER/var_ro

	# create new home, etc, var dirs (original will be mounted as R/W tmpfs)
	sudo mkdir -p $DST_FOLDER/home $DST_FOLDER/etc $DST_FOLDER/var $DST_FOLDER/tmp

	# Copy home_ro contents to home
	sudo cp -r $DST_FOLDER/root_ro $DST_FOLDER/root/

}

usage() {
  echo "$0 [options]"
  echo " -y                                     non-interactive option (do not ask if rootfs device is correct)"
  echo " -image <path to file>                  path to VM image"
  echo " -device <device>                       NBD device to use (default: $FS_DEVICE)"
  echo " -out-image <path to file>              output path to verity image (default: $DST_IMAGE)"
  echo " -out-hash-tree <path to file>          output path to device hash tree (default: $HASH_TREE)"
  echo " -out-root-hash <path to file>          output path to root hash (default: $ROOT_HASH)"
  exit
}

while [ -n "$1" ]; do
	case "$1" in
		-y) NON_INTERACTIVE="1"
			;;
		-image) SRC_IMAGE="$2"
			shift
			;;
		-device) FS_DEVICE="$2"
			shift
			;;
		-out-image) DST_IMAGE="$2"
			shift
			;;
		-out-hash-tree) HASH_TREE="$2"
			shift
			;;
		-out-root-hash) ROOT_HASH="$2"
			shift
			;;
        -debug) DEBUG="$2"
			shift
			;;
		*) 		usage
				;;
	esac

	shift
done

echo "Creating output image.."
create_output_image

echo "Initializing NBD module.."
initialize_nbd

echo "Finding root filesystem.."
find_root_fs_device
echo "Rootfs device selected: $SRC_ROOT_FS_DEVICE"

echo "Creating ext4 partition on output image.."
sudo mkfs.ext4 $DST_DEVICE

echo "Mounting images.."
sudo mount $SRC_ROOT_FS_DEVICE $SRC_FOLDER 
sudo mount $DST_DEVICE $DST_FOLDER

echo "Copying files (this may take some time).."
copy_filesystem

echo "Copying HyperBEAM.."
sudo rsync -axHAWXS --numeric-ids --info=progress2 $BUILD_DIR/hb/hb $DST_FOLDER/root

echo "Copy HyperBEAM service.."
sudo rsync -axHAWXS --numeric-ids --info=progress2 $BUILD_DIR/hb/hyperbeam.service $DST_FOLDER/etc/systemd/system/hyperbeam.service

echo "Enabling HyperBEAM service.."
sudo chroot $DST_FOLDER systemctl enable hyperbeam.service

echo "Copying CU.."
sudo rsync -axHAWXS --numeric-ids --info=progress2 $BUILD_DIR/hb/cu $DST_FOLDER/root

echo "Copy CU service.."
sudo rsync -axHAWXS --numeric-ids --info=progress2 $BUILD_DIR/hb/cu.service $DST_FOLDER/etc/systemd/system/cu.service

echo "Enabling CU service.."
sudo chroot $DST_FOLDER systemctl enable cu.service

echo "Preparing output filesystem for dm-verity.."
prepare_verity_fs

echo "Unmounting images.."
sudo umount -q "$SRC_FOLDER"
sudo umount -q "$DST_FOLDER"

echo "Computing hash tree.."
sudo veritysetup format $DST_DEVICE $HASH_TREE | grep Root | cut -f2 > $ROOT_HASH

echo "Root hash: `cat $ROOT_HASH`"

echo "All done!"