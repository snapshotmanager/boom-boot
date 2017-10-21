# Copyright (C) 2017 Red Hat, Inc., Bryn M. Reeves <bmr@redhat.com>
#
# bootloader.py - Boom BLS bootloader manager
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
"""The ``boom.bootloader`` module defines classes for working with
on-disk boot loader entries: the ``BootEntry`` class represents an
individual boot loader entry, and the ``BootParams`` class
encapsulates the parameters needed to boot an instance of the
operating system. The kernel version and root device configuration
of an existing ``BootEntry`` may be changed by modifying or
substituting its ``BootParams`` object (this may also be used to
'clone' configuration from one entry to another).

Functions are provided to read and write boot loader entries from an
on-disk store (normally located at ``/boot/loader/entries``), and to
retrieve particular ``BootEntry`` objects based on a variety of
selection criteria.

The ``BootEntry`` class includes named properties for each boot entry
attribute ("entry key"). In addition, the class serves as a container
type, allowing attributes to be accessed via dictionary-style indexing.
This simplifies iteration over a profile's key / value pairs and allows
straightforward access to all members in scripts and the Python shell.

All entry key names are made available as named members of the module:
``BOOT_ENTRY_*``, and the ``ENTRY_KEYS`` list. A map of Boom key names
to BLS keys is available in the ``KEY_MAP`` dictionary (a reverse map
is also provided in the ``MAP_KEY`` member).

"""
from boom import *
from boom.osprofile import *

from os.path import basename, exists as path_exists, join as path_join
from tempfile import mkstemp
from os import listdir, rename, fdopen, chmod, unlink
from hashlib import sha1
import logging
import re

#: The path to the BLS boot entries directory relative to /boot
ENTRIES_PATH = "loader/entries"

#: The format used to construct entry file names.
BOOT_ENTRIES_FORMAT = "%s-%s-%s.conf"

#: The file mode with which BLS entries should be created.
BOOT_ENTRY_MODE = 0o644

#: The ``BootEntry`` title key.
BOOT_TITLE = "BOOT_TITLE"
#: The ``BootEntry`` version key.
BOOT_VERSION = "BOOT_VERSION"
#: The ``BootEntry`` machine_id key.
BOOT_MACHINE_ID = "BOOT_MACHINE_ID"
#: The ``BootEntry`` linux key.
BOOT_LINUX = "BOOT_LINUX"
#: The ``BootEntry`` initrd key.
BOOT_INITRD = "BOOT_INITRD"
#: The ``BootEntry`` efi key.
BOOT_EFI = "BOOT_EFI"
#: The ``BootEntry`` options key.
BOOT_OPTIONS = "BOOT_OPTIONS"
#: The ``BootEntry`` device tree key.
BOOT_DEVICETREE = "BOOT_DEVICETREE"
#: The ``BootEntry`` boot identifier key.
BOOT_ID = "BOOT_ID"

#: An ordered list of all possible ``BootEntry`` keys.
ENTRY_KEYS = [
    # We require a title for each entry (BLS does not)
    BOOT_TITLE,
    # MACHINE_ID is optional in BLS, however, since the standard suggests
    # that it form part of the file name for compliant snippets, it is
    # effectively mandatory.
    BOOT_MACHINE_ID,
    BOOT_VERSION,
    # One of either BOOT_LINUX or BOOT_EFI must be present.
    BOOT_LINUX, BOOT_EFI,
    BOOT_INITRD, BOOT_OPTIONS,
    BOOT_DEVICETREE
]

#: Map Boom entry names to BLS keys
KEY_MAP = {
    BOOT_TITLE: "title",
    BOOT_VERSION: "version",
    BOOT_MACHINE_ID: "machine_id",
    BOOT_LINUX: "linux",
    BOOT_INITRD: "initrd",
    BOOT_EFI: "efi",
    BOOT_OPTIONS: "options",
    BOOT_DEVICETREE: "devicetree"
}

#: Map BLS entry keys to Boom names
MAP_KEY = {v: k for k, v in KEY_MAP.items()}

# Module logging configuration
_log = logging.getLogger(__name__)
_log.set_debug_mask(BOOM_DEBUG_ENTRY)

_log_debug = _log.debug
_log_debug_entry = _log.debug_masked
_log_info = _log.info
_log_warn = _log.warning
_log_error = _log.error

#: The global list of boot entries.
_entries = None

#: Pattern for forming root device paths from LVM2 names.
DEV_PATTERN = "/dev/%s"

def boom_entries_path():
    """Return the path to the boom profiles directory.

        :returns: The boom profiles path.
        :returntype: str
    """
    return path_join(get_boot_path(), ENTRIES_PATH)


class BootParams(object):
    """ The ``BootParams`` class encapsulates the information needed to
        boot an instance of the operating system: the kernel version,
        root device, and root device options.

        A ``BootParams`` object is used to configure a ``BootEntry``
        and to generate configuration keys for the entry based on an
        attached OsProfile.
    """
    #: The kernel version of the instance.
    version = None

    #: The path to the root device
    root_device = None

    #: The LVM2 logical volume containing the root file system
    lvm_root_lv = None

    #: The BTRFS subvolume path to be used as the root file system.
    btrfs_subvol_path = None

    #: The ID of the BTRFS subvolume to be used as the root file system.
    btrfs_subvol_id = None

    def __str(self, quote=False, prefix="", suffix=""):
        """Format BootParams as a string.

            Format this ``BootParams`` object as a string, with optional
            prefix, suffix, and value quoting.

            :param quote: A bool indicating whether to quote values.
            :param prefix: An optional prefix string to be concatenated
                           with the start of the formatted string.
            :param suffix: An optional suffix string to be concatenated
                           with the end of the formatted string.
            :returns: a formatted representation of this ``BootParams``.
            :returntype: string
        """
        bp_str = prefix

        fields = ["version", "root_device", "lvm_root_lv",
                  "btrfs_subvol_path", "btrfs_subvol_id"]
        params = (
            self.root_device,
            self.lvm_root_lv,
            self.btrfs_subvol_path, self.btrfs_subvol_id
        )

        # arg
        bp_str += self.version if not quote else '"%s"' % self.version
        bp_str += ", "

        # kwargs

        bp_fmt = "%s=%s, " if not quote else '%s="%s", '
        for fv in [fv for fv in zip(fields[1:], params) if fv[1]]:
            bp_str += bp_fmt % fv

        return bp_str.rstrip(", ") + suffix

    def __str__(self):
        """Format BootParams as a human-readable string.

            Format this ``BootParams`` object as a human-readable string.

            :returns: A human readable string representation of this
                      ``BootParams`` object.

            :returntype: string
        """
        return self.__str()

    def __repr__(self):
        """Format BootParams as a machine-readable string.

            Format this ``BootParams`` object as a machine-readable
            string. The string returned is in the form of a call to the
            ``BootParams`` constructor.

            :returns: a machine readable string represenatation of this
                      ``BootParams`` object.
        """
        return self.__str(quote=True, prefix="BootParams(", suffix=")")

    def __init__(self, version, root_device=None, lvm_root_lv=None,
                 btrfs_subvol_path=None, btrfs_subvol_id=None):
        """Initialise a new ``BootParams`` object.

            The root device is specified via the ``root_device``
            argument as a path relative to the root file system.

            The LVM2 logical volume containing the root file system is
            specified using ``lvm_root_lv`` if LVM2 is used.

            For instances using LVM2, if the ``lvm_root_lv`` argument is
            set and ``root_device`` is unset, ``root_device`` is assumed
            to be the normal path of the logical volume specified by the
            ``lvm_root_lv`` argument.

            For instances using BTRFS, the ``root_device`` argument is
            always required.

            Instances using BTRFS may select a subvolume to be mounted
            as the root file system by specifying either the subvolume
            path or id via ``btrfs_subvol_path`` and
            ``btrfs_subvol_id``.

            ``BootParams()`` raises ValueError if a required argument is
            missing, or if conflicting arguments are present.

            :param version: The version string for this BootParams
                            object.
            :param root_device: The root device for this BootParams
                                object.
            :param lvm_root_lv: The LVM2 logical volume containing the
                                root file system, for systems that use
                                LVM.
            :param btrfs_subvol_path: The BTRFS subvolume path
                                      containing the root file system,
                                      for systems using BTRFS.
            :param btrfs_subvol_id: The BTRFS subvolume ID containing
                                    the root file system, for systems
                                    using BTRFS.
            :returns: a newly initialised BootParams object.
            :returntype: class BootParams
            :raises: ValueError
        """
        if not version:
            raise ValueError("version argument is required.")

        self.version = version

        if root_device:
            self.root_device = root_device
        elif lvm_root_lv:
            self.root_device = DEV_PATTERN % lvm_root_lv
        else:
            raise ValueError("root_device is required.")

        if lvm_root_lv:
            self.lvm_root_lv = lvm_root_lv

        if btrfs_subvol_path and btrfs_subvol_id:
            raise ValueError("Only one of btrfs_subvol_path and "
                             "btrfs_subvol_id allowed.")

        if btrfs_subvol_path:
            self.btrfs_subvol_path = btrfs_subvol_path
        if btrfs_subvol_id:
            self.btrfs_subvol_id = btrfs_subvol_id

        _log_debug_entry("Initialised %s" % repr(self))

    @classmethod
    def from_entry(cls, be):
        """Recover BootParams from BootEntry.

        Recover BootParams values from a templated BootEntry: each
        key subject to template substitution is transformed into a
        regular expression, matching the element and capturing the
        corresponding BootParams value.

        A BootEntry object that has no attached OsProfile cannot be
        reversed since no templates exist to match the entry against:
        in this case None is returned but no exception is raised.
        The entry may be modified and re-written, but no templating
        is possible unless a new, valid, OsProfile is attached.

        :param be: The BootEntry to recover BootParams from.
        :returns: A newly initialised BootParams object.
        :returntype: ``BootParams``
        :raises: ValueError if expected values cannot be matched.
        """
        osp = be._osp
        # Version is written directly from BootParams
        version = be.version

        _log_debug_entry("Initialising BootParams() from "
                         "BootEntry(boot_id='%s')" % be.boot_id)

        # Decompose options first to obtain root device and options.
        options_regex = _key_regex_from_format(osp.options, capture=True)

        if not options_regex:
            return None

        _log_debug_entry("Matching options regex '%s' to '%s'" %
                         (options_regex, be.options))

        match = re.match(options_regex, be.options)
        if not match:
                raise ValueError("Cannot match BootEntry options")

        root_device = match.group(1)
        if len(match.groups()) == 2:
            root_opts = match.group(2)
        else:
            root_opts = None

        _log_debug_entry("Matched root_device='%s'" % root_device)

        lvm2_root_lv = None
        btrfs_root_opts = None
        btrfs_subvol_id = None
        btrfs_subvol_path = None

        # Decompose root opts to obtain BTRFS/LVM2 values
        if root_opts:
            lvm2_opts_regex = _key_regex_from_format(osp.root_opts_lvm2,
                                                     capture=True)
            btrfs_opts_regex = _key_regex_from_format(osp.root_opts_btrfs,
                                                      capture=True)

            match = re.search(lvm2_opts_regex, root_opts)
            if match:
                lvm2_root_lv=match.group(1)
                _log_debug_entry("Matched lvm2_root_lv='%s'" % lvm2_root_lv)

            match = re.search(btrfs_opts_regex, root_opts)
            if match:
                btrfs_root_opts=match.group(1)
                if "subvolid" in btrfs_root_opts:
                    subvolid_regex = r"subvolid=(\d*)"
                    match = re.match(subvolid_regex, btrfs_root_opts)
                    btrfs_subvol_id = match.group(1)
                    _log_debug_entry("Matched btrfs_subvol_id='%s'" %
                                     btrfs_subvol_id)
                elif "subvol" in btrfs_root_opts:
                    subvolpath_regex = r"subvol=(\S*)"
                    match = re.match(subvolpath_regex, btrfs_root_opts)
                    btrfs_subvol_path = match.group(1)
                    _log_debug_entry("Matched btrfs_subvol_path='%s'" %
                                     btrfs_subvol_path)
                else:
                    raise ValueError("Unrecognized btrfs root options: %s"
                                     % btrfs_root_opts)

        return BootParams(version, root_device=root_device,
                          lvm_root_lv=lvm2_root_lv,
                          btrfs_subvol_path=btrfs_subvol_path,
                          btrfs_subvol_id=btrfs_subvol_id)


def _add_entry(entry):
    """Add a new entry to the list of loaded on-disk entries.

        :param entry: The ``BootEntry`` to add.
    """
    global _entries
    if _entries is None:
        load_entries()
    if entry not in _entries:
        _entries.append(entry)


def _del_entry(entry):
    """Remove a ``BootEntry`` from the list of loaded entries.

        :param entry: The ``BootEntry`` to remove.
    """
    global _entries
    _entries.remove(entry)


def load_entries(machine_id=None):
    """ Load boot entries into memory.

        Load boot entries from ``boom.bootloader.boom_entries_path()``.

        If ``machine_id`` is specified only matching entries will be
        considered.

        :param machine_id: A ``machine_id`` value to match.
    """
    global _entries
    if not profiles_loaded():
        load_profiles()

    entries_path = boom_entries_path()

    _log_info("Loading boot entries from '%s'" % entries_path)
    _entries = []
    for entry in listdir(entries_path):
        if not entry.endswith(".conf"):
            continue
        if machine_id and machine_id not in entry:
            _log_debug_entry("Skipping entry with machine_id!='%s'",
                             machine_id)
            continue
        entry_path = path_join(entries_path, entry)
        try:
            _add_entry(BootEntry(entry_file=entry_path))
        except Exception as e:
            _log_warn("Could not load BootEntry '%s': %s" %
                      (entry_path, e))

    _log_info("Loaded %d entries" % len(_entries))


def write_entries():
    """Write out boot entries.

        Write all currently loaded boot entries to
        ``boom.bootloader.boom_entries_path()``.
    """
    global _entries
    for be in _entries:
        try:
            be.write_entry()
        except Exception as e:
            _log_warn("Could not write BootEntry(boot_id='%s'): %s" %
                      (be.disp_boot_id, e))


def min_boot_id_width():
    """Calculate the minimum unique width for boot_id values.

        Calculate the minimum width to ensure uniqueness when displaying
        boot_id values.

        :returns: the minimum boot_id width.
        :returntype: int
    """
    min_prefix = 7
    if not _entries:
        return min_prefix

    shas = set()
    for be in _entries:
        shas.add(be.boot_id)
    return _find_minimum_sha_prefix(shas, min_prefix)

def select_params(s, bp):
    """Test BootParams against Selection criteria.

        Test the supplied ``BootParams`` against the selection criteria
        in ``s`` and return ``True`` if it passes, or ``False``
        otherwise.

        :param bp: The BootParams to test
        :returntype: bool
        :returns: True if BootParams passes selection or ``False``
                  otherwise.
    """
    if s.root_device and s.root_device != bp.root_device:
        return False
    if s.lvm_root_lv and s.lvm_root_lv != bp.lvm_root_lv:
        return False
    if s.btrfs_subvol_path and s.btrfs_subvol_path != bp.btrfs_subvol_path:
        return False
    if s.btrfs_subvol_id and s.btrfs_subvol_id != bp.btrfs_subvol_id:
        return False

    return True

def select_entry(s, be):
    """Test BootEntry against Selection criteria.

        Test the supplied ``BootEntry`` against the selection criteria
        in ``s`` and return ``True`` if it passes, or ``False``
        otherwise.

        :param bp: The BootEntry to test
        :returntype: bool
        :returns: True if BootEntry passes selection or ``False``
                  otherwise.
    """
    if not select_profile(s, be._osp):
        return False

    if s.boot_id and not be.boot_id.startswith(s.boot_id):
        return False
    if s.title and be.title != s.title:
        return False
    if s.version and be.version != s.version:
        return False
    if s.machine_id and be.machine_id != s.machine_id:
        return False

    if not select_params(s, be.bp):
        return False

    return True


def find_entries(selection=None):
    """Find boot entries matching selection criteria.

        Return a list of ``BootEntry`` objects matching the specified
        criteria. Matching proceeds as the logical 'and' of all criteria.
        Criteria that are unset (``None``) are ignored.

        If no ``BootEntry`` matches the specified criteria the empty list
        is returned.

        Boot entries will be automatically loaded from disk if they are
        not already in memory.

        :param selection: A ``Selection`` object specifying the match
                          criteria for the operation.
        :returns: a list of ``BootEntry`` objects.
        :returntype: list
    """
    global _entries

    if not _entries:
        load_entries()

    matches = []

    # Use null search criteria if unspecified
    selection = selection if selection else Selection()

    selection.check_valid_selection(entry=True, params=True, profile=True)

    _log_debug_entry("Finding entries for %s" % repr(selection))

    for be in _entries:
        if select_entry(selection, be):
            matches.append(be)
    _log_debug_entry("Found %d entries" % len(matches))
    return matches


def _transform_key(key_name):
    """Transform key characters between Boom and BLS notation.

        Transform all occurrences of '_' in ``key_name`` to '-' or vice
        versa.

        Key names on-disk use a hyphen as the word separator, for e.g.
        "machine-id". We cannot use this character for Python attributes
        since it collides with the subtraction operator.

        :param key_name: The key name to be transformed.

        :returns: The transformed key name.

        :returntype: string
    """
    if "_" in key_name:
        return key_name.replace("_", "-")
    if "-" in key_name:
        return key_name.replace("-", "_")
    return key_name


class BootEntry(object):
    """A class representing a BLS compliant boot entry.

        A ``BootEntry`` exposes two sets of properties that are the
        keys of a BootLoader Specification boot entry.

        The properties of a ``BootEntry`` that is not associated with an
        ``OsProfile`` (for e.g. one read from disk) are the literal
        values read from a file or set through the API.

        When an ``OSProfile`` is attached to a ``BootEntry``, it is used
        as a template to fill out the values of keys for properties
        including the kernel and initramfs file name. This is used to
        create new ``BootEntry`` objects to be written to disk.

        An ``OsProfile`` can be attached to a ``BootEntry`` when it is
        created, or at a later time by calling the ``set_os_profile()``
        method.
    """
    _entry_data = None
    _unwritten = False
    _comments = None
    _osp = None
    bp = None

    def __str(self, quote=False, prefix="", suffix="", tail="\n",
              sep=" ", bls=True, no_boot_id=False):
        """Format BootEntry as a string.

            Return a human or machine readable representation of this
            BootEntry.

            :param quote: True if values should be quoted or False otherwise.

            :param prefix:An optional prefix string to be concatenated with
                          with the start of the formatted string.

            :param suffix: An optional suffix string to be concatenated
                           with the end of the formatted string.

            :param tail: A string to be concatenated between subsequent
                         records in the formatted string.

            :param sep: A separator to be inserted between each name and
                        value. Normally either ' ' or '='.

            :param bls: Generate output using BootLoader Specification
                        syntax and key names.

            :param no_boot_id: Do not include the BOOT_ID key in the
                               returned string. Used internally in
                               order to avoid recursion when calculating
                               the BOOT_ID checksum.

            :returns: A string representation.

            :returntype: string
        """
        be_str = prefix

        for key in [k for k in ENTRY_KEYS if getattr(self, KEY_MAP[k])]:
            attr = KEY_MAP[key]
            key_fmt = '%s%s"%s"' if quote else '%s%s%s'
            key_fmt += tail
            if bls:
                key_data = (_transform_key(attr), sep, getattr(self, attr))
            else:
                key_data = (key, sep, getattr(self, attr))
            be_str += key_fmt % key_data

        # BOOT_ID requires special handling to avoid recursion from the
        # boot_id property method (which uses the string representation
        # of the object to calculate the checksum).
        if not bls and not no_boot_id:
            key_fmt = ('%s%s"%s"' if quote else '%s%s%s') + tail
            boot_id_data = [BOOT_ID, sep, self.boot_id]
            if bls:
                boot_id_data[0] = _transform_key(BOOT_ID)
            be_str += key_fmt % tuple(boot_id_data)

        return be_str.rstrip(tail) + suffix

    def __str__(self):
        """Format BootEntry as a human-readable string in BLS notation.

            Format this BootEntry as a string containing a BLS
            configuration snippet.

            :returns: a BLS configuration snippet corresponding to this entry.

            :returntype: string
        """
        return self.__str()

    def __repr__(self):
        """Format BootEntry as a machine-readable string.

            Return a machine readable representation of this BootEntry,
            in constructor notation.

            :returns: A string in BootEntry constructor syntax.

            :returntype: str
        """
        return self.__str(quote=True, prefix="BootEntry(entry_data={",
                          suffix="})", tail=", ", sep=": ", bls=False)

    def __len__(self):
        """Return the length (key count) of this ``BootEntry``.

            :returns: the ``BootEntry`` length as an integer.
            :returntype: ``int``
        """
        return len(self._entry_data)

    def __getitem__(self, key):
        """Return an item from this ``BootEntry``.

            :returns: the item corresponding to the key requested.
            :returntype: the corresponding type of the requested key.
            :raises: TypeError if ``key`` is of an invalid type.
                     KeyError if ``key`` is valid but not present.
        """
        if not isinstance(key, str):
            raise TypeError("BootEntry key must be a string.")

        if key in self._entry_data:
            return self._entry_data[key]
        if key == BOOT_LINUX:
            return self.linux
        if key == BOOT_INITRD:
            return self.initrd
        if key == BOOT_OPTIONS:
            return self.options
        if key == BOOT_DEVICETREE:
            return self.devicetree
        if key == BOOT_EFI:
            return self.efi
        if key == BOOT_ID:
            return self.boot_id
        if self.bp and key == BOOT_VERSION:
            return self.bp.version

        raise KeyError("BootEntry key %s not present." % key)

    def __setitem__(self, key, value):
        """Set the specified ``BootEntry`` key to the given value.

            :param key: the ``BootEntry`` key to be set.
            :param value: the value to set for the specified key.
        """
        if not isinstance(key, str):
            raise TypeError("BootEntry key must be a string.")

        if key == BOOT_VERSION and self.bp:
            self.bp.version = value
        elif key == BOOT_LINUX and self.bp:
            self.linux = value
        elif key == BOOT_INITRD and self.bp:
            self.initrd = value
        elif key == BOOT_OPTIONS and self.bp:
            self.options = value
        elif key == BOOT_DEVICETREE and self.bp:
            self.devicetree = value
        elif key == BOOT_EFI and self.bp:
            self.efi = value
        elif key == BOOT_ID:
            raise TypeError("'boot_id' property does not support assignment")
        elif key in self._entry_data:
            self._entry_data[key] = value
        else:
            raise KeyError("BootEntry key %s not present." % key)

    def keys(self):
        """Return the list of keys for this ``BootEntry``.

            Return a copy of this ``BootEntry``'s keys as a list of
            key name strings.

            :returns: the current list of ``BotoEntry`` keys.
            :returntype: list of str
        """
        keys = list(self._entry_data.keys())
        add_keys = [BOOT_LINUX, BOOT_INITRD, BOOT_OPTIONS]

        # Sort the item list to give stable list ordering on Py3.
        keys = sorted(keys, reverse=True)

        if self.bp:
            add_keys.append(BOOT_VERSION)

        for k in add_keys:
            if k not in self._entry_data:
                keys.append(k)

        return keys

    def values(self):
        """Return the list of values for this ``BootEntry``.

            Return a copy of this ``BootEntry``'s values as a list.

            :returns: the current list of ``BotoEntry`` values.
            :returntype: list
        """
        values = list(self._entry_data.values())
        add_values = [self.linux, self.initrd, self.options]

        # Sort the item list to give stable list ordering on Py3.
        values = sorted(values, reverse=True)

        if self.bp:
            add_values.append(self.version)

        return values + add_values

    def items(self):
        """Return the items list for this BootEntry.

            Return a copy of this ``BootEntry``'s ``(key, value)``
            pairs as a list.

            :returns: the current list of ``BotoEntry`` items.
            :returntype: list of ``(key, value)`` tuples.
        """
        items = list(self._entry_data.items())

        add_items = [
            (BOOT_LINUX, self.linux),
            (BOOT_INITRD, self.initrd),
            (BOOT_OPTIONS, self.options)
        ]

        if self.bp:
            add_items.append((BOOT_VERSION, self.version))

        # Sort the item list to give stable list ordering on Py3.
        items = sorted(items, key=lambda i:i[0], reverse=True)

        return items + add_items

    def _dirty(self):
        """Mark this ``BootEntry`` as needing to be written to disk.

            A newly created ``BootEntry`` object is always dirty and
            a call to its ``write_entry()`` method will always write
            a new boot entry file. Writes may be avoided for entries
            that are not marked as dirty.

            A clean ``BootEntry`` is marked as dirty if a new value
            is written to any of its writable properties.

            :returntype: None
        """
        self._unwritten = True

    def __os_id_from_comment(self, comment):
        """Retrive OsProfile from BootEntry comment.

            Attempt to set this BootEntry's OsProfile using a comment
            string stored in the entry file. The comment must be of the
            form "OsIdentifier: <os_id>". If found the value is treated
            as authoritative and a reference to the corresponding
            ``OsProfile`` is stored  in the object's ``_osp`` member.

            Any comment lines that do not contain an OsIdentifier tag
            are returned as a multi-line string.

            :param comment: The comment to attempt to parse
            :returns: Comment lines not containing an OsIdentifier
            :returntype: str
        """
        if "OsIdentifier:" not in comment:
            return

        outlines = ""
        for line in comment.splitlines():
            (key, os_id) = line.split(":")
            os_id = os_id.strip()
            osp = get_os_profile_by_id(os_id)

            # An OsIdentifier comment is automatically added to the
            # entry when it is written: do not add the read value to
            # the comment list.
            if not self._osp and osp:
                self._osp = osp
                _log_debug_entry("Parsed os_id='%s' from comment" %
                                 osp.disp_os_id)
            else:
                outlines += line + "\n"
        return outlines

    def __match_os_profile(self):
        """Attempt to find a matching OsProfile for this BootEntry.

            Attempt to guess the correct ``OsProfile`` to use with
            this ``BootEntry`` by probing each loaded ``OsProfile``
            in turn until a profile recognises the entry. If no match
            is found the entrie's ``OsProfile`` is set to ``None``.

            Probing is only used in the case that a loaded entry has
            no embedded OsIdentifier string. All entries written by
            Boom include the OsIdentifier value: probing is primarily
            useful for entries that have been manually written or
            edited.
        """
        self._osp = match_os_profile(self)

    def __from_data(self, entry_data, boot_params):
        """Initialise a new BootEntry from in-memory data.

            Initialise a new ``BootEntry`` object with data from the
            dictionary ``entry_data`` (and optionally the supplied
            ``BootParams`` object). The supplied dictionary should be
            indexed by Boom entry key names (``BOOT_*``).

            Raises ``ValueError`` if required keys are missing
            (``BOOT_TITLE``, and either ``BOOT_LINUX`` or ``BOOT_EFI``).

            This method should not be called directly: to build a new
            ``BootEntry`` object from in-memory data, use the class
            initialiser with the ``entry_data`` argument.

            :param entry_data: A dictionary mapping Boom boot entry key
                               names to values
            :param boot_params: Optional BootParams to attach to the new
                                BootEntry object
            :returns: None
            :returntype: None
            :raises: ValueError
        """
        if BOOT_TITLE not in entry_data:
            raise ValueError("BootEntry missing BOOT_TITLE")

        if BOOT_LINUX not in entry_data and BOOT_EFI not in entry_data:
            raise ValueError("BootEntry missing BOOT_LINUX or BOOT_EFI")

        self._entry_data = {}
        for key in [k for k in ENTRY_KEYS if k in entry_data]:
            self._entry_data[key] = entry_data[key]

        if not self._osp:
            self.__match_os_profile()

        if boot_params:
            self.bp = boot_params
            # boot_params is always authoritative
            self._entry_data[BOOT_VERSION] = self.bp.version
        else:
            # Attempt to recover BootParams from entry data
            self.bp = BootParams.from_entry(self)

            def _pop_if_set(key):
                if key in self._entry_data:
                    self._entry_data.pop(key)

            if self.bp:
                # Clear templated keys from _entry_data and
                # regenerate from be.bp on demand.
                _pop_if_set(BOOT_VERSION)
                _pop_if_set(BOOT_LINUX)
                _pop_if_set(BOOT_INITRD)
                _pop_if_set(BOOT_OPTIONS)

    def __from_file(self, entry_file, boot_params):
        """Initialise a new BootEntry from on-disk data.

            Initialise a new ``BootEntry`` using the entry data in
            ``entry_file`` (and optionally the supplied ``BootParams``
            object).

            Raises ``ValueError`` if required keys are missing
            (``BOOT_TITLE``, and either ``BOOT_LINUX`` or ``BOOT_EFI``).

            This method should not be called directly: to build a new
            ``BootEntry`` object from entry file data, use the class
            initialiser with the ``entry_file`` argument.

            :param entry_file: The path to a file containing a BLS boot
                               entry
            :param boot_params: Optional BootParams to attach to the new
                                BootEntry object
            :returns: None
            :returntype: None
            :raises: ValueError
        """
        entry_data = {}
        comments = {}
        comment = ""

        _log_debug("Loading BootEntry from '%s'" % basename(entry_file))

        with open(entry_file, "r") as ef:
            for line in ef:
                if _blank_or_comment(line):
                    comment += line if line else ""
                else:
                    bls_key, value = _parse_name_value(line, separator=None)
                    key = MAP_KEY[_transform_key(bls_key)]
                    entry_data[key] = value
                    if comment:
                        comment = self.__os_id_from_comment(comment)
                        if not comment:
                            continue
                        comments[key] = comment
                        comment = ""
        self._comments = comments

        return self.__from_data(entry_data, boot_params)

    def __init__(self, title=None, machine_id=None, osprofile=None,
                 boot_params=None, entry_file=None, entry_data=None):
        """Initialise new BootEntry.

            Initialise a new ``BootEntry`` object from the specified
            file or using the supplied values.

            If ``osprofile`` is specified the profile is attached to the
            new ``BootEntry`` and will be used to supply templates for
            ``BootEntry`` values.

            A ``BootParams`` object may be supplied using the
            ``boot_params`` keyword argument. The object will be used to
            provide values for subsitution using the patterns defined by
            the configured ``OsProfile``.

            If ``entry_file`` is specified the ``BootEntry`` will be
            initialised from the values found in the file, which should
            contain a valid BLS snippet in UTF-8 encoding. The file may
            contain blank lines and comments (lines beginning with '#'),
            and these will be preserved if the entry is re-written.

            If ``entry_file`` is not specified, both ``title`` and
            ``machine_id`` must be given.

            The ``entry_data`` keyword argument is an optional argument
            used to initialise a ``BootEntry`` from a dictionary mapping
            ``BOOT_*`` keys to ``BootEntry`` values. It may be used to
            initialised a new ``BootEntry`` using the strings obtained
            from a call to ``BootEntry.__repr__()``.

            :param title: The title for this ``BootEntry``.

            :param machine_id: The ``machine_id`` of this ``BootEntry``.

            :param osprofile: An optional ``OsProfile`` to attach to
                              this ``BootEntry``.

            :param boot_params: An optional ``BootParams`` object to
                                initialise this ``BooyEntry``.

            :param entry_file: An optional path to a file in the file
                               system containing a boot entry in BLS
                               notation.

            :param entry_data: An optional dictionary of ``BootEntry``
                               key to value mappings to initialise
                               this ``BootEntry`` from.

            :returns: A new ``BootEntry`` object.

            :returntype: BootEntry
        """
        # An osprofile kwarg always takes precedent over either an
        # 'OsIdentifier' comment or a matched osprofile value.
        self._osp = osprofile

        if entry_data:
            return self.__from_data(entry_data, boot_params)
        if entry_file:
            return self.__from_file(entry_file, boot_params)

        self._unwritten = True

        if not title or not machine_id:
            raise ValueError("BootEntry title and machine_id cannot be None")

        self.bp = boot_params

        # The BootEntry._entry_data dictionary contains data for an existing
        # BootEntry that has been read from disk, as well as any overridden
        # fields for a new BootEntry with an OsProfile attached.
        self._entry_data = {}

        self.title = title
        self.machine_id = machine_id

        if not self._osp:
            self.__match_os_profile()

    def _apply_format(self, fmt):
        """Apply key format string substitution.

            Apply format key substitution to format string ``fmt``,
            using values provided by an attached ``BootParams`` object,
            and string patterns from either an associated ``OsProfile``
            object, or values set directly in this ``BootEntry``.

            If the source of data for a key is empty or None, the
            string is returned unchanged.

            The currently defined format keys are:

            * ``%{version}`` The kernel version string.
            * ``%{lvm_root_lv}`` The LVM2 logical volume containing the
              root file system.
            * ``%{btrfs_subvolume}`` The root flags specifying the BTRFS
              subvolume containing the root file system.
            * ``%{root_device}`` The device containing the root file
              system.
            * ``%{root_opts}`` The command line options required for the
              root file system.
            * ``%{linux}`` The linux image to boot

            :param fmt: The string to be formatted.

            :returns: The formatted string
            :returntype: str
        """
        orig = fmt
        key_format = "%%{%s}"
        bp = self.bp

        if not fmt:
            return ""

        version = None
        if not bp and self.version:
            version = self.version
        elif bp:
            version = bp.version

        key = key_format % FMT_VERSION
        if key in fmt and version:
            fmt = fmt.replace(key, version)

        key = key_format % FMT_LVM_ROOT_LV
        if bp and key in fmt and bp.lvm_root_lv:
            fmt = fmt.replace(key, bp.lvm_root_lv)

        key = key_format % FMT_BTRFS_SUBVOLUME
        if bp and key in fmt:
            if bp.btrfs_subvol_id or bp.btrfs_subvol_path:
                if bp.btrfs_subvol_id:
                    subvolume = "subvolid=%s" % bp.btrfs_subvol_id
                if bp.btrfs_subvol_path:
                    subvolume = "subvol=%s" % bp.btrfs_subvol_path
                fmt = fmt.replace(key, subvolume)

        key = key_format % FMT_ROOT_DEVICE
        if bp and key in fmt:
            if bp.root_device:
                fmt = fmt.replace(key, bp.root_device)

        key = key_format % FMT_KERNEL
        if key in fmt:
            fmt = fmt.replace(key, self.linux)

        key = key_format % FMT_INITRAMFS
        if key in fmt:
            fmt = fmt.replace(key, self.initrd)

        key = key_format % FMT_ROOT_OPTS
        if bp and key in fmt:
            root_opts = self._apply_format(self.root_opts)
            fmt = fmt.replace(key, root_opts)
        return fmt

    def __generate_boot_id(self):
        """Generate a new boot_id value.

            Generate a new sha1 profile identifier for this entry,
            using the title, version, root_device and any defined
            LVM2 or BTRFS snapshot parameters.

            :returns: A ``boot_id`` string
            :returntype: str
        """
        # The default ``str()`` and ``repr()`` behaviour for
        # ``BootEntry`` objects includes the ``boot_id`` value. This
        # must be disabled in order to generate the ``boot_id`` to
        # avoid recursing into __generate_boot_id() from the string
        # formatting methods.
        #
        # Call the underlying ``__str()`` method directly and disable
        # the inclusion of the ``boot_id``.
        #
        # Other callers should always rely on the standard methods.
        boot_id = sha1(self.__str(no_boot_id=True).encode('utf-8')).hexdigest()
        _log_debug_entry("Generated new boot_id='%s'" % boot_id)
        return boot_id

    def _entry_data_property(self, name):
        """Return property value from entry data.

            :param name: The boom key name of the property to return
            :returns: The property value from the entry data dictionary
        """
        if self._entry_data and name in self._entry_data:
            return self._entry_data[name]
        return None

    @property
    def disp_boot_id(self):
        """The display boot_id of this entry.

            Return the shortest prefix of this BootEntry's boot_id that
            is unique within the current set of loaded entries.

            :getter: return this BootEntry's boot_id.
            :type: str
        """
        return self.boot_id[:min_boot_id_width()]

    @property
    def boot_id(self):
        """A SHA1 digest that uniquely identifies this ``BootEntry``.

            :getter: return this ``BootEntry``'s ``boot_id``.
            :type: string
        """
        return self.__generate_boot_id()

    @property
    def root_opts(self):
        """The root options that should be used for this ``BootEntry``.

            :getter: Returns the root options string for this ``BootEntry``.
            :type: string
        """
        if not self._osp or not self.bp:
            return ""
        bp = self.bp
        osp = self._osp
        root_opts = "%s%s%s"

        lvm_opts = ""
        if bp.lvm_root_lv:
            lvm_opts = self._apply_format(osp.root_opts_lvm2)

        btrfs_opts = ""
        if bp.btrfs_subvol_id or bp.btrfs_subvol_path:
            btrfs_opts += self._apply_format(osp.root_opts_btrfs)

        spacer = " " if lvm_opts and btrfs_opts else ""

        return root_opts % (lvm_opts, spacer, btrfs_opts)

    @property
    def title(self):
        """The title of this ``BootEntry``.

            :getter: returns the ``BootEntry`` title.
            :setter: sets this ``BootEntry`` object's title.
            :type: string
        """
        return self._entry_data_property(BOOT_TITLE)

    @title.setter
    def title(self, title):
        self._entry_data[BOOT_TITLE] = title
        self._dirty()

    @property
    def machine_id(self):
        """The machine_id of this ``BootEntry``.

            :getter: returns this ``BootEntry`` object's ``machine_id``.
            :setter: sets this ``BootEntry`` object's ``machine_id``.
            :type: string
        """
        return self._entry_data_property(BOOT_MACHINE_ID)

    @machine_id.setter
    def machine_id(self, machine_id):
        self._entry_data[BOOT_MACHINE_ID] = machine_id
        self._dirty()

    @property
    def version(self):
        """The version string associated with this ``BootEntry``.

            :getter: returns this ``BootEntry`` object's ``version``.
            :setter: sets this ``BootEntry`` object's ``version``.
            :type: string
        """
        if self.bp and BOOT_VERSION not in self._entry_data:
            return self.bp.version
        return self._entry_data_property(BOOT_VERSION)

    @version.setter
    def version(self, version):
        self._entry_data[BOOT_VERSION] = version
        self._dirty()

    @property
    def options(self):
        """The command line options for this ``BootEntry``.

            :getter: returns the command line for this ``BootEntry``.
            :setter: sets the command line for this ``BootEntry``.
            :type: string
        """
        if not self._osp or BOOT_OPTIONS in self._entry_data:
            return self._entry_data_property(BOOT_OPTIONS)

        return self._apply_format(self._osp.options)

    @options.setter
    def options(self, options):
        self._entry_data[BOOT_OPTIONS] = options
        self._dirty()

    @property
    def linux(self):
        """The bootable Linux image for this ``BootEntry``.

            :getter: returns the configured ``linux`` image.
            :setter: sets the configured ``linux`` image.
            :type: string
        """
        if not self._osp or BOOT_LINUX in self._entry_data:
            return self._entry_data_property(BOOT_LINUX)

        kernel_path = self._apply_format(self._osp.kernel_pattern)
        return kernel_path

    @linux.setter
    def linux(self, linux):
        self._entry_data[BOOT_LINUX] = linux
        self._dirty()

    @property
    def initrd(self):
        """The loadable initramfs image for this ``BootEntry``.

            :getter: returns the configured ``initrd`` image.
            :getter: sets the configured ``initrd`` image.
            :type: string
        """
        if not self._osp or BOOT_INITRD in self._entry_data:
            return self._entry_data_property(BOOT_INITRD)

        initramfs_path = self._apply_format(self._osp.initramfs_pattern)
        return initramfs_path

    @initrd.setter
    def initrd(self, initrd):
        self._entry_data[BOOT_INITRD] = initrd
        self._dirty()

    @property
    def efi(self):
        """The loadable EFI image for this ``BootEntry``.

            :getter: returns the configured EFI application image.
            :getter: sets the configured EFI application image.
            :type: string
        """
        return self._entry_data_property(BOOT_EFI)

    @efi.setter
    def efi(self, efi):
        self._entry_data[BOOT_EFI] = efi
        self._dirty()

    @property
    def devicetree(self):
        """The devicetree archive for this ``BootEntry``.

            :getter: returns the configured device tree archive.
            :getter: sets the configured device tree archive.
            :type: string
        """
        return self._entry_data_property(BOOT_DEVICETREE)

    @devicetree.setter
    def devicetree(self, devicetree):
        self._entry_data[BOOT_DEVICETREE] = devicetree
        self._dirty()

    @property
    def _entry_path(self):
        id_tuple = (self.machine_id, self.boot_id[0:7], self.version)
        file_name = BOOT_ENTRIES_FORMAT % id_tuple
        return path_join(boom_entries_path(), file_name)

    def write_entry(self, force=False):
        """Write out entry to disk.

            Write out this ``BootEntry``'s data to a file in BLS
            format to the path specified by ``boom_entries_path()``.

            The file will be named according to the entry's key values,
            and the value of the ``BOOT_ENTRIES_FORMAT`` constant.
            Currently the ``machine_id`` and ``version`` keys are used
            to contstuct the file name.

            If the value of ``force`` is ``False`` and the ``OsProfile``
            is not currently marked as dirty (either new, or modified
            since the last load operation) the write will be skipped.

            :param force: Force this entry to be written to disk even
                          if the entry is unmodified.
            :raises: ``OSError`` if the temporary entry file cannot be
                     renamed, or if setting file permissions on the
                     new entry file fails.
            :returntype: None
        """
        entry_path = self._entry_path
        (tmp_fd, tmp_path) = mkstemp(prefix="boom", dir=boom_entries_path())
        with fdopen(tmp_fd, "w") as f:
            if self._osp:
                # Insert OsIdentifier comment at top-of-file
                f.write("#OsIdentifier: %s\n" % self._osp.os_id)
            for key in [k for k in ENTRY_KEYS if getattr(self, KEY_MAP[k])]:
                if self._comments and key in self._comments:
                    f.write(self._comments[key].rstrip() + '\n')
                # Map Boom key names to BLS entry keys
                key = KEY_MAP[key]
                key_fmt = "%s %s\n"
                key_data = (_transform_key(key), getattr(self, key))
                f.write(key_fmt % key_data)
        try:
            rename(tmp_path, entry_path)
            chmod(entry_path, BOOT_ENTRY_MODE)
        except Exception as e:
            _log_error("Error writing entry file %s: %s" %
                       (entry_path, e))
            try:
                unlink(tmp_path)
            except:
                pass
            raise e

        # Add this entry to the list of known on-disk entries
        _add_entry(self)

    def delete_entry(self):
        """Remove on-disk BootEntry file.

            Remove the on-disk entry corresponding to this ``BootEntry``
            object. This will permanently erase the current file
            (although the current data may be re-written at any time by
            calling ``write_entry()``).

            :returntype: ``NoneType``
            :raises: ``OsError`` if an error occurs removing the file or
                     ``ValueError`` if the entry does not exist.
        """
        if not path_exists(self._entry_path):
            raise ValueError("Entry does not exist: %s" % self._entry_path)
        try:
            unlink(self._entry_path)
        except Exception as e:
            _log_error("Error removing entry file %s: %s" %
                       (entry_path, e))
            raise

        if not self._unwritten:
            _del_entry(self)


__all__ = [
    # Module constants
    'BOOT_ENTRIES_FORMAT',
    'BOOT_ENTRY_MODE',

    # BootEntry keys
    'BOOT_TITLE',
    'BOOT_VERSION',
    'BOOT_MACHINE_ID',
    'BOOT_LINUX',
    'BOOT_INITRD',
    'BOOT_EFI',
    'BOOT_OPTIONS',
    'BOOT_DEVICETREE',

    # Root device pattern
    'DEV_PATTERN',

    # BootParams and BootEntry objects
    'BootParams', 'BootEntry',

    # Path configuration
    'boom_entries_path',

    # Entry lookup, load, and write functions
    'load_entries', 'write_entries', 'find_entries',

    # Formatting
    'min_boot_id_width'
]

# vim: set et ts=4 sw=4 :
