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
import boom

from boom import *
from boom.osprofile import *

from os.path import join as path_join
from tempfile import mkstemp
from os import listdir, rename, fdopen, chmod, unlink
import os.path
from hashlib import sha1

#: The path to the BLS boot entries directory.
BOOT_ENTRIES_PATH = path_join(BOOT_ROOT, "loader/entries")

#: The format used to construct entry file names.
BOOT_ENTRIES_FORMAT = "%s-%s.conf"

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

#: The global list of boot entries.
_entries = None

#: Pattern for forming root device paths from LVM2 names.
DEV_PATTERN = "/dev/%s"


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
        """__str(self, quote, prefix, suffix) -> string

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
        """__str__(self) -> string

            Format this ``BootParams`` object as a human-readable string.

            :returns: A human readable string representation of this
                      ``BootParams`` object.

            :returntype: string
        """
        return self.__str()

    def __repr__(self):
        """__repr__(self) -> string

            Format this ``BootParams`` object as a machine-readable
            string. The string returned is in the form of a call to the
            ``BootParams`` constructor.

            :returns: a machine readable string represenatation of this
                      ``BootParams`` object.
        """
        return self.__str(quote=True, prefix="BootParams(", suffix=")")

    def __init__(self, version, root_device=None, lvm_root_lv=None,
                 btrfs_subvol_path=None, btrfs_subvol_id=None):
        """__init__(self, root_device, lvm_root_lv, btrfs_subvol_path,
           btrfs_subvol_id) -> BootParams

            Initialise a new ``BootParams`` object with the specified
            values.

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

            :param version: The version string for this ``BootParams``
                            object.

            :param root_device: The root device for this ``BootParams``
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

            :returns: a newly initialised ``BootParams`` object.

            :returntype: ``class BootParams``

            :raises: ``ValueError``
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


def _add_entry(entry):
    """_add_entry(entry) -> None

        Add a new entry to the list of known on-disk entries.

        :param entry: The ``BootEntry`` to add.
    """
    global _entries
    if _entries == None:
        load_entries()
    if entry not in _entries:
        _entries.append(entry)


def _del_entry(entry):
    """_del_entry(entry) -> None

        Remove an existing ``BootEntry`` from the list of on-disk
        entries.

        :param entry: The ``BootEntry`` to remove.
    """
    global _entries
    _entries.remove(entry)


def load_entries(machine_id=None):
    """load_entries(machine_id) -> None

        Load boot entries from ``boom.bootloader.BOOT_ENTRIES_PATH``.

        If ``machine_id`` is specified only matching entries will be
        considered.

        :param machine_id: A ``machine_id`` value to match.
    """
    global _entries
    if not boom.osprofile._profiles:
        load_profiles()

    _entries = []
    for entry in listdir(BOOT_ENTRIES_PATH):
        if not entry.endswith(".conf"):
            continue
        if machine_id and machine_id not in entry:
            continue
        entry_path = path_join(BOOT_ENTRIES_PATH, entry)
        _add_entry(BootEntry(entry_file=entry_path))


def write_entries():
    """write_entries() -> None

        Write all currently loaded boot entries to
        ``boom.bootloader.BOOT_ENTRIES_PATH``.
    """
    global _entries
    for be in _entries:
        be.write_entry()


def find_entries(boot_id=None, title=None, version=None,
                 machine_id=None, root_device=None, lvm_root_lv=None,
                 btrfs_subvol_path=None, btrfs_subvol_id=None):
    """find_entries(boot_id, title, version, machine_id, root_device,
       lvm_root_lv, btrfs_subvol_path, btrfs_subvol_id) -> list

        Return a list of ``BootEntry`` objects matching the specified
        criteria. Matching proceeds as the logical 'and' of all criteria.
        Criteria that are unset (``None``) are ignored.

        If no ``BootEntry`` matches the specified criteria the empty list
        is returned.

        Boot entries will be automatically loaded from disk if they are
        not already in memory.

        :param boot_id: The boot identifier to match.
        :param title: The entry title to match.
        :param version: The version string to match``.
        :param root_device: The ``root_device`` value to match.
        :param lvm_root_lv: The root logical volume to match.
        :param btrfs_subvol_path: The BTRFS subvolume path to match.
        :param btrfs_subvol_id: The BTRFS subvolume ID to match.
        :returns: a list of ``BootEntry`` objects.
        :returntype: list
    """
    global _entries

    if not _entries:
        load_entries()

    matches = []

    # Option string prefixes
    svpath = "subvolpath=" + btrfs_subvol_path if btrfs_subvol_path else None
    svid = "subvolid=" + btrfs_subvol_id if btrfs_subvol_id else None

    for be in _entries:
        if boot_id and not be.boot_id.startswith(boot_id):
            continue
        if title and be.title != title:
            continue
        if version and be.version != version:
            continue
        if machine_id and be.machine_id != machine_id:
            continue
        # Match format attributes against the resulting options string.
        if root_device and root_device not in be.options:
            continue
        if lvm_root_lv and lvm_root_lv not in be.options:
            continue
        if btrfs_subvol_path and svpath not in be.options:
            continue
        if btrfs_subvol_id and svid not in be.options:
            continue
        matches.append(be)
    return matches


def _transform_key(key_name):
    """_transform_key(key_name) -> string

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
    _bp = None

    def __str(self, quote=False, prefix="", suffix="", tail="\n",
              sep=" ", bls=True, no_boot_id=False):
        """__str(self) -> string

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
        """__str__(self) -> string
            Format this BootEntry as a string containing a BLS
            configuration snippet.

            :returns: a BLS configuration snippet corresponding to this entry.

            :returntype: string
        """
        return self.__str()

    def __repr__(self):
        """__repr__(self) -> string
            Return a machine readable representation of this BootEntry,
            in constructor notation.

            :returns: A string in BootEntry constructor syntax.

            :returntype: str
        """
        return self.__str(quote=True, prefix="BootEntry(entry_data={",
                          suffix="})", tail=", ", sep=": ", bls=False)

    def __len__(self):
        """__len__(self) -> int

            Return the length (field count) of this ``BootEntry``.

            :returns: the ``BootEntry`` length as an integer.
            :returntype: ``int``
        """
        return len(self._entry_data)

    def __getitem__(self, key):
        """__getitem__(self, key) -> item

            Return an item from this ``BootEntry``.

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
        if self._bp and key == BOOT_VERSION:
            return self._bp.version

        raise KeyError("BootEntry key %s not present." % key)

    def __setitem__(self, key, value):
        """__setitem__(self, key, value) -> None

            Set the specified ``BootEntry`` key to the given value.

            :param key: the ``BootEntry`` key to be set.
            :param value: the value to set for the specified key.
        """
        if not isinstance(key, str):
            raise TypeError("BootEntry key must be a string.")

        if key == BOOT_VERSION and self._bp:
            self._bp.version = value
        elif key == BOOT_LINUX and self._bp:
            self.linux = value
        elif key == BOOT_INITRD and self._bp:
            self.initrd = value
        elif key == BOOT_OPTIONS and self._bp:
            self.options = value
        elif key == BOOT_DEVICETREE and self._bp:
            self.devicetree = value
        elif key == BOOT_EFI and self._bp:
            self.efi = value
        elif key == BOOT_ID:
            raise TypeError("'boot_id' property does not support assignment")
        elif key in self._entry_data:
            self._entry_data[key] = value
        else:
            raise KeyError("BootEntry key %s not present." % key)

    def keys(self):
        """keys(self) -> list

            Return a copy of this ``BootEntry``'s keys as a list of
            key name strings.

            :returns: the current list of ``BotoEntry`` keys.
            :returntype: list of str
        """
        keys = self._entry_data.keys()
        add_keys = [BOOT_LINUX, BOOT_INITRD, BOOT_OPTIONS]

        if self._bp:
            add_keys.append(BOOT_VERSION)

        for k in add_keys:
            if k not in self._entry_data:
                keys.append(k)

        return keys

    def values(self):
        """values(self) -> list

            Return a copy of this ``BootEntry``'s values as a list.

            :returns: the current list of ``BotoEntry`` values.
            :returntype: list
        """
        values = self._entry_data.values()
        add_values = [self.linux, self.initrd, self.options]

        if self._bp:
            add_values.append(self.version)

        return values + add_values

    def items(self):
        """items(self) -> list

            Return a copy of this ``BootEntry``'s ``(key, value)``
            pairs as a list.

            :returns: the current list of ``BotoEntry`` items.
            :returntype: list of ``(key, value)`` tuples.
        """
        add_items = [
            (BOOT_LINUX, self.linux),
            (BOOT_INITRD, self.initrd),
            (BOOT_OPTIONS, self.options)
        ]

        if self._bp:
            add_items.append((BOOT_VERSION, self.version))

        return self._entry_data.items() + add_items

    def _dirty(self):
        """_dirty(self) -> None
            Mark this ``BootEntry`` as needing to be written to disk.
            A newly created ``BootEntry`` object is always dirty and
            a call to its ``write_entry()`` method will always write
            a new boot entry file. Writes may be avoided for entries
            that are not marked as dirty.

            A clean ``BootEntry`` is marked as dirty if a new value
            is written to any of its writable properties.
        """
        self._unwritten = True

    def __os_id_from_comment(self, comment):
        """__os_id_from_comment(comment) -> None

            Attempt to set this BootEntry's OsProfile using a comment
            string stored in the entry file. The comment must be of the
            form "OsIdentifier: <os_id>". If found the value is treated
            as authoritative.
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
            else:
                outlines += line + "\n"
        return outlines

    def __match_os_profile(self):
        """__match_os_profile(self) -> None
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

        """__from_data(self, entry_data) -> None
            Initialise a new ``BootEntry`` object with data from the
            dictionary ``entry_data``.

            Raises ``ValueError`` if required keys are missing
            (``BOOT_TITLE``, and either ``BOOT_LINUX`` or ``BOOT_EFI``).

            :returns: ``None``
            :returntype: ``None``
            :raises: ``ValueError``
        """
        if BOOT_TITLE not in entry_data:
            raise ValueError("BootEntry missing BOOT_TITLE")

        if BOOT_LINUX not in entry_data and BOOT_EFI not in entry_data:
            raise ValueError("BootEntry missing BOOT_LINUX or BOOT_EFI")

        self._entry_data = {}
        for key in [k for k in ENTRY_KEYS if k in entry_data]:
            self._entry_data[key] = entry_data[key]

        if boot_params:
            self._bp = boot_params
            # boot_params is always authoritative
            self._entry_data[BOOT_VERSION] = self._bp.version

        if not self._osp:
            self.__match_os_profile()

    def __from_file(self, entry_file, boot_params):
        entry_data = {}
        comments = {}
        comment = ""
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
        """__init__(self, title, machine_id, osprofile, boot_params,
           entry_file, entry_data) -> BootEntry

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

        self._bp = boot_params

        # The BootEntry._entry_data dictionary contains data for an existing
        # BootEntry that has been read from disk, as well as any overridden
        # fields for a new BootEntry with an OsProfile attached.
        self._entry_data = {}

        self.title = title
        self.machine_id = machine_id

        if not self._osp:
            self.__match_os_profile()

    def _apply_format(self, fmt):
        """_apply_format(self, fmt) -> None

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

            :param fmt: The string to be formatted.

            :returns: The formatted string
            :returntype: str
        """
        orig = fmt
        key_format = "%%{%s}"
        bp = self._bp

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

        key = key_format % FMT_ROOT_OPTS
        if bp and key in fmt:
            root_opts = self._apply_format(self.root_opts)
            fmt = fmt.replace(key, root_opts)
        return fmt

    def __generate_boot_id(self):
        """_generate_boot_id()
            Generate a new sha1 profile identifier for this entry,
            using the title, version, root_device and any defined
            LVM2 or BTRFS snapshot parameters.
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
        return sha1(self.__str(no_boot_id=True).encode('utf-8')).hexdigest()

    def _entry_data_property(self, name):
        if self._entry_data and name in self._entry_data:
            return self._entry_data[name]
        return None

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
        if not self._osp or not self._bp:
            return ""
        bp = self._bp
        osp = self._osp
        if bp.lvm_root_lv:
            return self._apply_format(osp.root_opts_lvm2)
        if bp.btrfs_subvol_id or bp.btrfs_subvol_path:
            return self._apply_format(osp.root_opts_btrfs)
        return ""

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
        if self._bp and BOOT_VERSION not in self._entry_data:
            return self._bp.version
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

        kernel_name = self._apply_format(self._osp.kernel_pattern)
        kernel_path = self._apply_format(self._osp.kernel_path)
        return path_join(kernel_path, kernel_name)

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

        initramfs_name = self._apply_format(self._osp.initramfs_pattern)
        initramfs_path = self._apply_format(self._osp.initramfs_path)
        return path_join(initramfs_path, initramfs_name)

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
        file_name = BOOT_ENTRIES_FORMAT % (self.machine_id, self.version)
        return path_join(BOOT_ENTRIES_PATH, file_name)

    def write_entry(self, force=False):
        """write_entry(self) -> None

            Write out this ``BootEntry``'s data to a file in BLS
            format to the path specified by ``BOOT_ENTRIES_PATH``.

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
        """
        entry_path = self._entry_path
        (tmp_fd, tmp_path) = mkstemp(prefix="boom", dir=BOOT_ENTRIES_PATH)
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
            try:
                unlink(tmp_path)
            except:
                pass
            raise e

        # Add this entry to the list of known on-disk entries
        _add_entry(self)

    def delete_entry(self):
        """delete_entry(self) -> None

            Remove the on-disk entry corresponding to this ``BootEntry``
            object. This will permanently erase the current file
            (although the current data may be re-written at any time by
            calling ``write_entry()``).

            :returntype: ``NoneType``
            :raises: ``OsError`` if an error occurs removing the file or
                     ``ValueError`` if the entry does not exist.
        """
        if not os.path.exists(self._entry_path):
            raise ValueError("Entry does not exist: %s" % self._entry_path)
        os.unlink(self._entry_path)
        _del_entry(self)


__all__ = [
    # Module constants
    'BOOT_ENTRIES_PATH',
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

    # BootParams and BootEntry objects
    'BootParams', 'BootEntry',

    # Entry lookup, load, and write functions
    'load_entries', 'write_entries', 'find_entries'
]

# vim: set et ts=4 sw=4 :
