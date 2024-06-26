![Boom CI](https://github.com/snapshotmanager/boom/actions/workflows/default.yml/badge.svg)
# Boom

Boom is a *boot manager* for Linux systems using boot loaders that
support the [BootLoader Specification][0] for boot entry configuration.
It is based on the boot manager design discussed in the
[Boot-to-snapshot design v0.6][1] document.

Boom requires a BLS compatible boot loader to function: either the
`systemd-boot` project, or `Grub2` with the `bls` patch (*Red Hat*
Grub2 builds include this support in both *Red Hat Enterprise Linux 7*
and *Fedora*).

Boom allows for flexible boot configuration and simplifies the
creation of new or modified boot entries: for example to boot
snapshot images of the system created using LVM2 or BTRFS.

Boom does not modify the existing boot loader configuration (other
than to insert the additional entries managed by boom - see
[Grub2 Integration](#grub2-integration)): the existing boot
configuration is maintained and any distribution integration (e.g.
kernel installation and update scripts) will continue to function as
before.


   * [Boom](#boom)
      * [Reporting bugs](#reporting-bugs)
      * [Mailing list](#mailing-list)
      * [Building and installing Boom](#building-and-installing-boom)
         * [Building an RPM package](#building-an-rpm-package)
      * [The boom command](#the-boom-command)
         * [Operating System Profiles and Boot Entries](#operating-system-profiles-and-boot-entries)
            * [OsProfile](#osprofile)
               * [OsProfile templates](#osprofile-templates)
            * [BootEntry](#bootentry)
         * [Boom subcommands](#boom-subcommands)
            * [create](#create)
            * [delete](#delete)
            * [clone](#clone)
            * [show](#show)
            * [list](#list)
            * [edit](#edit)
         * [Reporting commands](#reporting-commands)
         * [Getting help](#getting-help)
      * [Configuring Boom](#configuring-boom)
         * [Creating an OsProfile](#creating-an-osprofile)
         * [Creating a BootEntry](#creating-a-bootentry)
      * [Grub2 Integration](#grub2-integration)
         * [Submenu support](#submenu-support)
      * [Python API](#python-api)
         * [Command API](#command-api)
         * [Object API](#object-api)
      * [Patches and pull requests](#patches-and-pull-requests)
      * [Documentation](#documentation)

Boom aims to be a simple and extensible, and to be able to create boot
configurations for a wide range of Linux system configurations and boot
parameters.

This project is hosted at:

  * http://github.com/snapshotmanager/boom

For the latest version, to contribute, and for more information, please visit
the project pages or join the mailing list.

To clone the current main (development) branch run:

```
git clone git://github.com/snapshotmanager/boom.git
```
## Reporting bugs

Please report bugs via the mailing list or by opening an issue in the [GitHub
Issue Tracker][2]

## Mailing list

The [dm-devel][3] is the mailing list for any boom-related questions and
discussion. Patch submissions and reviews are welcome too.

## Building and installing Boom

A `setuptools` based build script is provided: local installations and
package builds can be performed by running `python setup.py` and a
setup command. See `python setup.py --help` for detailed information on
the available options and commands.

### Builds and packages
Binary packages for Fedora and Red Hat Enterprise Linux are available
from the distribution repositories.

Red Hat Enterprise Linux 7:

```
# yum -y install lvm2-python-boom
```

Red Hat Enterprise Linux 8 and Fedora:

```
# dnf -y install boom-boot
```

## The boom command

The `boom` command is the main interface to the boom boot manager.
It is able to create, delete, edit and display boot entries,
operating system and host profiles and provides reports showing the
available profiles and entries, and their configurations.

Boom commands normally operate on a particular object type: a boot
entry, a host profile or an OS profile. Commands are also provided
to manipulate legacy boot loader configurations (for systems that
do not natively support the BLS standard).

```
# boom [entry] <command> <options> # `BootEntry` command
```

```
# boom profile <command> <options> # `OsProfile` command
```

```
# boom hostprofile <command> <options> # `HostProfile` command
```

```
# boom legacy <command> <options> # Legacy boot loader commands
```

If no command type is given `entry` is assumed.

### Profiles and Boot Entries

The two main object types in boom are the `Profile` and `BootEntry`.
Profiles support tailoring boot entry configuration to either a
specific operating system distribution (`OsProfile`), or a specific
installation (`HostProfile`, based on the system `machine-id`).

Boom stores boot loader entries (`BootEntry`) in the system BLS loader
directory - normally `/boot/loader/entries`.

Boom `OsProfile` files are stored in the boom configuration directory,
`/boot/boom/profiles` and `HostProfile` data is found in
`/boot/boom/hosts`.

The location of the boot file system may be overridden using the
`--boot-dir` command line option and the location of both the boot
file system and boom configuration directory may be overridden by
calling the `boom.set_boot_path()` and `boom.set_boom_path()`
functions.

These options are primarily of use for testing, or for working with
boom data from a system other than the running host.

Boom configuration data is stored in the `/boot` file system to permit
the tool to be run from any booted instance of any installed operating
system.

#### OsProfile

An `OsProfile` stores identity information and templates used to write
bootloader configurations for an instance of an operating system. The
identity is based on values from the `/etc/os-release` file, and the
available templates allow customisation of the kernel and initramfs
images, kernel options and other properties required to boot an instance
of that OS.

A set of `OsProfile` files can be pre-installed with boom, or generated
using the command line tool.

An `OsProfile` is uniquely identified by its *OS Identifier*, or
*os_id*, a SHA2 hash computed on the `OsProfile` identity fields.
All SHA identifiers are displayed by default using the minimum width
necessary to ensure uniqueness: all command line arguments accepting
an identifier also accept any unique prefix of a valid identifier.

##### OsProfile templates

The template properties of an `OsProfile` (kernel pattern, initramfs
pattern, LVM2 and BTRFS root options and kernel command line options)
may include format strings that are expanded when creating a new
``BootEntry``.

The available keys are:

  * `%{version}` - the kernel version
  * `%{lvm_root_lv}` - the LVM2 logical volume containing the root file
    system in `vg/lv` notation.
  * `%{btrfs_subvol_id}` - the BTRFS subvolume identifier to use.
  * `%{btrfs_subvol_path}` - the BTRFS subvolume path to use.
  * `%{root_device}` - The system root device, relative to `/`.
  * `%{options}` - Kernel command line options, including the root
    device specification and options.

Default template values are supplied when creating a new `OsProfile`;
these can be overridden by specifying alternate values on the command
line. The defaults are suitable for most Linux operating systems but
can be customised to allow for particular OS requirements, or to set
custom behaviours.

#### HostProfile

A `HostProfile` provides an additional means to customise the boot
configuration on a per-installation basis. Use of host profiles is
optional: if no `HostProfile` exits for a given host then the
default values from the corresponding `OsProfile` are used.

Values specified in a Boom `HostProfile` are automatically applied
whenever a boot entry for the corresponding `machine-id` is created
or edited. Multiple Boom `HostProfile` templates can be defined for
a given system and distinguished by a *label*: for example
'production', 'debug' or other profile labels used to identify
and group commonly-used sets of boot options.

Host profiles can be used to add or remove kernel command line
options, or to modify existing template values provided by the
`OsProfile` (including the location and naming of the kernel,
initramfs and other boot images). This can be used to automatically
apply settings where required, for example adding `nomodeset` or
other kernel command line parameters if required for that
installation, or modifying the command line to enable or disable
debugging, logging or storage activation options.

Like the `OsProfile`, a `HostProfile` is uniquely identified by
a `HostId` identifier.

#### BootEntry

A `BootEntry` is an individual bootloader entry for one instance of an
operating system. It includes all the parameters required for the
boot loader to load the OS, and for the kernel and user space to
boot the environment (including configuration of LVM2 logical volumes
and BTRFS subvolumes).

The `BootEntry` stored on-disk is generated from the templates stored
in an associated `OsProfile` and boot parameters configuration provided
by command line arguments.

Boom uses BLS[0] notation as the canonical format for the boot entry
store.

An `BootEntry` is uniquely identified by its *Boot Identifier*, or
*boot_id*, a SHA2 hash computed on the `BootEntry` boot parameter
fields (note that this means that changing the parameters of an
existing `BootEntry` will also change its `boot_id`. All SHA
identifiers are displayed by default using the minimum width
necessary to ensure uniqueness: all command line arguments
accepting an identifier also accept any unique prefix of a valid
identifier.

### Boom subcommands

For both profile and boot entry command types, boom provides six
subcommands:

  * `create`
  * `delete --profile OS_ID | --host-profile HOST_ID | --boot-id BOOT_ID [...]`
  * `clone --profile OS_ID | --host-profile HOST_ID | --boot-id BOOT_ID [...]`
  * `show`
  * `list`
  * `edit`

#### create

Create a new `OsProfile` `HostProfile`, or `BootEntry` using the
values entered on the command line.

#### delete

Delete the specified profile or BootEntry.

#### clone

Create a new profile or `BootEntry` by cloning an existing object
and modifying its properties. A `boot_id`, `os_id` or `host_id`
must be used to select the object to clone. Any remaining command
line options modify the newly created object.

#### show

Display the specified objects in human readable format.

#### list

List objects matching selection criteria as a tabular report.

#### edit

Modify an existing profile or `BootEntry` by changing one or more
of its attributes.

It is not possible to change the name, short name, version, or
version identifier of an `OsProfile` using this command, since these
fields form the `OsProfile` identifier: to modify one of these
fields use the `clone` command to create a new profile specifying
the attribute to be changed.

When editing a BootEntry, the `boot_id` will change: this is
because the options that define an entry form the entry's identity.
The new `boot_id` is written to the terminal on success.

### Boot image cache

Boom can optionally back up the boot images used by a boom BootEntry
so that the entry can still be used if an operating system update
removes the kernel or initramfs image used.

To use backup images the boot image cache must be enabled in the
`boom.conf` configuration file and the `--backup` option should
be given to the `boom entry` `create`, `edit`, or `clone`
subcommands.

When `--backup` is used boom will make a copy of each boot image
used by the new entry by adding a '.boomN' suffix (where `N` is a
number) to the file name. The new BootEntry uses the backup copy
of the image rather than the original file name.

If the `auto_clean` configuration option is set cache entries are
automatically removed when they are no longer in use by any
BootEntry.

#### boom cache command

The `boom cache` command gives information about the paths and
images stored in the boom boot image cache. The `boom cache list`
command gives information on cache entries in a tabular report
format similar to other `list` commands.

Detailed information on selected cache entries is provided by the
`boom cache show` command.

### Reporting commands

The `boom entry list` and `boom host|profile list`, and `boom cache
list` commands generate a tabular report as output. To control the
list of displayed fields use the `-o/--options FIELDS` argument:

```
boom list -oboot_id,version
BootId  Version
fb3286f 3.10-1.el7.fc24.x86_64
1031ab0 3.10-23.el7
a559d3a 2.6.32-232.el6
a559d3a 2.6.32-232.el6
2c89556 2.2.2-2.fc24.x86_64
e79db6a 1.1.1-1.fc24.x86_64
d85f2c3 3.10.1-1.el7
2fc3f4f 4.1.1-100.fc24
d85f2c3 3.10.1-1.el7
```

To add extra fields to the default selection, prefix the field list
with the `+` character:

```
boom list -o+kernel,initramfs
BootID  Version                  OsID    Name                            OsVersion   Kernel                               Initramfs
fb3286f 3.10-1.el7.fc24.x86_64   3fc389b Red Hat Enterprise Linux Server 7.2 (Maipo) /boot/vmlinuz-3.10-1.el7.fc24.x86_64 /boot/initramfs-3.10-1.el7.fc24.x86_64.img
1031ab0 3.10-23.el7              3fc389b Red Hat Enterprise Linux Server 7.2 (Maipo) /boot/vmlinuz-3.10-23.el7            /boot/initramfs-3.10-23.el7.img
a559d3a 2.6.32-232.el6           98c3edb Red Hat Enterprise Linux Server 6 (Server)  /boot/kernel-2.6.32-232.el6          /boot/initramfs-2.6.32-232.el6.img
a559d3a 2.6.32-232.el6           98c3edb Red Hat Enterprise Linux Server 6 (Server)  /boot/kernel-2.6.32-232.el6          /boot/initramfs-2.6.32-232.el6.img
d85f2c3 3.10.1-1.el7             3fc389b Red Hat Enterprise Linux Server 7.2 (Maipo) /boot/vmlinuz-3.10.1-1.el7           /boot/initramfs-3.10.1-1.el7.img
d85f2c3 3.10.1-1.el7             3fc389b Red Hat Enterprise Linux Server 7.2 (Maipo) /boot/vmlinuz-3.10.1-1.el7           /boot/initramfs-3.10.1-1.el7.img
e19586b 7.7.7                    3fc389b Red Hat Enterprise Linux Server 7.2 (Maipo) /boot/vmlinuz-7.7.7                  /boot/initramfs-7.7.7.img
```

```
boom list -o+title
BootID  Version                  Name                     RootDevice                                    Title
635ed15 6.8.9-300.fc40.x86_64    Fedora Linux             /dev/mapper/fedora-root                       Fedora Linux (6.8.9-300.fc40.x86_64) 40 (Server Edition)
995b87e 6.8.9-300.fc40.x86_64    Fedora Linux             /dev/fedora/root-snapset_upgrade_1719340050_- Snapshot upgrade 2024-06-25 19:27:30 (6.8.9-300.fc40.x86_64)
029c307 6.8.9-300.fc40.x86_64    Fedora Linux             /dev/fedora/root                              Revert upgrade 2024-06-25 19:27:30 (6.8.9-300.fc40.x86_64)
```

To display the available fields for either report use the field
name `help`.

`BootEntry` fields:
```
boom list -o help
Boot loader entries Fields
--------------------------
  bootid        - Boot identifier [sha]
  title         - Entry title [str]
  options       - Kernel options [str]
  kernel        - Kernel image [str]
  initramfs     - Initramfs image [str]
  machineid     - Machine identifier [sha]

OS profiles Fields
------------------
  osid          - OS identifier [sha]
  osname        - OS name [str]
  osshortname   - OS short name [str]
  osversion     - OS version [str]
  osversion_id  - Version identifier [str]
  unamepattern  - UTS name pattern [str]
  kernelpattern - Kernel image pattern [str]
  initrdpattern - Initrd pattern [str]
  lvm2opts      - LVM2 options [str]
  btrfsopts     - BTRFS options [str]
  options       - Kernel options [str]

Boot parameters Fields
----------------------
  version       - Kernel version [str]
  rootdev       - Root device [str]
  rootlv        - Root logical volume [str]
  subvolpath    - BTRFS subvolume path [str]
  subvolid      - BTRFS subvolume ID [num]
```

`OsProfile` fields:
```
boom profile list -o help
OS profiles Fields
------------------
  osid          - OS identifier [sha]
  osname        - OS name [str]
  osshortname   - OS short name [str]
  osversion     - OS version [str]
  osversion_id  - Version identifier [str]
  unamepattern  - UTS name pattern [str]
  kernelpattern - Kernel image pattern [str]
  initrdpattern - Initrd pattern [str]
  lvm2opts      - LVM2 options [str]
  btrfsopts     - BTRFS options [str]
  options       - Kernel options [str]
```

`HostProfile` fields:
```
boom host list -o help
Host profiles Fields
--------------------
  hostid        - Host identifier [sha]
  machineid     - Machine identifier [sha]
  osid          - OS identifier [sha]
  hostname      - Host name [str]
  label         - Host label [str]
  kernelpattern - Kernel image pattern [str]
  initrdpattern - Initrd pattern [str]
  lvm2opts      - LVM2 options [str]
  btrfsopts     - BTRFS options [str]
  options       - Kernel options [str]
  profilepath   - On-disk profile path [str]
  addopts       - Added Options [str]
  delopts       - Deleted Options [str]
```

`Cache` fields:
```
Cache entries Fields
--------------------
  imgid       - Image identifier [sha]
  path        - Image path [str]
  mode        - Path mode [str]
  uid         - User ID [num]
  gid         - Group ID [num]
  ts          - Timestamp [num]
  state       - State [str]
  count       - Use Count [num]
```

#### JSON report output

The reporting commands can also produce output in JSON notation. The
output is an array of JSON objects mapping field names to values. The
full field name including the type prefix is used to ensure keys are
unambiguous.

```
# boom list --json
{
    "Entries": [
        {
            "entry_bootid": "635ed15b411495cffa0c1eece74d3756278f484a",
            "param_version": "6.8.9-300.fc40.x86_64",
            "profile_osname": "Fedora Linux",
            "param_rootdev": "/dev/mapper/fedora-root"
        },
        {
            "entry_bootid": "995b87eac66fa6b4507e4c5dbd8a30e196b13e2c",
            "param_version": "6.8.9-300.fc40.x86_64",
            "profile_osname": "Fedora Linux",
            "param_rootdev": "/dev/fedora/root-snapset_upgrade_1719340050_-"
        },
        {
            "entry_bootid": "029c3078f83df79bfc2240223c6f79c648b2fce3",
            "param_version": "6.8.9-300.fc40.x86_64",
            "profile_osname": "Fedora Linux",
            "param_rootdev": "/dev/fedora/root"
        }
    ]
}
```

To include all fields for a given prefix use the special field name
`all`:

```
# boom list --json -o+entry_all,param_all,profile_all
{
    "Entries": [
        {
            "entry_bootid": "635ed15b411495cffa0c1eece74d3756278f484a",
            "param_version": "6.8.9-300.fc40.x86_64",
            "profile_osname": "Fedora Linux",
            "param_rootdev": "/dev/mapper/fedora-root",
            "entry_title": "Fedora Linux (6.8.9-300.fc40.x86_64) 40 (Server Edition)",
            "entry_options": "root=/dev/mapper/fedora-root ro rd.lvm.lv=fedora/root rhgb quiet ",
            "entry_kernel": "/vmlinuz-6.8.9-300.fc40.x86_64",
            "entry_initramfs": "/initramfs-6.8.9-300.fc40.x86_64.img",
            "entry_machineid": "5d1e621b0c1349aea3bd47e4bb619024",
            "entry_entrypath": "/boot/loader/entries/5d1e621b0c1349aea3bd47e4bb619024-6.8.9-300.fc40.x86_64.conf",
            "entry_entryfile": "5d1e621b0c1349aea3bd47e4bb619024-6.8.9-300.fc40.x86_64.conf",
            "entry_readonly": true,
            "param_rootlv": "fedora/root",
            "param_subvolpath": "",
            "param_subvolid": -1,
            "profile_osid": "5ea08f4d8c4d6fbdfdb2c0b79829e7ff4dfce7d4",
            "profile_osshortname": "fedora",
            "profile_osversion": "40 (Server Edition)",
            "profile_osversion_id": "40",
            "profile_unamepattern": "fc40",
            "profile_kernelpattern": "/vmlinuz-%{version}",
            "profile_initrdpattern": "/initramfs-%{version}.img",
            "profile_lvm2opts": "rd.lvm.lv=%{lvm_root_lv}",
            "profile_btrfsopts": "rootflags=%{btrfs_subvolume}",
            "profile_options": "root=%{root_device} ro %{root_opts} rhgb quiet",
            "profile_profilepath": "/boot/boom/profiles/5ea08f4d8c4d6fbdfdb2c0b79829e7ff4dfce7d4-fedora40.profile"
        }
    ]
}
```

### Getting help

Help is available for the `boom` command and each command line option.

Run the command with `--help` to display the full usage message:

```
# boom --help
```

## Configuring Boom

### Creating an OsProfile
To automatically generate boot configuration Boom needs an *Operating
System Profile* for the system(s) for which it will create entries.

And *OsProfile* is a collection of attributes that describe the OS
identity and provide templates for boot loader entries.

The identity information comprising an `OsProfile` is taken from the
`os-release` file for the distribution. Additional properties,
such as the UTS release pattern to match for the distribution,
are either provided on the boom command line or are set to default
values.

To create an `OsProfile` for the running system, use the
`-H/--from-host'` command line option:

```
# boom profile create --from-host --uname-pattern fc26
Created profile with os_id d4439b7:
  OS ID: "d4439b7d2f928c39f1160c0b0291407e5990b9e0",
  Name: "Fedora", Short name: "fedora",
  Version: "26 (Workstation Edition)", Version ID: "26",
  UTS release pattern: "fc26",
  Kernel pattern: "/kernel-%{version}", Initramfs pattern: "/initramfs-%{version}.img",
  Root options (LVM2): "rd.lvm.lv=%{lvm_root_lv}",
  Root options (BTRFS): "rootflags=%{btrfs_subvolume}",
  Options: "root=%{root_device} ro %{root_opts}"
```

The `--uname-pattern` `OsProfile` property is an optional but recommended
pattern (regular expression) that should match the UTS release (`uname`)
strings reported by the operating system.

The uname pattern is used when an on-disk boot loader entry is found that
does not contain an OS identifier (for e.g. a manually edited entry, or
one created by a different program).

### Creating a HostProfile
Boom can optionally apply further customisation to the boot entries
it creates by defining a *HostProfile*. The host profile can be used
to modify the templates (boot image names and paths, boot entry
titles, kernel command line options etc) provided by the `OsProfile`.

To create a new host profile for the current system use the
`host create` command, specifying the parameters to modify. For
example, to create a new host profile for a system running Fedora 30
that adds the "debug" kernel command line argument, and removes the
"rhgb" and "quiet" arguments run:

```
boom profile list --name Fedora --osversionid 30
OsID    Name                     OsVersion               
8896596 Fedora                   30 (Workstation Edition)

boom host create --profile 8896596 --add-opts debug --del-opts "rhgb quiet"
Created host profile with host_id ff4266a:
  Host ID: "ff4266a7a0ceac789d65df75a1edd47b832dd9c5",
  Host name: "localhost.localdomain",
  Machine ID: "653b444d513a43239c37deae4f5fe644",
  OS ID: "8896596a45fcc9e36e9c87aee77ab3e422da2635",
  Add options: "debug", Del options: "rhgb quiet",
  Name: "Fedora", Short name: "fedora", Version: "30 (Workstation Edition)",
  Version ID: "30", UTS release pattern: "fc30",
  Kernel pattern: "/vmlinuz-%{version}", Initramfs pattern: "/initramfs-%{version}.img",
  Root options (LVM2): "rd.lvm.lv=%{lvm_root_lv}",
  Root options (BTRFS): "rootflags=%{btrfs_subvolume}",
  Options: "root=%{root_device} ro %{root_opts}"
```

### Creating a BootEntry
To create a new boot entry using an existing `OsProfile`, use the
`boom create` command, specifying the `OsProfile` using its assigned
identifier:

```
# boom profile list --short-name rhel
OsID    Name                            OsVersion
98c3edb Red Hat Enterprise Linux Server 6 (Server)
c0b921e Red Hat Enterprise Linux Server 7 (Server)

# boom create --profile 3fc389b --title "RHEL7 snapshot" --version 3.10-272.el7 --root-lv vg00/lvol0-snap
Created entry with boot_id a5aef11:
title RHEL7 snapshot
machine-id 611f38fd887d41dea7eb3403b2730a76
version 3.10-272.el7
linux /boot/vmlinuz-3.10-272.el7
initrd /boot/initramfs-3.10-272.el7.img
options root=/dev/vg00/lvol0-snap ro rd.lvm.lv=vg00/lvol0-snap rhgb quiet
```

Once the entry has been created it will appear in the boot loader
menu as configured:

```
      Red Hat Enterprise Linux Server (3.10.0-327.el7.x86_64) 7.2 (Maipo)
      Red Hat Enterprise Linux Server (3.10.0-272.el7.x86_64) 7.2 (Maipo)
      RHEL7 Snapshot











      Use the ↑ and ↓ keys to change the selection.
      Press 'e' to edit the selected item, or 'c' for a command prompt.
```

If creating an entry for the currently running kernel version, and the
OsProfile of the running host, these options can be omitted from the
create command:

```
# boom create --title "Fedora 26 snapshot" --root-lv vg_hex/root-snap-f26
Created entry with boot_id d12c177:
  title Fedora 26 snapshot
  machine-id 611f38fd887d41dea7eb3403b2730a76
  version 4.13.5-200.fc26.x86_64
  linux /kernel-4.13.5-200.fc26.x86_64
  initrd /initramfs-4.13.5-200.fc26.x86_64.img
  options root=/dev/vg_hex/root-snap-f26 ro rd.lvm.lv=vg_hex/root-snap-f26
```

```
      Red Hat Enterprise Linux Server (3.10.0-327.el7.x86_64) 7.2 (Maipo)
      Red Hat Enterprise Linux Server (3.10.0-272.el7.x86_64) 7.2 (Maipo)
      Fedora 26 snapshot (4.13.5-200.fc26.x86_64)
      RHEL7 Snapshot











      Use the ↑ and ↓ keys to change the selection.
      Press 'e' to edit the selected item, or 'c' for a command prompt.
```
## Grub2 Integration

Support for the [BootLoader Specification][0] is enabled by default in
supported distributions beginning with Fedora 30 and Red Hat Enterprise Linux
8. No special steps are required to enable BLS for boot configuration on these
distributions.

### Submenu support

Previous versions of boom for distributions that included support for BLS but
did not enable it by default allowed boom-managed boot entries to be placed
into a separate Grub2 submenu. This is no longer possible with distributions
that use BLS by default since there is no way to separately load the boom
managed entries into a Grub2 submenu. Support for configuring this option was
removed in boom-1.4.

## Python API
Boom also supports programmatic use via a Python API. The API is flexible
and allows greater customisation than is possible using the command line
tool.

Two interfaces are provided: a procedural command-driven interface that
closely mimics the command line tool (the boom CLI is implemented using
this interface), and a native object interface that provides complete
access to boom's capabilities and full control over boom `OsProfile`
`BootEntry`, and `BootParams` objects. User-defined tabular reports
may also be created using the `boom.report` module.

### Command API
The command API is implemented in the `boom.command` sub-module. Programs
wishing to use the command API can just import this module:

```
import boom.command
```

The command API is [documented][7] at [readthedocs.org][6].

### Object API
The object API is implemented in several `boom` sub-modules:

  * `boom`
  * `boom.bootloader`
  * `boom.cache`
  * `boom.command`
  * `boom.config`
  * `boom.hostprofile`
  * `boom.legacy`
  * `boom.osprofile`
  * `boom.report`


Applications using the object API need only import the sub-modules that
contain the needed interfaces.

The object API is [documented][8] at [readthedocs.org][6].

## Patches and pull requests

Patches can be submitted via the mailing list or as GitHub pull requests. If
using GitHub please make sure your branch applies to the current main as a
'fast forward' merge (i.e. without creating a merge commit). Use the `git
rebase` command to update your branch to the current main branch if
necessary.

## Documentation

API [documentation][4] is automatically generated using [Sphinx][5]
and [Read the Docs][6].

Installation and user documentation will be added in a future update.

 [0]: https://systemd.io/BOOT_LOADER_SPECIFICATION
 [1]: https://github.com/snapshotmanager/snapshot-boot-docs
 [2]: https://github.com/snapshotmanager/boom/issues
 [3]: https://www.redhat.com/mailman/listinfo/dm-devel
 [4]: https://boom.readthedocs.org/en/latest/index.html#
 [5]: http://sphinx-doc.org/
 [6]: https://www.readthedocs.org/
 [7]: https://boom.readthedocs.io/en/latest/boom.html#module-boom.command
 [8]: https://boom.readthedocs.io/en/latest/boom.html
