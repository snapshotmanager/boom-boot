# Copyright (C) 2017 Red Hat, Inc., Bryn M. Reeves <bmr@redhat.com>
#
# command.py - Boom BLS bootloader command interface
#
# This file is part of the boom project.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions
# of the GNU General Public License v.2.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

import boom
from boom.osprofile import OsProfile, load_profiles, write_profiles

from boom.report import (
    BoomField, BoomReportOpts, BoomReport,
    REP_STR, REP_INT, REP_SHA
)

from boom.bootloader import (
    load_entries, write_entries, find_entries,
    BootEntry, BootParams
)

import sys
from argparse import ArgumentParser


#
# Command driven API
#

def create_entry(title, version, machine_id, root_device, lvm_root_lv=None,
                 btrfs_subvol_path=None, btrfs_subvol_id=None, osprofile=None):
    """create_entry(title, version, machine_id, root_device, lvm_root_lv,
                    btrfs_subvol_path, btrfs_subvol_id, osprofile) -> str

        Create the specified boot entry in the configured loader directory.
        An error is raised if a matching entry already exists.

        :param title: the title of the new entry.
        :param version: the version string for the new entry.
        :param root_device: the root device path for the new entry.
        :param lvm_root_lv: an optional LVM2 root logical volume.
        :param btrfs_subvol_path: an optional BTRFS subvolume path.
        :param btrfs_subvol_id: an optional BTRFS subvolume id.
        :param osprofile: The ``OsProfile`` for this entry.
        :returns: a ``BootEntry`` object corresponding to the new entry.
        :returntype: ``BootEntry``
        :raises: ``ValueError`` if required values are missing or ``OsError``
                 if an error occurs while writing the entry file.
    """
    if not title:
        raise ValueError("Entry title cannot be empty.")

    if not version:
        raise ValueError("Entry version cannot be empty.")

    if not machine_id:
        raise ValueError("Entry machine_id cannot be empty.")

    if not root_device:
        raise ValueError("Entry requires a root_device.")

    if not osprofile:
        raise ValueError("Cannot create entry without OsProfile.")

    btrfs = any([btrfs_subvol_path, btrfs_subvol_id])

    bp = BootParams(version, root_device, lvm_root_lv=lvm_root_lv,
                    btrfs_subvol_path=btrfs_subvol_path,
                    btrfs_subvol_id=btrfs_subvol_id)

    be = BootEntry(title=title, machine_id=machine_id,
                   osprofile=osprofile, boot_params=bp)
    print(be.options)
    if find_entries(boot_id=be.boot_id):
        raise ValueError("Entry already exists (boot_id=%s)." % be.boot_id)

    be.write_entry()

    return be


def delete_entries(boot_id=None, title=None, version=None,
                   machine_id=None, root_device=None, lvm_root_lv=None,
                   btrfs_subvol_path=None, btrfs_subvol_id=None):
    """delete_entries(boot_id, title, version,
                      machine_id, root_device, lvm_root_lv,
                      btrfs_subvol_path, btrfs_subvol_id) -> int

        Delete the specified boot entry or entries from the configured
        loader directory. If ``boot_id`` is used, or of the criteria
        specified match exactly one entry, a single entry is removed.
        If ``boot_id`` is not used, and more than one matching entry
        is present, all matching entries will be removed.

        On success the number of entries removed is returned.

        :param boot_id: ``boot_id`` to match.
        :param title: title string to match.
        :param version: version to match.
        :param root_device: root device path to match.
        :param lvm_root_lv: LVM2 root logical volume to match.
        :param btrfs_subvol_path: BTRFS subvolume path to match.
        :param btrfs_subvol_id: BTRFS subvolume id to match.
        :returns: the number of entries removed.
        :returntype: ``int``
    """
    bes = find_entries(boot_id=boot_id, title=title, version=version,
                       machine_id=machine_id, root_device=root_device,
                       lvm_root_lv=lvm_root_lv,
                       btrfs_subvol_path=btrfs_subvol_path,
                       btrfs_subvol_id=btrfs_subvol_id)

    if not bes:
        raise IndexError("No matching entry found.")

    deleted = 0
    for be in bes:
        be.delete_entry()
        deleted += 1

    return deleted


def list_entries(boot_id=None, title=None, version=None,
                 machine_id=None, root_device=None, lvm_root_lv=None,
                 btrfs_subvol_path=None, btrfs_subvol_id=None):
    """list_entries(boot_id, title, version,
                    machine_id, root_device, lvm_root_lv,
                    btrfs_subvol_path, btrfs_subvol_id) -> list

        Return a list of ``boom.bootloader.BootEntry`` objects matching
        the given criteria.

        :param boot_id: ``boot_id`` to match.
        :param title: the title of the new entry.
        :param version: the version string for the new entry.
        :param root_device: the root device path for the new entry.
        :param lvm_root_lv: an optional LVM2 root logical volume.
        :param btrfs_subvol_path: an optional BTRFS subvolume path.
        :param btrfs_subvol_id: an optional BTRFS subvolume id.
        :param osprofile: The ``OsProfile`` for this entry.
        :returns: the ``boot_id`` of the new entry.
        :returntype: str
    """
    bes = find_entries(boot_id=boot_id, title=title, version=version,
                       machine_id=machine_id, root_device=root_device,
                       lvm_root_lv=lvm_root_lv,
                       btrfs_subvol_path=btrfs_subvol_path,
                       btrfs_subvol_id=btrfs_subvol_id)

    return bes


_entry_fields = [
    BoomField("boot_id", "Boot ID", 12, REP_SHA, lambda d: d.boot_id),
    BoomField("title", "Title", 56, REP_STR, lambda d: d.title),
    BoomField("title", "Version", 24, REP_STR, lambda d: d.version),
]

_entry_fields_verbose = [
    BoomField("kernel", "Kernel", 32, REP_STR, lambda d: d.linux),
    BoomField("initramfs", "Initramfs", 40, REP_STR, lambda d: d.initrd),
    BoomField("options", "Options", 52, REP_STR, lambda d: d.options),
    BoomField("machine_id", "Machine ID", 12, REP_SHA, lambda d: d.machine_id),
]


def print_entries(boot_id=None, title=None, version=None,
                  machine_id=None, root_device=None, lvm_root_lv=None,
                  btrfs_subvol_path=None, btrfs_subvol_id=None,
                  opts=None, out_file=None, fields=None):
    """print_entries(boot_id, title, version,
                    machine_id, root_device, lvm_root_lv,
                    btrfs_subvol_path, btrfs_subvol_id) -> list

        Return a list of ``boom.bootloader.BootEntry`` objects matching
        the given criteria.

        :param boot_id: ``boot_id`` to match.
        :param title: the title of the new entry.
        :param version: the version string for the new entry.
        :param root_device: the root device path for the new entry.
        :param lvm_root_lv: an optional LVM2 root logical volume.
        :param btrfs_subvol_path: an optional BTRFS subvolume path.
        :param btrfs_subvol_id: an optional BTRFS subvolume id.
        :param osprofile: The ``OsProfile`` for this entry.
        :returns: the ``boot_id`` of the new entry.
        :returntype: str
    """
    opts = BoomReportOpts() if not opts else opts

    if not out_file:
        out_file = sys.stdout

    if not fields:
        fields = _entry_fields

    bes = find_entries(boot_id=boot_id, title=title, version=version,
                       machine_id=machine_id, root_device=root_device,
                       lvm_root_lv=lvm_root_lv,
                       btrfs_subvol_path=btrfs_subvol_path,
                       btrfs_subvol_id=btrfs_subvol_id)

    br = BoomReport(out_file, title, _entry_fields, None)
    for be in bes:
        br.add_row_data(be)

    return br.output()


def make_default(boot_id=None, title=None, version=None,
                 machine_id=None, root_device=None, lvm_root_lv=None,
                 btrfs_subvol_path=None, btrfs_subvol_id=None):
    pass


#
# boom command line tool
#

boom_usage = """%(prog}s <command> [options]\n\n"
                create <title> <version> [--osprofile=os_id] [...]
                delete [title|version|boot_id|os_id]
                list [title|version|boot_id|os_id|root_device|machine_id]
             """


def main(args):
    parser = ArgumentParser(description="BooM Boot Manager")
    parser.add_argument("command", metavar="COMMAND", type=str, nargs=1,
                        help="The boom command to run")
    parser.add_argument("-t", "--title", metavar="TITLE", type=str, nargs=1,
                        help="The title of a boom boot entry")
    parser.add_argument("-v", "--version", metavar="VERSION", type=str,
                        nargs=1, help="The kernel version of a boom "
                        "boot entry")
    parser.add_argument("-b", "--boot-id", metavar="BOOT_ID", type=str,
                        nargs=1, help="The BOOT_ID of a boom boot entry")
    parser.add_argument("-o", "--os-profile", metavar="OS_ID", type=str,
                        nargs=1, help="A boom operating system profile "
                        "identifier")
    parser.add_argument("-r", "--root-device", metavar="ROOT", type=str,
                        nargs=1, help="The root device for a boot entry")
    parser.add_argument("-m", "--machine-id", metavar="MACHINE_ID", type=str,
                        nargs=1, help="The machine_id value to use")
    parser.parse_args()

# vim: set et ts=4 sw=4 :
