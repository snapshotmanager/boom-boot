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

  * http://github.com/bmr-cymru/boom

For the latest version, to contribute, and for more information, please visit
the project pages or join the mailing list.

To clone the current master (development) branch run:

```
git clone git://github.com/bmr-cymru/boom.git
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

### Building an RPM package

To build a binary RPM package for the current distribution, use the
`bdist_rpm` build command:

```
$ python setup.py bdist_rpm
```

On success an RPM package will be written to the `dist/` directory.

Note that due to limitations in `setuptools` it is not possible for
the packages built by this method to install the Grub2 integration
scripts to the `/etc` directory.

To enable automatic inclusion of Boom boot entries when the Grub2
configuration script runs, execute the following commands as root
from the Boom source directory:

```
# cp etc/default/boom /etc/default
# cp etc/grub.d/42_boom /etc/grub.d
```
## The boom command

The `boom` command is the main interface to the boom boot manager.
It is able to create, delete, edit and display boot entries and
operating system profiles and provides reports showing the available
profiles and entries, and their configurations.

All `boom` commands operate on either an *OsProfile* or a *BootEntry*:

```
# boom profile <command> <options> # `OsProfile` command
```

```
# boom [entry] <command> <options> # `BootEntry` command
```

If no command type is given `entry` is assumed.

### Operating System Profiles and Boot Entries

The two main object types in boom are the `OsProfile` and `BootEntry`.

Boom stores boot loader entries (`BootEntry`) in the system BLS loader
directory - normally `/boot/loader/entries`.

Boom `OsProfile` files are stored in the boom configuration directory,
`/boot/boom/profiles`.

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

For each type, boom provides six subcommands:

  * `create`
  * `delete --profile OS_ID | --boot-id BOOT_ID [...]`
  * `clone --profile OS_ID | --boot-id BOOT_ID [...]`
  * `show`
  * `list`
  * `edit`

#### create

Create a new `OsProfile` or `BootEntry` using the values entered on
the command line.

#### delete

Delete the specified `OsProfile` or BootEntry.

#### clone

Create a new `OsProfile` or `BootEntry` by cloning an existing object
and modifying its properties. A `boot_id` or `os_id` must be used
to select the object to clone. Any remaining command line options
modify the newly created object.

#### show

Display the specified objects in human readable format.

#### list

List objects matching selection criteria as a tabular report.

#### edit

Modify an existing `OsProfile` or `BootEntry` by changing one or
more of its attributes.

It is not possible to change the name, short name, version, or
version identifier of an `OsProfile` using this command, since these
fields form the `OsProfile` identifier: to modify one of these
fields use the `clone` command to create a new profile specifying
the attribute to be changed.

When editing a BootEntry, the `boot_id` will change: this is
because the options that define an entry form the entry's identity.
The new `boot_id` is written to the terminal on success.

### Reporting commands

The `boom entry list` and `boom profile list` commands generate a
tabular report as output. To control the list of displayed fields
use the `-o/--options FIELDS` argument:

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
# boom profile create --from-host --uname-pattern fc24
Created profile with os_id 9cb53dd:
OS ID: "9cb53ddda889d6285fd9ab985a4c47025884999f",
Name: "Fedora", Short name: "fedora",
Version: "24 (Workstation Edition)", Version ID: "24",
UTS release pattern: "fc24",
Kernel pattern: "/boot/kernel-%{version}", Initramfs pattern: "/boot/initramfs-%{version}.img",
Root options (LVM2): "rd.lvm.lv=%{lvm_root_lv}",
Root options (BTRFS): "rootflags=%{btrfs_subvolume}",
Options: "root=%{root_device} ro %{root_opts}"

```

The `--uname-pattern` `OsProfile` property is an otional but recommended
pattern (regular expression) that should match the UTS release (`uname`)
strings reported by the operating system.

The uname pattern is used when an on-disk boot loader entry is found that
does not contain an OS identifier (for e.g. a manually edited entry, or
one created by a different program).

### Creating a BootEntry
To create a new boot entry using an existing `OsProfile`, use the
`boom create` command, specifying the `OsProfile` using its assigned
identifier:

```
# boom profile list --short-name rhel
OsID    Name                            OsVersion
3fc389b Red Hat Enterprise Linux Server 7.2 (Maipo)
98c3edb Red Hat Enterprise Linux Server 6 (Server)
c0b921e Red Hat Enterprise Linux Server 7 (Server)

# boom create --profile 3fc389b --title "RHEL7 snapshot" --version 3.10-272.el7 --rootlv vg00/lvol0-snap
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

## Grub2 Integration

Boom includes scripts to integrate with versions of `grub2` that support
the BLS extension (including the builds of Grub shipped with Fedora and
Red Hat Enterprise Linux).

The scripts support optionally placing all boom-managed entries into a
separate named submenu.

### Submenu support

To place all boom-managed boot entries into a separate submenu edit the
file `/etc/default/boom` and set the `BOOM_USE_SUBMENU` variable to `yes`:

```
BOOM_USE_SUBMENU="yes"
```

To change the name of the submenu modify the `BOOM_SUBMENU_NAME` variable:

```
BOOM_SUBMENU_NAME="Snapshots"
```

After modifying the file run the `grub2-mkconfig` program to update the
Grub boot loader configuration.

If submenu support is enabled a new entry (named `Snapshots` in this
example) will appear at the bottom of the main Grub2 menu:

```
      Red Hat Enterprise Linux Server (3.10.0-327.el7.x86_64) 7.2 (Maipo)
      Red Hat Enterprise Linux Server (3.10.0-272.el7.x86_64) 7.2 (Maipo)
      Snapshots











      Use the ↑ and ↓ keys to change the selection.
      Press 'e' to edit the selected item, or 'c' for a command prompt.
```

Hitting `enter` on the submenu item will display the available boom
boot entries:

```
      RHEL7 Snapshot (3.10.0-327.el7.x86_64) 2017-10-10
      RHEL7 Snapshot (3.10.0-327.el7.x86_64) 2017-10-01
      RHEL7 Snapshot (3.10.0-272.el7.x86_64) 2017-09-20
      RHEL7 Snapshot (3.10.0-272.el7.x86_64) 2017-08-13
      Fedora 24 (4.11.12-100.fc24.x86_64)








      Use the ↑ and ↓ keys to change the selection.
      Press 'e' to edit the selected item, or 'c' for a command prompt.
      Press Escape to return to the previous menu.
```

## Python API
Boom also supports programatic use via a Python API. The API is flexible
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
  * `boom.osprofile`
  * `boom.report`

Applications using the object API need only import the sub-modules that
contain the needed interfaces.

The object API is [documented][8] at [readthedocs.org][6].

## Patches and pull requests

Patches can be submitted via the mailing list or as GitHub pull requests. If
using GitHub please make sure your branch applies to the current master as a
'fast forward' merge (i.e. without creating a merge commit). Use the `git
rebase` command to update your branch to the current master if necessary.

## Documentation

API [documentation][4] is automatically generated using [Sphinx][5]
and [Read the Docs][6].

Installation and user documentation will be added in a future update.

 [0]: https://www.freedesktop.org/wiki/Specifications/BootLoaderSpec/
 [1]: https://github.com/bmr-cymru/snapshot-boot-docs
 [2]: https://github.com/bmr-cymru/boom/issues
 [3]: https://www.redhat.com/mailman/listinfo/dm-devel
 [4]: https://boom.readthedocs.org/en/latest/index.html#
 [5]: http://sphinx-doc.org/
 [6]: https://www.readthedocs.org/
 [7]: https://boom.readthedocs.io/en/latest/boom.html#module-boom.command
 [8]: https://boom.readthedocs.io/en/latest/boom.html
