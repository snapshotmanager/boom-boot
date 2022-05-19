# A profile with comments and blank lines
BOOM_OS_ID="3fda8a315ae33e869ba1756cce40c7d8c4c24db9"
BOOM_OS_NAME="Blanks"
BOOM_OS_SHORT_NAME="blanks"
BOOM_OS_VERSION="1 (Workstation Edition)"
BOOM_OS_VERSION_ID="1"

BOOM_OS_UNAME_PATTERN="bl1"
BOOM_OS_KERNEL_PATTERN="/vmlinuz-%{version}"
BOOM_OS_INITRAMFS_PATTERN="/initramfs-%{version}.img"
BOOM_OS_ROOT_OPTS_LVM2="rd.lvm.lv=%{lvm_root_lv}"
BOOM_OS_ROOT_OPTS_BTRFS="rootflags=%{btrfs_subvolume}"
BOOM_OS_OPTIONS="root=%{root_device} ro %{root_opts} rhgb quiet"
