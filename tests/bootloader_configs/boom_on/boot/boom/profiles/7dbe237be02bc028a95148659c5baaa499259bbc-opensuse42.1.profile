BOOM_OS_ID="7dbe237be02bc028a95148659c5baaa499259bbc"
BOOM_OS_NAME="openSUSE Leap"
BOOM_OS_SHORT_NAME="opensuse"
BOOM_OS_VERSION="42.1"
BOOM_OS_VERSION_ID="42.1"
BOOM_OS_UNAME_PATTERN="default"
BOOM_OS_KERNEL_PATTERN="/vmlinuz-%{version}"
BOOM_OS_INITRAMFS_PATTERN="/initramfs-%{version}.img"
BOOM_OS_ROOT_OPTS_LVM2="rd.lvm.lv=%{lvm_root_lv}"
BOOM_OS_ROOT_OPTS_BTRFS="rootflags=%{btrfs_subvolume}"
BOOM_OS_OPTIONS="root=%{root_device} ro %{root_opts}"
