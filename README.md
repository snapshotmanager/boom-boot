[![Build Status](https://github.com/snapshotmanager/boom-boot/actions/workflows/default.yml/badge.svg)](https://github.com/snapshotmanager/boom-boot/actions) [![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/snapshotmanager/boom-boot) [![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

# Boom Boot Manager

Boom is a Linux boot manager that simplifies creating and managing bootable
snapshots using the [Boot Loader Specification (BLS)][bls]. It enables flexible
boot configuration without modifying your existing bootloader setup.

Boom integrates with [Snapshot Manager][snapm] to provide higher level snapshot
management, including automated multi-volume snapshot sets, coordinated revert
using failsafe boot entries, snapshot scheduling with flexible retention
policies and more.

## Features

- **Minimal Configuration**: Create boot entries with just a title and a device.
  Boom auto-detects the rest.
- **Snapshot Boot Entries**: Easily boot from LVM2, Stratis, or BTRFS snapshots.
- **Profile-Based Configuration**: Automatic OS detection and template-based
  entry generation.
- **BLS Compliance**: Works with systemd-boot and BLS-enabled GRUB 2.
- **Non-Intrusive**: Preserves existing boot configuration and distribution
  integration.
- **Host Customization**: Per-system boot parameter customization.
- **Boot Image Cache**: Optional backup of kernel and initramfs images.

## Quick Start

### Installation

**Red Hat Enterprise Linux 8+/Fedora:**
```bash
dnf install boom-boot
```

**Red Hat Enterprise Linux 7:**
```bash
yum install lvm2-python-boom
```

#### Manual Installation

Clone the ``boom-boot`` repository and install using pip:

```bash
git clone https://github.com/snapshotmanager/boom-boot.git
cd boom-boot
python3 -m venv .venv && source .venv/bin/activate
python3 -m pip install .
```

### Creating Your First Snapshot Boot Entry

1. **Create an OS Profile**:
   ```bash
   boom profile create --from-host
   ```

Example output (Fedora 42):

```bash
boom profile create --from-host
Created profile with os_id 6d5913a:
  OS ID: "6d5913af35d4b022ba6b203c4160879b492e6fed",
  Name: "Fedora Linux", Short name: "fedora",
  Version: "42 (Server Edition)", Version ID: "42",
  Kernel pattern: "/vmlinuz-%{version}", Initramfs pattern: "/initramfs-%{version}.img",
  Root options (LVM2): "rd.lvm.lv=%{lvm_root_lv}",
  Root options (BTRFS): "rootflags=%{btrfs_subvolume}",
  Options: "root=%{root_device} ro %{root_opts} rhgb quiet",
  Title: "%{os_name} %{os_version_id} (%{version})",
  Optional keys: "grub_users grub_arg grub_class id", UTS release pattern: "fc42"
```

2. **Create a snapshot**:

Create a snapshot using the appropriate command for the installed system's
storage configuration. Adjust LV/subvolume names and sizes to match your setup:

LVM2 Copy-on-Write:

   ```bash
   lvcreate --snapshot --size 5G --name root-snapshot /dev/vg/root
   ```

LVM2 Thin:

   ```bash
   lvcreate --snapshot --name root-snapshot /dev/vg/thinroot
   ```

Stratis:

   ```bash
   stratis fs snapshot pool/rootfs root-snapshot
   ```

BTRFS:

   ```bash
   btrfs subvolume snapshot -r /root /root-snapshot
   ```

3. **Create a boot entry for the snapshot**:
   ```bash
   boom create --title "System Snapshot $(date +%Y-%m-%d)" --root-lv vg/root-snapshot
   ```

The new boot entry is displayed on the terminal:

```text
# boom create --title "System Snapshot $(date +%Y-%m-%d)" --root-lv vg/root-snapshot
Created entry with boot_id 6f5d483:
  title System Snapshot 2025-09-09
  machine-id 5d1e621b0c1349aea3bd47e4bb619024
  version 6.15.9-201.fc42.x86_64
  linux /vmlinuz-6.15.9-201.fc42.x86_64
  initrd /initramfs-6.15.9-201.fc42.x86_64.img
  options root=/dev/vg/root-snapshot ro rd.lvm.lv=vg/root-snapshot rhgb quiet
  grub_users $grub_users
  grub_arg --unrestricted
  grub_class kernel
```

- Tip: add ``--backup`` to cache boot images for this entry (kernel and
  initramfs).

4. **List your boot entries**:
   ```bash
   boom list
   ```

For example:

```text
# boom list
BootID  Version                  Name                     RootDevice
605b3bb 6.15.9-201.fc42.x86_64   Fedora Linux             /dev/mapper/vg-root
66dc7ad 6.15.9-201.fc42.x86_64   Fedora Linux             /dev/vg/root-snapshot
```

5. **Reboot and select your snapshot** from the boot menu!

### Managing Boot Entries

- Create a basic boot entry

```bash
boom create --title "System Backup" --root-lv vg/root
```

- Create a debug boot entry

```bash
boom create --title "Debug Boot" --root-lv vg/root --add-opts debug --del-opts "rhgb quiet"
```

- List all boot entries

```bash
boom list
```

- Show detailed entry information

```bash
boom show <boot_id>
```

- Clone an existing entry with modifications

```bash
boom clone --title "Modified Entry" --add-opts debug <boot_id>
```

- Delete an entry

```bash
boom delete <boot_id>
```

- Edit an existing entry

```bash
boom edit <boot_id> --title "New Title"
```

### Working with Profiles

- List OS profiles

```bash
boom profile list
```

- Create a custom profile

```bash
boom profile create --name "Custom OS" --short-name custom \
                      --os-version "1.0" --os-version-id 1 \
                      --kernel-pattern "/vmlinuz-%{version}" \
                      --initramfs-pattern "/initramfs-%{version}.img" \
                      --uname-pattern custom1
```

- List host profiles (per-system customizations)

```bash
boom host list
```

## Requirements

- Linux system with BLS-compatible bootloader:
  - GRUB 2 with BLS support (Red Hat/Fedora builds), or
  - systemd-boot
- Python 3.9+
- LVM2, Stratis, or BTRFS for snapshot functionality

## Documentation

- [User Guide](https://boom.readthedocs.io/en/latest/user_guide.html) - Comprehensive usage documentation
- [API Reference](https://boom.readthedocs.io/en/latest/boom.html) - Python API documentation
- [Boot Loader Specification][bls] - BLS standard documentation

## Project Structure

```text
boom-boot/
├── boom/                  # Python package
│   ├── bootloader.py     # Boot loader integration
│   ├── osprofile.py      # OS profile management
│   ├── hostprofile.py    # Host-specific profiles
│   ├── cache.py          # Boot image cache
│   ├── command.py        # Command-line interface
│   ├── config.py         # Configuration management
│   ├── mounts.py         # Mount handling (Boot Environments)
│   └── stratis.py        # Stratis storage support
├── bin/boom              # Command line tool
├── doc/                  # Sphinx documentation
├── examples/             # Example configurations and profiles
├── man/                  # Manual pages
└── tests/                # Test suite
```

## Configuration

Boom stores its configuration in:
- **Boot entries**: `/boot/loader/entries/`
- **Configuration**: `/boot/boom/boom.conf`
- **OS profiles**: `/boot/boom/profiles/`
- **Host profiles**: `/boot/boom/hosts/`
- **Boot image cache**: `/boot/boom/cache/`

## Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md)
for details.

### Submitting Changes

- Fork the repository on GitHub
- Create a feature branch from `main`
- Make your changes with appropriate tests
- Ensure your branch applies cleanly as a fast-forward merge
- Submit a pull request

## Support

- **Issues**: [GitHub Issue Tracker](https://github.com/snapshotmanager/boom-boot/issues)
- **Mailing List**: [dm-devel](https://www.redhat.com/mailman/listinfo/dm-devel)
- **Documentation**: [ReadTheDocs](https://boom.readthedocs.io/)

## License

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for details.

## Related Projects

- [Snapshot Manager][snapm] - Automated system snapshot management
- [Boot-to-snapshot Design](https://github.com/snapshotmanager/snapshot-boot-docs) - Design documentation

---

**Note**: Boom requires BLS support in your bootloader. This is enabled by
default in Fedora 30+ and RHEL 8+. For older distributions, you may need to
enable BLS support manually.

[snapm]: https://github.com/snapshotmanager/snapm
[bls]: https://uapi-group.org/specifications/specs/boot_loader_specification/
