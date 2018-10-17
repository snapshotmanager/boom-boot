BOOM_OS_ID="c48d3c2d3fe9c53384a99fbd402e2ea5bcba5a49"
BOOM_OS_NAME="Fedora Core"
BOOM_OS_SHORT_NAME="fedora"
BOOM_OS_VERSION="1 (Workstation Edition)"
BOOM_OS_VERSION_ID="1"
BOOM_OS_UNAME_PATTERN="fc1"
BOOM_OS_KERNEL_PATTERN="/vmlinuz-%{version}"
BOOM_OS_INITRAMFS_PATTERN="/initramfs-%{version}.img"
BOOM_OS_ROOT_OPTS_LVM2="rd.lvm.lv=%{lvm_root_lv}"
BOOM_OS_ROOT_OPTS_BTRFS="rootflags=%{btrfs_subvolume}"
BOOM_OS_OPTIONS="root=%{root_device} ro %{root_opts} rhgb quiet"
BOOM_OS_TITLE="%{os_name} %{os_version_id} (%{version})"
