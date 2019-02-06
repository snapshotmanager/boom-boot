BOOM_OS_ID="21e37c8002f33c177524192b15d91dc9612343a3"
BOOM_OS_NAME="Ubuntu"
BOOM_OS_SHORT_NAME="ubuntu"
BOOM_OS_VERSION="16.04 LTS (Xenial Xerus)"
BOOM_OS_VERSION_ID="16.04"
BOOM_OS_UNAME_PATTERN="generic"
BOOM_OS_KERNEL_PATTERN="/vmlinuz-%{version}"
BOOM_OS_INITRAMFS_PATTERN="/initrd.img-%{version}"
BOOM_OS_ROOT_OPTS_LVM2="rd.lvm.lv=%{lvm_root_lv}"
BOOM_OS_ROOT_OPTS_BTRFS="rootflags=%{btrfs_subvolume}"
BOOM_OS_OPTIONS="root=%{root_device} ro %{root_opts}"
