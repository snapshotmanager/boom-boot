==========
User Guide
==========

Overview
========

Boom is a boot manager for Linux systems that simplifies the creation and
management of boot entries using the `Boot Loader Specification (BLS)
<https://uapi-group.org/specifications/specs/boot_loader_specification/>`_. It
enables flexible boot configuration and simplifies creating boot entries for
system snapshots created using LVM2, Stratis, or BTRFS.

Key Features
------------

* **Profile-Based Configuration**: Automatic OS detection with customizable templates
* **Snapshot Support**: Easy boot entry creation for LVM2, Stratis, and BTRFS snapshots
* **Non-Intrusive**: Preserves existing bootloader configuration
* **Host Customization**: Per-system boot parameter customization
* **Boot Image Cache**: Optional backup of kernel and initramfs images
* **BLS Compliance**: Works with systemd-boot and BLS-enabled GRUB 2

Architecture
============

Core Components
---------------

Boom operates on three main object types:

**OsProfile**
    Contains OS identity information and boot entry templates. Profiles are
    identified by OS-release data and include patterns for kernel images, initramfs
    files, and boot options.

**HostProfile**
    Optional per-system customization that modifies OsProfile templates. Allows
    adding/removing kernel options or modifying boot image paths on a
    per-installation basis.

**BootEntry**
    Individual bootloader entries generated from profiles and boot parameters.
    Each entry includes all parameters needed to boot an OS instance.

Data Storage
------------

Boom stores its data in the ``/boot`` filesystem to ensure availability from
any booted OS:

* **Boot entries**: ``/boot/loader/entries/`` (BLS format)
* **Configuration**: ``/boot/boom/boom.conf``
* **OS profiles**: ``/boot/boom/profiles/``
* **Host profiles**: ``/boot/boom/hosts/``
* **Boot image cache**: ``/boot/boom/cache/``

Installation
============

Package Installation
--------------------

**Red Hat Enterprise Linux 8+ / Fedora**::

    dnf install boom-boot

**Red Hat Enterprise Linux 7**::

    yum install lvm2-python-boom

**From Source**::

    git clone https://github.com/snapshotmanager/boom-boot.git
    cd boom-boot
    python3 -m pip install .

Requirements
------------

* BLS-compatible bootloader (systemd-boot or GRUB 2 with BLS support)
* Python 3.9 or later
* LVM2, Stratis, or BTRFS for snapshot functionality

Command Line Interface
======================

The ``boom`` command provides the main interface to the boom boot manager. Commands operate on specific object types:

.. code-block:: bash

    boom [entry] <command> <options>        # BootEntry commands (default)
    boom profile <command> <options>        # OsProfile commands
    boom host <command> <options>           # HostProfile commands
    boom cache <command> <options>          # Cache commands

Core Commands
-------------

The entry, profile, and host object types support these commands:

**create**
    Create new objects with specified parameters

**delete**
    Remove existing objects by identifier

**clone**
    Create new objects by copying and modifying existing ones

**show**
    Display detailed information about objects

**list**
    Generate tabular reports of objects

**edit**
    Modify existing object properties

Working with OS Profiles
========================

OS Profiles define how boot entries are created for a specific operating system
distribution. They contain identity information from ``/etc/os-release`` and
templates for generating boot configuration.

Creating Profiles
-----------------

**From the running system**::

    boom profile create --from-host

**Manual creation**::

    boom profile create \\
        --name "Custom Linux" \\
        --short-name custom \\
        --version "1.0" \\
        --version-id "1.0" \\
        --kernel-pattern "/c9d1bfa49e885b1000adc367f5bbc569/%{version}/linux" \\
        --initramfs-pattern "/c9d1bfa49e885b1000adc367f5bbc569/%{version}/initrd"

Profile Templates
-----------------

Profiles use template strings expanded when creating boot entries:

* ``%{version}`` - Kernel version
* ``%{lvm_root_lv}`` - LVM2 root logical volume (vg/lv format)
* ``%{btrfs_subvol_id}`` - BTRFS subvolume ID
* ``%{btrfs_subvol_path}`` - BTRFS subvolume path
* ``%{btrfs_subvolume}`` - BTRFS subvolume (path or ID)
* ``%{root_device}`` - Root device specification
* ``%{root_opts}`` - Root filesystem options
* ``%{options}`` - Complete kernel command line options

Example profile templates::

    Kernel pattern: "/vmlinuz-%{version}"
    Initramfs pattern: "/initramfs-%{version}.img"
    Options: "root=%{root_device} ro %{root_opts} rhgb quiet"

Managing Profiles
-----------------

**List all profiles**::

    boom profile list

**Show profile details**::

    boom profile show --profile a1b2c3d

**Edit a profile**::

    boom profile edit --profile a1b2c3d --options "root=%{root_device} ro %{root_opts}"

**Delete a profile**::

    boom profile delete --profile a1b2c3d

Working with Host Profiles
==========================

Host Profiles provide per-system customization of OS Profile templates. They
allow modifying boot parameters for specific installations without changing the
base OS Profile.

Creating Host Profiles
----------------------

**Basic host profile**::

    boom host create --profile a1b2c3d --add-opts debug

**Advanced customization**::

    boom host create \\
        --profile a1b2c3d \\
        --label production \\
        --add-opts "debug console=ttyS0" \\
        --del-opts "rhgb quiet" \\
        --kernel-pattern "/vmlinuz-%{version}-prod"

Host Profile Options
--------------------

**add-opts**
    Kernel command line options to add

**del-opts**
    Kernel command line options to remove

**kernel-pattern**
    Override kernel image path template

**initramfs-pattern**
    Override initramfs image path template

**label**
    Descriptive label for the host profile

Managing Host Profiles
----------------------

**List host profiles**::

    boom host list

**Show details**::

    boom host show --host-profile x1y2z3a

**Edit host profile**::

    boom host edit --host-profile x1y2z3a --add-opts "mem=4G"

Working with Boot Entries
=========================

Boot Entries are individual bootloader entries that define how to boot a
specific OS instance. They are generated from OS Profile templates combined
with boot parameters.

Creating Boot Entries
---------------------

**Basic entry creation**::

    boom create --title "System Backup" --root-device /dev/sda3

**Snapshot boot entry**::

    boom create \\
        --title "Pre-upgrade Snapshot" \\
        --root-lv vg/root-snapshot

**BTRFS snapshot entry**::

    boom create \\
        --title "BTRFS Snapshot" \\
        --root-device /dev/sda1 \\
        --btrfs-subvolume @snapshots/2024-01-15

**Using specific profiles**::

    boom create \\
        --profile a1b2c3d \\
        --title "Custom Boot" \\
        --root-device /dev/sda3

Boot Entry Options
------------------

**Required Parameters**
    * ``--title`` - Boot entry display title
    * ``--root-device`` or ``--root-lv`` - Root device selection

**Root Device Options**
    * ``--root-lv`` - LVM2 logical volume (vg/lv format)
    * ``--root-device`` - Block device path
    * ``--btrfs-subvolume`` - BTRFS subvolume path or ID

**Additional Options**
    * ``--add-opts`` - Extra kernel command line options
    * ``--del-opts`` - Remove default kernel options
    * ``--profile`` - Specific OS Profile to use
    * ``--backup`` - Create backup copies of boot images

Managing Boot Entries
---------------------

**List all entries**::

    boom list

The default fields are ``bootid``, ``version``, ``osname``, ``rootdev``: see
``man 8 boom`` for further information.

**Detailed entry information**::

    boom show --boot-id f1e2d3c4

**Clone and modify**::

    boom clone --boot-id f1e2d3c4 --title "Modified Entry" --add-opts debug

**Edit existing entry**::

    boom edit --boot-id f1e2d3c4 --title "Updated Title"

**Delete entry**::

    boom delete --boot-id f1e2d3c4

Tip: When the context is unambiguous, you can omit ``--boot-id`` and let
boom infer the target from the current selection or sole match.

Complete Snapshot Environments
==============================

*Added in boom-1.6.0*

With systemd v254 or later — or RHEL 9.6+ where this feature is backported
(systemd-252-18.el9) — boom supports creating complete snapshot environments
that include not only the root filesystem but also arbitrary auxiliary mounts.
This feature uses the ``--no-fstab`` and ``--mount`` options to bypass normal
fstab processing and specify exact mount configurations on the kernel command
line.

Mount Specification Format
--------------------------

The ``--mount`` option uses the format::

    --mount WHAT:WHERE:FSTYPE:OPTIONS

Where:
    * **WHAT** - Device path, UUID, or LABEL
    * **WHERE** - Mount point path
    * **FSTYPE** - Filesystem type (ext4, xfs, btrfs, etc.)
    * **OPTIONS** - Mount options (defaults, ro, rw, etc.)

Swap devices can be specified with::

    --swap WHAT:OPTIONS

Where:
    * **WHAT** - Device path, UUID, or LABEL of the swap device
    * **OPTIONS** - Swap options (e.g., defaults)

Complete Snapshot Workflow
--------------------------

**Create comprehensive LVM snapshots**::

    # Create snapshots for all filesystems
    lvcreate --snapshot --size 2G --name root-snapshot /dev/vg/root
    lvcreate --snapshot --size 1G --name home-snapshot /dev/vg/home
    lvcreate --snapshot --size 1G --name var-snapshot /dev/vg/var

**Create boot entry with all mounts**::

    boom create \\
        --title "Complete System Snapshot $(date +%Y-%m-%d)" \\
        --root-lv vg/root-snapshot \\
        --no-fstab \\
        --mount /dev/vg/home-snapshot:/home:ext4:defaults \\
        --mount /dev/vg/var-snapshot:/var:ext4:defaults \\
        --swap /dev/vg/swap:defaults

**BTRFS subvolume snapshots**::

    boom create \\
        --title "BTRFS Complete Snapshot" \\
        --root-device /dev/sda1 \\
        --btrfs-subvolume root-backup \\
        --no-fstab \\
        --mount /dev/sda1:/home:btrfs:subvol=home-backup \\
        --mount /dev/sda1:/var:btrfs:subvol=var-backup

**Mixed storage environments**::

    boom create \\
        --title "Mixed Snapshot Environment" \\
        --root-lv vg/root-snapshot \\
        --no-fstab \\
        --mount /dev/sdb1:/home:ext4:defaults \\
        --mount UUID=abc123:/var/log:xfs:defaults \\
        --mount LABEL=backup:/backup:ext4:ro

Use Cases
---------

**System maintenance windows**
    Create complete isolated environments for system updates, ensuring all
    configuration and data directories are captured

**Development and testing**
    Boot complete application stacks with consistent data states for testing

**Disaster recovery**
    Maintain point-in-time snapshots of entire system states that can be booted
    independently

**Compliance and auditing**
    Preserve complete system states with all mounted filesystems for compliance
    requirements

LVM2 Snapshots
--------------

**Pre-upgrade snapshot workflow**:

1. Create the snapshot::

    lvcreate --snapshot --size 5G --name root-pre-upgrade /dev/vg/root

2. Create boot entry::

    boom create \\
        --title "Pre-upgrade backup $(date +%Y-%m-%d)" \\
        --root-lv vg/root-pre-upgrade

3. Perform system upgrade

4. If issues occur, reboot and select the snapshot entry

5. To reset main volume back to the snapshot state::

   lvconvert --merge vg/root-pre-upgrade

**System maintenance snapshots**::

1. Create the snapshot::

    lvcreate --snapshot --size 2G --name root-maintenance /dev/vg/root

2. Create boot entry::

    boom create --title "Maintenance Mode" --root-lv vg/root-maintenance --add-opts "single"

BTRFS Snapshots
---------------

**Creating BTRFS snapshot entries**::

1. Create snapshot subvolume::

    btrfs subvolume snapshot / /top-level/root-backup-$(date +%Y%m%d)

2. Create boot entry::

    boom create \\
        --title "BTRFS Snapshot $(date +%Y-%m-%d)" \\
        --root-device /dev/sdb2 \\
        --btrfs-subvolume root-backup-$(date +%Y%m%d)

Boot Image Cache
================

The boot image cache allows boom to make backup copies of kernel and initramfs
images, ensuring boot entries remain functional even if original images are
removed or damaged during system updates.

Enabling the Cache
------------------

The cache is enabled in the default configuration file
``/boot/boom/boom.conf``::

    [cache]
    enable = yes
    auto_clean = yes
    cache_path = /boot/boom/cache

Using Cached Images
-------------------

**Create entry with image backup**::

    boom create --backup --title "Cached Entry" --root-lv/root-snapshot

**Cache management**::

    # List cached images
    boom cache list

    # Show cache details
    boom cache show

Reports and Output Formats
==========================

Boom provides flexible reporting with customizable field selection, multiple
output formats, and optional multi-key sorting.

Field Selection
---------------

**Default fields**::

    # Shows: BootID, Version, Name, RootDevice
    boom list

**Custom field selection**::

    boom list -o bootid,title,kernel,options

**Add fields to defaults**::

    boom list -o+initramfs,kernel

**Show all available fields**::

    boom list -o help

Available Fields
----------------

**Boot Entry Fields**
    * ``bootid`` - Boot identifier
    * ``title`` - Entry title
    * ``kernel`` - Kernel image path
    * ``initramfs`` - Initramfs image path
    * ``options`` - Kernel command line options
    * ``machineid`` - Machine identifier

**OS Profile Fields**
    * ``osid`` - OS identifier
    * ``osname`` - OS name
    * ``osversion`` - OS version string
    * ``kernelpattern`` - Kernel image template
    * ``initrdpattern`` - Initramfs template
    * ``options`` - Default kernel options

**Host Profile Fields**
    * ``hostid`` - Host identifier
    * ``hostname`` - System hostname
    * ``label`` - Profile label
    * ``addopts`` - Added options
    * ``delopts`` - Deleted options

**Boot Parameter Fields**
    * ``version`` - Kernel version used for the entry
    * ``rootdev`` - Root device (block device or LV)
    * ``rootlv`` - Root logical volume
    * ``subvolpath`` / ``subvolid`` - BTRFS subvolume identifiers

JSON Output
-----------

**Generate JSON reports**::

    boom list --json

**JSON with all fields**::

    boom list --json -o+entry_all,profile_all

Note that JSON keys always include the full field name, including the type
prefix (for example `entry_title` vs. `title`).

Example JSON output::

    {
        "Entries": [
            {
                "entry_bootid": "a1b2c3d4e5f6789012345678901234567890abcd",
                "param_version": "6.11.0-63.fc41.x86_64",
                "profile_osname": "Fedora Linux",
                "param_rootdev": "/dev/mapper/fedora-root",
                "entry_title": "Fedora Linux (6.11.0-63.fc41.x86_64) 41"
            }
        ]
    }

Advanced Configuration
======================

Configuration File
------------------

The main configuration file is ``/boot/boom/boom.conf``::

    [global]
    boot_root = /boot
    boom_root = %(boot_root)s/boom

    [legacy]
    enable = False
    format = grub1
    sync = True

    [cache]
    enable = yes
    auto_clean = yes
    cache_path = /boot/boom/cache

Environment Variables
---------------------

**BOOM_BOOT_PATH**
    Override boot filesystem path

Python API
----------

**Command API** (mimics CLI)::

    import boom.command

    # Create entry using command API
    boom.command.create_entry(
        title="API Entry",
        version="5.15.0-25",
        root_lv="vg/root"
    )

**Object API** (direct object manipulation)::

    from boom.osprofile import OsProfile
    from boom.bootloader import BootParams, BootEntry

    # Find profile
    profile = OsProfile.find_profile(short_name="fedora")

    # Create boot parameters
    bp = BootParams(root_lv="vg/root", version="5.15.0-25")

    # Create entry
    entry = BootEntry(
        title="Object API Entry",
        osprofile=profile,
        boot_params=bp,
    )
    entry.write_entry()

Troubleshooting
===============

Common Issues
-------------

**"No matching profile found"**
    * Create an OS profile for your distribution
    * Use ``--profile`` to specify a profile explicitly

**Boot entries not appearing**
    * Verify BLS support is enabled in your bootloader
    * Check ``/boot/loader/entries/`` for generated files
    * Ensure correct machine-id in entries

**Permission denied errors**
    * All boom commands require root privileges
      * Log in as root or run boom commands with ``sudo``
    * Verify ``/boot`` filesystem is writable

**Snapshot boot fails**
    * Verify snapshot exists and is accessible
    * Check LVM2/BTRFS configuration
    * Review kernel command line in boot entry

Debugging
---------

**Enable debug output**::

    boom list -VV --debug=all

**Check boom configuration**::

    boom --help
    boom profile list
    boom host list

**Verify BLS files**::

    boom list -o+entryfile
    ls -la /boot/loader/entries/
    cat /boot/loader/entries/<entry-file>

Getting Help
============

* **Documentation**: https://boom.readthedocs.io/
* **Manual page**: man 8 boom
* **Issue Tracker**: https://github.com/snapshotmanager/boom-boot/issues
* **Mailing List**: dm-devel@redhat.com
* **Command Help**: ``boom --help``
