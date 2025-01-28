#!/bin/bash

set -e

SRC_DEVICE=/dev/nbd0
SRC_FOLDER=$(mktemp -d)
DST_DEVICE=/dev/nbd1
DST_FOLDER=$(mktemp -d)

SRC_IMAGE=
DST_IMAGE=verity_image.qcow2
HASH_TREE=hash_tree.bin
ROOT_HASH=roothash.txt

NON_INTERACTIVE=""

SCRIPT_PATH=$(realpath `dirname $0`)
. $SCRIPT_PATH/common.sh
. $SCRIPT_PATH/hb/release.sh

BUILD_DIR=$SCRIPT_PATH/../build

trap clean_up EXIT

prepare_verity_fs() {
	# removing SSH keys: they will be regenerated later
	sudo rm -rf $DST_FOLDER/etc/ssh/ssh_host_*

	# Disable SSH service
    echo "Disabling SSH service..."
    sudo chroot $DST_FOLDER systemctl disable ssh.service
    sudo chroot $DST_FOLDER systemctl mask ssh.service

    # Clear authorized keys
    echo "Clearing authorized keys..."
    sudo rm -f $DST_FOLDER/root/.ssh/authorized_keys
    sudo rm -rf $DST_FOLDER/home/*/.ssh
    sudo rm -rf $DST_FOLDER/etc/ssh/ssh_host_*

    # Block SSH port with iptables
    echo "Blocking SSH port 22..."
    sudo chroot $DST_FOLDER iptables -A INPUT -p tcp --dport 22 -j DROP

    # Remove unnecessary shell binaries (but keep essential ones for services like hyperbeam)
    echo "Removing unnecessary shell binaries..."
    sudo mv $DST_FOLDER/bin/bash $DST_FOLDER/bin/bash_disabled 2>/dev/null || true
    sudo mv $DST_FOLDER/bin/sh $DST_FOLDER/bin/sh_disabled 2>/dev/null || true

    # Disable TTY access
    echo "Disabling TTY access..."
    sudo sed -i '/tty[0-9]/d' $DST_FOLDER/etc/inittab 2>/dev/null || true
    sudo rm -f $DST_FOLDER/etc/securetty 2>/dev/null || true
    sudo rm -f $DST_FOLDER/dev/tty*

    # Change default login shell to /usr/sbin/nologin for all users
    echo "Changing default shell for all users..."
    sudo sed -i 's#/bin/bash#/usr/sbin/nologin#g' $DST_FOLDER/etc/passwd
    sudo sed -i 's#/bin/sh#/usr/sbin/nologin#g' $DST_FOLDER/etc/passwd

    # Allow specific shell for hyperbeam (if required)
    echo "Allowing shell for hyperbeam service user..."
    sudo sed -i '/hyperbeam/s#/usr/sbin/nologin#/bin/bash_disabled#g' $DST_FOLDER/etc/passwd

	# remove any data in tmp folder
	sudo rm -rf $DST_FOLDER/tmp

	# rename home, etc, var dirs
	sudo mv $DST_FOLDER/home $DST_FOLDER/home_ro
	sudo mv $DST_FOLDER/etc $DST_FOLDER/etc_ro
	sudo mv $DST_FOLDER/var $DST_FOLDER/var_ro

	# create new home, etc, var dirs (original will be mounted as R/W tmpfs)
	sudo mkdir -p $DST_FOLDER/home $DST_FOLDER/etc $DST_FOLDER/var $DST_FOLDER/tmp
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

echo "Build HyperBEAM.."
build_and_copy_hb

echo "Copying HyperBEAM.."
sudo rsync -axHAWXS --numeric-ids --info=progress2 $BUILD_DIR/hb/hb $DST_FOLDER/usr/local/bin/

echo "Copy HyperBEAM service.."
sudo rsync -axHAWXS --numeric-ids --info=progress2 $BUILD_DIR/hb/hyperbeam.service $DST_FOLDER/etc/systemd/system/hyperbeam.service

echo "Enabling HyperBEAM service.."
sudo chroot $DST_FOLDER systemctl enable hyperbeam.service

echo "Preparing output filesystem for dm-verity.."
prepare_verity_fs

echo "Unmounting images.."
sudo umount -q "$SRC_FOLDER"
sudo umount -q "$DST_FOLDER"

echo "Computing hash tree.."
sudo veritysetup format $DST_DEVICE $HASH_TREE | grep Root | cut -f2 > $ROOT_HASH

echo "Root hash: `cat $ROOT_HASH`"

echo "All done!"

	# # # removing SSH keys: they will be regenerated later
	# sudo rm -rf $DST_FOLDER/etc/ssh/ssh_host_*

    # # Disable SSH service
    # echo "Disabling SSH service..."
    # sudo chroot $DST_FOLDER systemctl disable ssh.service
    # sudo chroot $DST_FOLDER systemctl mask ssh.service

	# # Removing SSH keys and configuration
	# echo "Clearing authorized keys..."
	# sudo rm -f $DST_FOLDER/root/.ssh/authorized_keys
	# sudo rm -rf $DST_FOLDER/home/*/.ssh

    # # Block SSH port with iptables
    # echo "Blocking SSH port 22..."
    # sudo chroot $DST_FOLDER iptables -A INPUT -p tcp --dport 22 -j DROP
    # sudo chroot $DST_FOLDER iptables-save > /etc/iptables/rules.v4

    # # Remove shell binaries
    # echo "Removing shell binaries..."
    # sudo rm -f $DST_FOLDER/bin/bash
    # sudo rm -f $DST_FOLDER/bin/sh
    # sudo rm -f $DST_FOLDER/usr/bin/dash
    # sudo rm -f $DST_FOLDER/usr/bin/zsh
    # sudo rm -f $DST_FOLDER/usr/bin/ksh

    # # Disable TTY access
    # echo "Disabling TTY access..."
    # sudo sed -i '/tty[0-9]/d' $DST_FOLDER/etc/inittab 2>/dev/null || true
    # sudo rm -f $DST_FOLDER/etc/securetty 2>/dev/null || true
    # sudo rm -f $DST_FOLDER/dev/tty*

    # # Change default login shell to /bin/false
    # echo "Changing default shell for all users..."
    # sudo sed -i 's#/bin/bash#/bin/false#g' $DST_FOLDER/etc/passwd
    # sudo sed -i 's#/bin/sh#/bin/false#g' $DST_FOLDER/etc/passwd

