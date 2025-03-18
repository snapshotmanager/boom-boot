# Copyright Red Hat
#
# boom/bootloader.py - Boom BLS bootloader manager
#
# This file is part of the boom project.
#
# SPDX-License-Identifier: GPL-2.0-only
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
from __future__ import print_function

from os.path import basename, exists as path_exists, join as path_join
from subprocess import Popen, PIPE
from tempfile import mkstemp
from os import listdir, rename, fdopen, chmod, unlink, fdatasync, stat, dup
from stat import S_ISBLK
from hashlib import sha1
import logging

from boom import *
from boom.osprofile import *
from boom.hostprofile import find_host_profiles
from boom.stratis import *
import re

#: The path to the BLS boot entries directory relative to /boot
ENTRIES_PATH = "loader/entries"

#: The format used to construct entry file names.
BOOT_ENTRIES_FORMAT = "%s-%s-%s.conf"

#: A regular expression matching the boom file name format.
BOOT_ENTRIES_PATTERN = r"(\w*)-([0-9a-f]{7,})-.*\.conf"

#: The file mode with which BLS entries should be created.
BOOT_ENTRY_MODE = 0o644

#: The ``BootEntry`` title key.
BOOM_ENTRY_TITLE = "BOOM_ENTRY_TITLE"
#: The ``BootEntry`` version key.
BOOM_ENTRY_VERSION = "BOOM_ENTRY_VERSION"
#: The ``BootEntry`` machine_id key.
BOOM_ENTRY_MACHINE_ID = "BOOM_ENTRY_MACHINE_ID"
#: The ``BootEntry`` linux key.
BOOM_ENTRY_LINUX = "BOOM_ENTRY_LINUX"
#: The ``BootEntry`` initrd key.
BOOM_ENTRY_INITRD = "BOOM_ENTRY_INITRD"
#: The ``BootEntry`` efi key.
BOOM_ENTRY_EFI = "BOOM_ENTRY_EFI"
#: The ``BootEntry`` options key.
BOOM_ENTRY_OPTIONS = "BOOM_ENTRY_OPTIONS"
#: The ``BootEntry`` device tree key.
BOOM_ENTRY_DEVICETREE = "BOOM_ENTRY_DEVICETREE"
#: The ``BootEntry`` architecture key.
BOOM_ENTRY_ARCHITECTURE = "BOOM_ENTRY_ARCHITECTURE"
#: The ``BootEntry`` boot identifier key.
BOOM_ENTRY_BOOT_ID = "BOOM_ENTRY_BOOT_ID"

#
# Optional and non-standard BLS keys
#
# The keys defined here are optional and implementation defined:
# They may only be used in a ``BootEntry`` if the corresponding
# ``OsProfile`` or ``HostProfile`` permits them.
#

#: The Red Hat ``BootEntry`` grub_users key.
BOOM_ENTRY_GRUB_USERS = "BOOM_ENTRY_GRUB_USERS"
#: The Red Hat ``BootEntry`` grub_arg key.
BOOM_ENTRY_GRUB_ARG = "BOOM_ENTRY_GRUB_ARG"
#: The Red Hat ``BootEntry`` grub_class key.
BOOM_ENTRY_GRUB_CLASS = "BOOM_ENTRY_GRUB_CLASS"
#: The Red Hat ``BootEntry`` id key.
BOOM_ENTRY_GRUB_ID = "BOOM_ENTRY_GRUB_ID"

#: Optional keys not defined by the upstream BLS specification.
OPTIONAL_KEYS = [
    BOOM_ENTRY_GRUB_USERS,
    BOOM_ENTRY_GRUB_ARG,
    BOOM_ENTRY_GRUB_CLASS,
    BOOM_ENTRY_GRUB_ID,
]

#: An ordered list of all possible ``BootEntry`` keys.
ENTRY_KEYS = [
    # We require a title for each entry (BLS does not)
    BOOM_ENTRY_TITLE,
    # MACHINE_ID is optional in BLS, however, since the standard suggests
    # that it form part of the file name for compliant snippets, it is
    # effectively mandatory.
    BOOM_ENTRY_MACHINE_ID,
    BOOM_ENTRY_VERSION,
    # One of either BOOM_ENTRY_LINUX or BOOM_ENTRY_EFI must be present.
    BOOM_ENTRY_LINUX,
    BOOM_ENTRY_EFI,
    BOOM_ENTRY_INITRD,
    BOOM_ENTRY_OPTIONS,
    BOOM_ENTRY_DEVICETREE,
    BOOM_ENTRY_ARCHITECTURE,
    # Optional implementation defined BLS keys
    BOOM_ENTRY_GRUB_ID,
    BOOM_ENTRY_GRUB_USERS,
    BOOM_ENTRY_GRUB_ARG,
    BOOM_ENTRY_GRUB_CLASS,
]

#: Map Boom entry names to BLS keys
KEY_MAP = {
    BOOM_ENTRY_TITLE: "title",
    BOOM_ENTRY_VERSION: "version",
    BOOM_ENTRY_MACHINE_ID: "machine_id",
    BOOM_ENTRY_LINUX: "linux",
    BOOM_ENTRY_INITRD: "initrd",
    BOOM_ENTRY_EFI: "efi",
    BOOM_ENTRY_OPTIONS: "options",
    BOOM_ENTRY_DEVICETREE: "devicetree",
    BOOM_ENTRY_ARCHITECTURE: "architecture",
    BOOM_ENTRY_GRUB_USERS: "grub_users",
    BOOM_ENTRY_GRUB_ARG: "grub_arg",
    BOOM_ENTRY_GRUB_CLASS: "grub_class",
    BOOM_ENTRY_GRUB_ID: "id",
}

#: Default values for optional keys
OPTIONAL_KEY_DEFAULTS = {
    BOOM_ENTRY_GRUB_USERS: "$grub_users",
    BOOM_ENTRY_GRUB_ARG: "--unrestricted",
    BOOM_ENTRY_GRUB_CLASS: "kernel",
    BOOM_ENTRY_GRUB_ID: None,
}


def optional_key_default(key):
    """Return the default value for the optional key ``key``.

    :param key: A Boom optional entry key.
    :returns: The default value for optional key ``key``.
    :rtype: str
    """
    if key not in OPTIONAL_KEY_DEFAULTS.keys():
        raise ValueError("Unknown optional BootEntry key: %s" % key)
    return OPTIONAL_KEY_DEFAULTS[key]


def key_to_bls_name(key):
    """Return the BLS key name for the corresponding Boom entry key.

    :param key: A Boom entry key.
    :returns: A string representing the BLS key name.
    :rtype: str
    """
    if key not in KEY_MAP.keys():
        raise ValueError("Unknown BootEntry key: %s" % key)
    return KEY_MAP[key]


#: Map BLS entry keys to Boom names
MAP_KEY = {v: k for k, v in KEY_MAP.items()}

#: Grub2 environment variable expansion character
GRUB2_EXPAND_ENV = "$"

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
    :rtype: str
    """
    return path_join(get_boot_path(), ENTRIES_PATH)


class BoomRootDeviceError(BoomError):
    """Boom exception indicating an invalid root device."""

    pass


def check_root_device(dev):
    """Test for the presence of root device ``dev`` and return if it
    exists in the configured /dev directory and is a valid block
    device, or raise ``BoomRootDeviceError`` otherwise.

    The exception string indicates the class of error: missing
    path or not a block device.

    :param dev: the root device to check for.
    :raises: BoomRootDeviceError if ``dev`` is invalid.
    :returns: None
    """
    if not path_exists(dev):
        raise BoomRootDeviceError("Device '%s' not found." % dev)

    st = stat(dev)
    if not S_ISBLK(st.st_mode):
        raise BoomRootDeviceError("Path '%s' is not a block device." % dev)


def _match_root_lv(root_device, rd_lvm_lv):
    """Return ``True`` if ``rd_lvm_lv`` is the logical volume
    represented by ``root_device`` or ``False`` otherwise.

    The root_device for an LVM2 LV may be in one of two possible
    forms:

        root_device=/dev/mapper/vg-lv
        root_device=/dev/vg/lv

    """

    def dm_split_name(name):
        for i in range(1, len(name)):
            if name[i] == "-":
                if name[i - 1] != "-" and name[i + 1] != "-":
                    return (name[0:i], name[i + 1 :])

    # root_device=/dev/vg/lv
    if rd_lvm_lv == root_device[5:]:
        return True
    if "mapper" in root_device:
        (vg, lv) = dm_split_name(root_device.split("/")[-1])
        if rd_lvm_lv == "%s/%s" % (vg, lv):
            return True
    return False


def _grub2_get_env(name):
    """Return the value of the Grub2 environment variable with name
    ``name`` as a string.

    :param name: The name of the environment variable to return.
    :returns: The value of the named environment variable.
    :rtype: string
    """
    grub_cmd = ["grub2-editenv", "list"]
    try:
        p = Popen(grub_cmd, stdin=None, stdout=PIPE, stderr=PIPE)
        out = p.communicate()[0]
    except OSError as e:
        _log_error("Could not obtain grub2 environment: %s", e)
        return ""

    for line in out.decode("utf8").splitlines():
        (env_name, value) = line.split("=", 1)
        if name == env_name:
            return value.strip()
    return ""


def _expand_vars(args):
    """Expand a ``BootEntry`` option string that may contain
    references to Grub2 environment variables using shell
    style ``$value`` notation.
    """
    var_char = GRUB2_EXPAND_ENV
    if var_char not in args:
        return args

    for arg in args.split():
        if arg.startswith(var_char):
            env_name = arg[1:]
            args = args.replace(arg, _grub2_get_env(env_name))
    return args


class BootParams(object):
    """The ``BootParams`` class encapsulates the information needed to
    boot an instance of the operating system: the kernel version,
    root device, and root device options.

    A ``BootParams`` object is used to configure a ``BootEntry``
    and to generate configuration keys for the entry based on an
    attached OsProfile.
    """

    #: The kernel version of the instance.
    _version = None

    #: The path to the root device
    _root_device = None

    #: The LVM2 logical volume containing the root file system
    _lvm_root_lv = None

    #: The BTRFS subvolume path to be used as the root file system.
    _btrfs_subvol_path = None

    #: The ID of the BTRFS subvolume to be used as the root file system.
    _btrfs_subvol_id = None

    #: The UUID of the Stratis pool containing the root_device.
    _stratis_pool_uuid = None

    #: A list of additional kernel options to append
    _add_opts = []

    #: A list of kernel options to drop
    _del_opts = []

    #: Generation counter for dirty detection
    generation = 0

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
        :rtype: string
        """
        bp_str = prefix

        fields = [
            "version",
            "root_device",
            "lvm_root_lv",
            "btrfs_subvol_path",
            "btrfs_subvol_id",
            "stratis_pool_uuid",
        ]
        params = (
            self.root_device,
            self.lvm_root_lv,
            self.btrfs_subvol_path,
            self.btrfs_subvol_id,
            self.stratis_pool_uuid,
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

        :rtype: string
        """
        return self.__str()

    def __repr__(self):
        """Format BootParams as a machine-readable string.

        Format this ``BootParams`` object as a machine-readable
        string. The string returned is in the form of a call to the
        ``BootParams`` constructor.

        :returns: a machine readable string representation of this
                  ``BootParams`` object.
        """
        return self.__str(quote=True, prefix="BootParams(", suffix=")")

    def __init__(
        self,
        version,
        root_device=None,
        lvm_root_lv=None,
        btrfs_subvol_path=None,
        btrfs_subvol_id=None,
        stratis_pool_uuid=None,
        add_opts=None,
        del_opts=None,
    ):
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
        :param stratis_pool_uuid: The UUID of the Stratis pool that
                                  contains root_device.
        :param add_opts: A list containing additional kernel
                         options to be appended to the command line.
        :param del_opts: A list containing kernel options to be
                         dropped from the command line.
        :returns: a newly initialised BootParams object.
        :rtype: class BootParams
        :raises: ValueError
        """
        if not version:
            raise ValueError("version argument is required.")

        self.version = version

        if root_device:
            self.root_device = root_device

        if lvm_root_lv:
            if not root_device:
                self.root_device = DEV_PATTERN % lvm_root_lv
            self.lvm_root_lv = lvm_root_lv

        if btrfs_subvol_path and btrfs_subvol_id:
            raise ValueError(
                "Only one of btrfs_subvol_path and " "btrfs_subvol_id allowed."
            )

        if btrfs_subvol_path:
            self.btrfs_subvol_path = btrfs_subvol_path
        if btrfs_subvol_id:
            self.btrfs_subvol_id = btrfs_subvol_id

        if stratis_pool_uuid:
            self._stratis_pool_uuid = stratis_pool_uuid

        self.add_opts = add_opts or []
        self.del_opts = del_opts or []

        _log_debug_entry("Initialised %s", repr(self))

    # We have to use explicit properties for BootParam attributes since
    # we need to track modifications to the BootParams values to allow
    # a containing BootEntry to mark itself as dirty.

    @property
    def version(self):
        """Return this ``BootParams`` object's version."""
        return self._version

    @version.setter
    def version(self, value):
        """Set this ``BootParams`` object's version."""
        self.generation += 1
        self._version = value

    @property
    def root_device(self):
        """Return this ``BootParams`` object's root_device."""
        return self._root_device

    @root_device.setter
    def root_device(self, value):
        """Set this ``BootParams`` object's root_device."""
        self.generation += 1
        self._root_device = value

    @property
    def lvm_root_lv(self):
        """Return this ``BootParams`` object's lvm_root_lv."""
        return self._lvm_root_lv

    @lvm_root_lv.setter
    def lvm_root_lv(self, value):
        """Set this ``BootParams`` object's lvm_root_lv."""
        self.generation += 1
        self._lvm_root_lv = value

    @property
    def btrfs_subvol_path(self):
        """Return this ``BootParams`` object's btrfs_subvol_path."""
        return self._btrfs_subvol_path

    @btrfs_subvol_path.setter
    def btrfs_subvol_path(self, value):
        """Set this ``BootParams`` object's btrfs_subvol_path."""
        self.generation += 1
        self._btrfs_subvol_path = value

    @property
    def btrfs_subvol_id(self):
        """Return this ``BootParams`` object's btrfs_subvol_id."""
        return self._btrfs_subvol_id

    @btrfs_subvol_id.setter
    def btrfs_subvol_id(self, value):
        """Set this ``BootParams`` object's btrfs_subvol_id."""
        self.generation += 1
        self._btrfs_subvol_id = value

    @property
    def stratis_pool_uuid(self):
        """Return this ``BootParams`` object's stratis_pool_uuid."""
        if self._stratis_pool_uuid:
            return self._stratis_pool_uuid
        if self.has_stratis():
            return format_pool_uuid(symlink_to_pool_uuid(self.root_device))
        return ""

    @stratis_pool_uuid.setter
    def stratis_pool_uuid(self, value):
        """Override this ``BootParams`` object's stratis_pool_uuid."""
        self.generation += 1
        self._stratis_pool_uuid = value

    @property
    def add_opts(self):
        """Return this ``BootParams`` object's add_opts."""
        return self._add_opts

    @add_opts.setter
    def add_opts(self, value):
        """Set this ``BootParams`` object's add_opts."""
        self.generation += 1
        self._add_opts = value

    @property
    def del_opts(self):
        """Return this ``BootParams`` object's del_opts."""
        return self._del_opts

    @del_opts.setter
    def del_opts(self, value):
        """Set this ``BootParams`` object's del_opts."""
        self.generation += 1
        self._del_opts = value

    def has_btrfs(self):
        """Return ``True`` if this BootParams object is configured to
        use BTRFS.

        :returns: True if BTRFS is in use, or False otherwise
        :rtype: bool
        """
        return any((self.btrfs_subvol_id, self.btrfs_subvol_path))

    def has_lvm2(self):
        """Return ``True`` if this BootParams object is configured to
        use LVM2.

        :returns: True if LVM2 is in use, or False otherwise
        :rtype: bool
        """
        return self.lvm_root_lv is not None and len(self.lvm_root_lv)

    def has_stratis(self):
        """Return ``True`` if this BootParams object is configured to
        use a Stratis root file system.

        :returns: ``True`` if Stratis is in use, or ``False``
                  otherwise.
        :rtype: bool
        """
        if self.root_device is None:
            return False
        return is_stratis_device_path(self.root_device)

    @classmethod
    def from_entry(cls, be, expand=False):
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
        :param expand: Expand bootloader environment variables.
        :returns: A newly initialised BootParams object.
        :rtype: ``BootParams``
        :raises: ValueError if expected values cannot be matched.
        """
        osp = be._osp
        # Version is written directly from BootParams
        version = be.version
        bp = BootParams(version)
        matches = {}

        opts_regexes = osp.make_format_regexes(osp.options)
        if not opts_regexes:
            return None

        _log_debug_entry(
            "Matching options regex list with %d entries", len(opts_regexes)
        )
        _log_debug_entry("Options regex list: %s", str(opts_regexes))

        for rgx_word in opts_regexes:
            (name, exp) = rgx_word
            value = ""
            for word in be.expand_options.split():
                match = re.search(exp, word) if name else re.match(exp, word)
                if match:
                    if len(match.groups()):
                        value = match.group(1)
                        _log_debug_entry("Matching: '%s' (%s)", value, name)
                    if name == "lvm_root_lv":
                        if not _match_root_lv(bp.root_device, value):
                            continue
                        _log_debug_entry(
                            "Matched root_device=%s to %s=%s",
                            bp.root_device,
                            name,
                            value,
                        )
                    matches[word] = True
                    if name:
                        _log_debug_entry("Matched %s=%s", name, value)
                        setattr(bp, name, value)

            # The root_device key is handled specially since it is required
            # for a valid BootEntry.
            if name == "root_device" and not value:
                _log_warn("No root_device for entry at %s", be._last_path)
                setattr(bp, name, "")

        def is_add(opt):
            """Return ``True`` if ``opt`` was appended to this options line,
            and was not generated from the active ``OsProfile`` template,
            or from expansion of a bootloader environment variable.
            """

            def opt_in_expansion(opt):
                """Return ``True`` if ``opt`` is contained in the expansion of
                a bootloader environment variable embedded in this entry's
                options string.

                :param opt: A kernel command line option.
                :returns: ``True`` if ``opt`` is defined in a bootloader
                          environment variable, or ``False`` otherwise.
                :rtype: bool
                """
                if GRUB2_EXPAND_ENV not in be.options:
                    return False
                return opt not in _expand_vars(be.options).split()

            if opt not in matches.keys():
                if opt not in be._osp.options.split():
                    if not opt_in_expansion(opt):
                        _log_debug_entry("Found add_opt: %s", opt)
                        return True
            return False

        def is_del(opt):
            """Return ``True`` if the option regex `opt` has been deleted
            from this options line. An option is dropped if it is in
            the ``OsProfile`` template and is absent from the option
            line.

            Optional boot parameters (e.g. rd.lvm.lv and rootflags)
            are ignored since these are only templated when the
            corresponding boot parameter is set.

            The fact that an option is dropped is recorded for later
            templating operations.
            """
            # Ignore optional boot parameters
            ignore_bp = [
                "rootflags",
                "rd.lvm.lv",
                "subvol",
                "subvolid",
                "stratis.rootfs.pool_uuid",
            ]
            opt_name = opt.split("=")[0]
            matched_opts = [k.split("=")[0] for k in matches.keys()]
            if opt_name not in matched_opts and opt_name not in ignore_bp:
                _log_debug_entry("Found del_opt: %s", opt)
                return True
            return False

        options = be.expand_options.split() if expand else be.options.split()

        # Compile list of unique non-template options
        bp.add_opts = [opt for opt in options if is_add(opt)]

        # Compile list of deleted template options
        bp.del_opts = [o for o in [r[1] for r in opts_regexes] if is_del(o)]

        _log_debug_entry("Parsed %s", repr(bp))

        return bp


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


def drop_entries():
    """Drop all in-memory entries.

    Clear the list of in-memory entries and reset the BootEntry
    list to the default state.

    :returns: None
    """
    global _entries
    _entries = []


def load_entries(machine_id=None):
    """Load boot entries into memory.

    Load boot entries from ``boom.bootloader.boom_entries_path()``.

    If ``machine_id`` is specified only matching entries will be
    considered.

    :param machine_id: A ``machine_id`` value to match.
    """
    global _entries
    if not profiles_loaded():
        load_profiles()

    entries_path = boom_entries_path()

    drop_entries()

    _log_debug("Loading boot entries from '%s'", entries_path)
    for entry in listdir(entries_path):
        if not entry.endswith(".conf"):
            continue
        if machine_id and machine_id not in entry:
            _log_debug_entry("Skipping entry with machine_id!='%s'", machine_id)
            continue
        entry_path = path_join(entries_path, entry)
        try:
            _add_entry(BootEntry(entry_file=entry_path))
        except Exception as e:
            _log_info("Could not load BootEntry '%s': %s", entry_path, e)
            if get_debug_mask():
                raise e

    _log_debug("Loaded %d entries", len(_entries))


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
            _log_warn("Could not write BootEntry(boot_id='%s'): %s", be.disp_boot_id, e)


def min_boot_id_width():
    """Calculate the minimum unique width for boot_id values.

    Calculate the minimum width to ensure uniqueness when displaying
    boot_id values.

    :returns: the minimum boot_id width.
    :rtype: int
    """
    return min_id_width(7, _entries, "boot_id")


def select_params(s, bp):
    """Test BootParams against Selection criteria.

    Test the supplied ``BootParams`` against the selection criteria
    in ``s`` and return ``True`` if it passes, or ``False``
    otherwise.

    :param s: Selection criteria
    :param bp: The BootParams to test
    :rtype: bool
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

    :param s: The selection criteria
    :param be: The BootEntry to test
    :rtype: bool
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
    if s.linux and be.linux != s.linux:
        return False
    if s.initrd and be.initrd != s.initrd:
        return False
    if s.path:
        if s.path != be.linux and s.path != be.initrd:
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
    :rtype: list
    """
    global _entries

    if not _entries:
        load_entries()

    matches = []

    # Use null search criteria if unspecified
    selection = selection if selection else Selection()

    selection.check_valid_selection(entry=True, params=True, profile=True)

    _log_debug_entry("Finding entries for %s", repr(selection))

    for be in _entries:
        if select_entry(selection, be):
            matches.append(be)

    _log_debug_entry("Found %d entries", len(matches))
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

    :rtype: string
    """
    _exclude_keys = OPTIONAL_KEYS

    # Red Hat's non-upstream BLS keys use '_', rather than '-' (unlike
    # the standard BLS keys).
    if key_name in MAP_KEY and MAP_KEY[key_name] in _exclude_keys:
        return key_name

    if key_name in ["grub_users", "grub_class", "grub_arg"]:
        return key_name
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
    _last_path = None
    _comments = None
    _osp = None
    _bp = None
    _bp_generation = None
    _suppress_machine_id = False

    # Read only state for foreign BLS entries
    read_only = False

    # boot_id cache
    __boot_id = None

    def __str(
        self,
        quote=False,
        prefix="",
        suffix="",
        tail="\n",
        sep=" ",
        bls=True,
        no_boot_id=False,
        expand=False,
    ):
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

        :param no_boot_id: Do not include the BOOM_ENTRY_BOOT_ID key in the
                           returned string. Used internally in
                           order to avoid recursion when calculating
                           the BOOM_ENTRY_BOOT_ID checksum.

        :returns: A string representation.

        :rtype: string
        """
        be_str = prefix

        for key in [k for k in ENTRY_KEYS if getattr(self, KEY_MAP[k])]:
            if key == BOOM_ENTRY_MACHINE_ID and self._suppress_machine_id:
                continue
            attr = KEY_MAP[key]
            key_fmt = '%s%s"%s"' if quote else "%s%s%s"
            key_fmt += tail

            attr_val = getattr(self, attr)
            if expand:
                attr_val = _expand_vars(attr_val)

            if bls:
                key_data = (_transform_key(attr), sep, attr_val)
            else:
                key_data = (key, sep, attr_val)
            be_str += key_fmt % key_data

        # BOOM_ENTRY_BOOT_ID requires special handling to avoid
        # recursion from the boot_id property method (which uses the
        # string representation of the object to calculate the
        # checksum).
        if not bls and not no_boot_id:
            key_fmt = ('%s%s"%s"' if quote else "%s%s%s") + tail
            boot_id_data = [BOOM_ENTRY_BOOT_ID, sep, self.boot_id]
            be_str += key_fmt % tuple(boot_id_data)

        return be_str.rstrip(tail) + suffix

    def __str__(self):
        """Format BootEntry as a human-readable string in BLS notation.

        Format this BootEntry as a string containing a BLS
        configuration snippet.

        :returns: a BLS configuration snippet corresponding to this entry.

        :rtype: string
        """
        return self.__str()

    def __repr__(self):
        """Format BootEntry as a machine-readable string.

        Return a machine readable representation of this BootEntry,
        in constructor notation.

        :returns: A string in BootEntry constructor syntax.

        :rtype: str
        """
        return self.__str(
            quote=True,
            prefix="BootEntry(entry_data={",
            suffix="})",
            tail=", ",
            sep=": ",
            bls=False,
        )

    def __len__(self):
        """Return the length (key count) of this ``BootEntry``.

        :returns: the ``BootEntry`` length as an integer.
        :rtype: ``int``
        """
        return len(self._entry_data)

    def __eq__(self, other):
        """Test for equality between this ``BootEntry`` and another
        object.

        Equality for ``BootEntry`` objects is true if the both
        ``boot_id`` values match.

        :param other: The object against which to test.

        :returns: ``True`` if the objects are equal and ``False``
                  otherwise.
        :rtype: bool
        """
        if not hasattr(other, "boot_id"):
            return False
        if self.boot_id == other.boot_id:
            return True
        return False

    def __getitem__(self, key):
        """Return an item from this ``BootEntry``.

        :returns: the item corresponding to the key requested.
        :rtype: the corresponding type of the requested key.
        :raises: TypeError if ``key`` is of an invalid type.
                 KeyError if ``key`` is valid but not present.
        """
        if not isinstance(key, str):
            raise TypeError("BootEntry key must be a string.")

        if key in KEY_MAP and hasattr(self, KEY_MAP[key]):
            return getattr(self, KEY_MAP[key])

        raise KeyError("BootEntry key %s not present." % key)

    def __setitem__(self, key, value):
        """Set the specified ``BootEntry`` key to the given value.

        :param key: the ``BootEntry`` key to be set.
        :param value: the value to set for the specified key.
        """
        if not isinstance(key, str):
            raise TypeError("BootEntry key must be a string.")

        if key in KEY_MAP and hasattr(self, KEY_MAP[key]):
            return setattr(self, KEY_MAP[key], value)

        raise KeyError("BootEntry key %s not present." % key)

    def keys(self):
        """Return the list of keys for this ``BootEntry``.

        Return a copy of this ``BootEntry``'s keys as a list of
        key name strings.

        :returns: the current list of ``BotoEntry`` keys.
        :rtype: list of str
        """
        keys = list(self._entry_data.keys())
        add_keys = [BOOM_ENTRY_LINUX, BOOM_ENTRY_INITRD, BOOM_ENTRY_OPTIONS]

        # Sort the item list to give stable list ordering on Py3.
        keys = sorted(keys, reverse=True)

        if self.bp:
            add_keys.append(BOOM_ENTRY_VERSION)

        for k in add_keys:
            if k not in self._entry_data:
                keys.append(k)

        return keys

    def values(self):
        """Return the list of values for this ``BootEntry``.

        Return a copy of this ``BootEntry``'s values as a list.

        :returns: the current list of ``BootEntry`` values.
        :rtype: list
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
        :rtype: list of ``(key, value)`` tuples.
        """
        items = list(self._entry_data.items())

        add_items = [
            (BOOM_ENTRY_LINUX, self.linux),
            (BOOM_ENTRY_INITRD, self.initrd),
            (BOOM_ENTRY_OPTIONS, self.options),
        ]

        if self.bp:
            add_items.append((BOOM_ENTRY_VERSION, self.version))

        # Sort the item list to give stable list ordering on Py3.
        items = sorted(items, key=lambda i: i[0], reverse=True)

        return items + add_items

    def _dirty(self):
        """Mark this ``BootEntry`` as needing to be written to disk.

        A newly created ``BootEntry`` object is always dirty and
        a call to its ``write_entry()`` method will always write
        a new boot entry file. Writes may be avoided for entries
        that are not marked as dirty.

        A clean ``BootEntry`` is marked as dirty if a new value
        is written to any of its writable properties.

        :rtype: None
        """
        if self.read_only:
            raise ValueError(
                "Entry with boot_id='%s' is read-only." % self.disp_boot_id
            )

        # Clear cached boot_id: it will be regenerated on next access
        self.__boot_id = None
        self._unwritten = True

    def __os_id_from_comment(self, comment):
        """Retrieve OsProfile from BootEntry comment.

        Attempt to set this BootEntry's OsProfile using a comment
        string stored in the entry file. The comment must be of the
        form "OsIdentifier: <os_id>". If found the value is treated
        as authoritative and a reference to the corresponding
        ``OsProfile`` is stored  in the object's ``_osp`` member.

        Any comment lines that do not contain an OsIdentifier tag
        are returned as a multi-line string.

        :param comment: The comment to attempt to parse
        :returns: Comment lines not containing an OsIdentifier
        :rtype: str
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
                _log_debug_entry("Parsed os_id='%s' from comment", osp.disp_os_id)
            else:
                outlines += line + "\n"
        return outlines

    def __match_os_profile(self):
        """Attempt to find a matching OsProfile for this BootEntry.

        Attempt to guess the correct ``OsProfile`` to use with
        this ``BootEntry`` by probing each loaded ``OsProfile``
        in turn until a profile recognises the entry. If no match
        is found the entry's ``OsProfile`` is set to ``None``.

        Probing is only used in the case that a loaded entry has
        no embedded OsIdentifier string. All entries written by
        Boom include the OsIdentifier value: probing is primarily
        useful for entries that have been manually written or
        edited.
        """
        self._osp = match_os_profile(self)

    def __match_host_profile(self):
        """Attempt to find a matching HostProfile for this BootEntry.

        Try to find a ``HostProfile`` with a matching machine_id,
        and if one is found, wrap this ``BootEntry``'s operating
        system profile with the host.

        This method must be called with a valid ``BootParams``
        object attached.
        """
        if BOOM_ENTRY_MACHINE_ID in self._entry_data:
            machine_id = self._entry_data[BOOM_ENTRY_MACHINE_ID]
            hps = find_host_profiles(Selection(machine_id=machine_id))
            self._osp = hps[0] if hps else self._osp

        # Import add/del options from HostProfile if attached.
        if hasattr(self._osp, "add_opts"):
            self.bp.add_opts = self._osp.add_opts.split()

        if hasattr(self._osp, "del_opts"):
            self.bp.del_opts = self._osp.del_opts.split()

    def __from_data(self, entry_data, boot_params):
        """Initialise a new BootEntry from in-memory data.

        Initialise a new ``BootEntry`` object with data from the
        dictionary ``entry_data`` (and optionally the supplied
        ``BootParams`` object). The supplied dictionary should be
        indexed by Boom entry key names (``BOOM_ENTRY_*``).

        Raises ``ValueError`` if required keys are missing
        (``BOOM_ENTRY_TITLE``, and either ``BOOM_ENTRY_LINUX`` or
        ``BOOM_ENTRY_EFI``).

        This method should not be called directly: to build a new
        ``BootEntry`` object from in-memory data, use the class
        initialiser with the ``entry_data`` argument.

        :param entry_data: A dictionary mapping Boom boot entry key
                           names to values
        :param boot_params: Optional BootParams to attach to the new
                            BootEntry object
        :returns: None
        :rtype: None
        :raises: ValueError
        """
        if BOOM_ENTRY_TITLE not in entry_data:
            raise ValueError("BootEntry missing BOOM_ENTRY_TITLE")

        if BOOM_ENTRY_LINUX not in entry_data:
            if BOOM_ENTRY_EFI not in entry_data:
                raise ValueError(
                    "BootEntry missing BOOM_ENTRY_LINUX or" " BOOM_ENTRY_EFI"
                )

        self._entry_data = {}
        for key in [k for k in ENTRY_KEYS if k in entry_data]:
            self._entry_data[key] = entry_data[key]

        if not self._osp:
            self.__match_os_profile()

        self.machine_id = self.machine_id or ""
        self.architecture = self.architecture or ""

        if boot_params:
            self._bp = boot_params
            # boot_params is always authoritative
            self._entry_data[BOOM_ENTRY_VERSION] = self.bp.version
        else:
            _log_debug_entry(
                "Initialising BootParams() from BootEntry(boot_id='%s')", self.boot_id
            )
            # Attempt to recover BootParams from entry data
            self._bp = BootParams.from_entry(self)
            self._bp_generation = self._bp.generation

        if self.machine_id:
            # Wrap OsProfile in HostProfile if available
            self.__match_host_profile()

        if not self.read_only:

            def _pop_if_set(key):
                if key in _entry_data:
                    if _entry_data[key] == getattr(self, KEY_MAP[key]):
                        _entry_data.pop(key)

            # Copy the current _entry_data and clear self._entry_data to
            # allow comparison of stored value with template.
            _entry_data = self._entry_data
            self._entry_data = {}

            # Clear templated keys from _entry_data and if the value
            # read from entry_data is identical to that generated by the
            # current OsProfile and BootParams.
            _pop_if_set(BOOM_ENTRY_VERSION)
            _pop_if_set(BOOM_ENTRY_LINUX)
            _pop_if_set(BOOM_ENTRY_INITRD)
            _pop_if_set(BOOM_ENTRY_OPTIONS)
            self._entry_data = _entry_data

    def __from_file(self, entry_file, boot_params):
        """Initialise a new BootEntry from on-disk data.

        Initialise a new ``BootEntry`` using the entry data in
        ``entry_file`` (and optionally the supplied ``BootParams``
        object).

        Raises ``ValueError`` if required keys are missing
        (``BOOM_ENTRY_TITLE``, and either ``BOOM_ENTRY_LINUX`` or
        ``BOOM_ENTRY_EFI``).

        This method should not be called directly: to build a new
        ``BootEntry`` object from entry file data, use the class
        initialiser with the ``entry_file`` argument.

        :param entry_file: The path to a file containing a BLS boot
                           entry
        :param boot_params: Optional BootParams to attach to the new
                            BootEntry object
        :returns: None
        :rtype: None
        :raises: ValueError
        """

        def machine_id_from_filename(filename):
            """Try to obtain a machine-id value from a BLS entry file name.

            :param filename: The file name of the BLS snippet.
            :param returns: The machine-id or the empty string if it
                            could not be read.
            """
            machine_id_len = 32
            machine_id_chars = "0123456789abcdef"
            try:
                maybe_machine_id = filename.split("-")[0]
            except ValueError:
                return ""
            if len(maybe_machine_id) != machine_id_len:
                return ""
            for c in maybe_machine_id:
                if c not in machine_id_chars:
                    return ""
            return maybe_machine_id

        entry_data = {}
        comments = {}
        comment = ""

        entry_basename = basename(entry_file)
        _log_debug("Loading BootEntry from '%s'", entry_basename)
        self._last_path = entry_file

        with open(entry_file, "r") as ef:
            for line in ef:
                if blank_or_comment(line):
                    comment += line if line else ""
                else:
                    bls_key, value = parse_name_value(
                        line, separator=None, allow_empty=True
                    )
                    # Convert BLS key name to Boom notation
                    key = _transform_key(bls_key)
                    if key not in MAP_KEY:
                        raise LookupError("Unknown BLS key '%s'" % bls_key)
                    key = MAP_KEY[_transform_key(bls_key)]
                    entry_data[key] = value
                    if comment:
                        comment = self.__os_id_from_comment(comment)
                        if not comment:
                            continue
                        comments[key] = comment
                        comment = ""
        self._comments = comments

        # Red Hat native BLS entries do not set the machine-id BLS key:
        # this does not matter when we are reading and displaying the
        # entry, but it becomes important when cloning since we want to
        # use the BOOM_ENTRY_MACHINE_ID value as the first component of
        # the file name. Handle these entries by reading the machine-id
        # value from the file name and setting the _suppress_machine_id
        # attribute on the BootEntry. This prevents the machine-id from
        # appearing in string representations of the BootEntry or being
        # part of the boot_id calculation, but is not copied across a
        # clone operation (meaning that the cloned entry has normal boom
        # machine-id handling).
        if BOOM_ENTRY_MACHINE_ID not in entry_data:
            machine_id = machine_id_from_filename(entry_basename)
            if machine_id:
                entry_data[BOOM_ENTRY_MACHINE_ID] = machine_id
                self._suppress_machine_id = True

        self.__from_data(entry_data, boot_params)

        match = re.match(BOOT_ENTRIES_PATTERN, entry_basename)
        if not match or len(match.groups()) <= 1:
            _log_info("Marking unknown boot entry as read-only: %s", entry_basename)
            self.read_only = True
        else:
            if self.disp_boot_id != match.group(2):
                _log_info("Entry file name does not match boot_id: %s", entry_basename)
                self.update_entry(force=True)

        self._unwritten = False

    def __init__(
        self,
        title=None,
        machine_id=None,
        osprofile=None,
        boot_params=None,
        entry_file=None,
        entry_data=None,
        architecture=None,
        allow_no_dev=False,
    ):
        """Initialise new BootEntry.

        Initialise a new ``BootEntry`` object from the specified
        file or using the supplied values.

        If ``osprofile`` is specified the profile is attached to the
        new ``BootEntry`` and will be used to supply templates for
        ``BootEntry`` values.

        A ``BootParams`` object may be supplied using the
        ``boot_params`` keyword argument. The object will be used to
        provide values for substitution using the patterns defined by
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
        ``BOOM_ENTRY_*`` keys to ``BootEntry`` values. It may be used to
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

        :param architecture: An optional BLS architecture string.

        :returns: A new ``BootEntry`` object.

        :rtype: BootEntry
        """
        # An osprofile kwarg always takes precedent over either an
        # 'OsIdentifier' comment or a matched osprofile value.
        self._osp = osprofile

        if entry_data:
            self.__from_data(entry_data, boot_params)
            return
        if entry_file:
            self.__from_file(entry_file, boot_params)
            return

        self._unwritten = True

        self.bp = boot_params

        # The BootEntry._entry_data dictionary contains data for an existing
        # BootEntry that has been read from disk, as well as any overridden
        # fields for a new BootEntry with an OsProfile attached.
        self._entry_data = {}

        def title_empty(osp, title):
            if osp and not osp.title:
                return True
            elif not osp and not title:
                return True
            return False

        if title:
            self.title = title
        elif title_empty(self._osp, title):
            raise ValueError("BootEntry title cannot be empty")

        self.machine_id = machine_id or ""
        self.architecture = architecture or ""

        if not self._osp:
            self.__match_os_profile()

        if self.machine_id:
            # Wrap OsProfile in HostProfile if available
            self.__match_host_profile()

        if self.bp:
            if not allow_no_dev:
                check_root_device(self.bp.root_device)

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
        * ``%{os_name}`` The OS Profile name
        * ``%{os_short_name`` The OS Profile short name
        * ``%{os_version}`` The OS Profile version
        * ``%{os_version id`` The OS Profile version ID

        :param fmt: The string to be formatted.

        :returns: The formatted string
        :rtype: str
        """
        key_format = "%%{%s}"
        bp = self.bp

        if not fmt:
            return ""

        # Table-driven key formatting
        #
        # Each entry in the format_key_specs table specifies a list of
        # possible key substitutions to perform for the named key. Each
        # entry of the key_spec list contains a dictionary containing
        # one or more attribute sources or predicates.
        #
        # A key substitution is evaluated if at least one of the listed
        # attribute sources is defined, and if all defined predicates
        # evaluate to True. A predicate must be a Python callable
        # accepting no arguments and returning a boolean. A key_spec
        # may also specify an explicit list of needed objects, "bp",
        # or "osp", that must exist to evaluate predicates.
        #
        # Several helper functions exist to obtain key values from the
        # appropriate data source (accounting for keys that exist in
        # multiple objects as well as keys that return None or empty
        # values), to test key_spec predicates, and to safely obtain
        # function attributes where the containing object may or may
        # not exist.
        def get_key_attr(key_spec):
            """Return a key's value attribute.

            Return a value from either `BootParams`, `OsProfile`,
            or `BootEntry`. Each source is tested in order and the
            value is taken from the first object type with a value
            for the named key.
            """

            def have_attr():
                """Test whether any attribute source for this key exists."""
                attrs_vals = [(BP_ATTR, bp), (OSP_ATTR, self._osp), (BE_ATTR, True)]
                have = False
                for attr, source in attrs_vals:
                    if attr in key_spec:
                        have |= source is not None
                return have

            val_fmt = "%s" if VAL_FMT not in key_spec else key_spec[VAL_FMT]

            if have_attr():
                if BP_ATTR in key_spec and bp:
                    value = getattr(bp, key_spec[BP_ATTR])
                elif OSP_ATTR in key_spec:
                    value = getattr(self._osp, key_spec[OSP_ATTR])
                elif BE_ATTR in key_spec:
                    value = getattr(self, key_spec[BE_ATTR])
                return val_fmt % value if value is not None else None
            else:
                return None

        def test_predicates(key_spec):
            """Test all defined predicate functions and return `True` if
            all evaluate `True`, or `False` otherwise.
            """
            if PRED_FN not in key_spec:
                return True
            predicates = key_spec[PRED_FN]
            # Ignore invalid predicates
            return all([fn() for fn in predicates if fn])

        def mkpred(obj, fn):
            """Return a callable predicate function for method ``fn`` of
            object ``obj`` if ``obj`` is valid and contains ``fn``,
            or ``None`` otherwise.

            This is used to safely build predicate function lists
            whether or not the objects they reference are defined
            or not for a given substitution key.
            """
            return getattr(obj, fn) if obj else None

        # Key spec constants
        BE_ATTR = "be_attr"
        BP_ATTR = "bp_attr"
        OSP_ATTR = "osp_attr"
        PRED_FN = "pred_fn"
        VAL_FMT = "val_fmt"
        NEEDS = "needs"

        format_key_specs = {
            FMT_VERSION: [{BE_ATTR: "version", BP_ATTR: "version"}],
            FMT_LVM_ROOT_LV: [{BP_ATTR: "lvm_root_lv"}],
            FMT_LVM_ROOT_OPTS: [{OSP_ATTR: "root_opts_lvm2"}],
            FMT_BTRFS_ROOT_OPTS: [{OSP_ATTR: "root_opts_btrfs"}],
            FMT_BTRFS_SUBVOLUME: [
                {
                    BP_ATTR: "btrfs_subvol_id",
                    NEEDS: "bp",
                    PRED_FN: [mkpred(bp, "has_btrfs")],
                    VAL_FMT: "subvolid=%s",
                },
                {
                    BP_ATTR: "btrfs_subvol_path",
                    NEEDS: "bp",
                    PRED_FN: [mkpred(bp, "has_btrfs")],
                    VAL_FMT: "subvol=%s",
                },
            ],
            FMT_STRATIS_POOL_UUID: [
                {
                    BP_ATTR: "stratis_pool_uuid",
                    NEEDS: "bp",
                    PRED_FN: [mkpred(bp, "has_stratis")],
                }
            ],
            FMT_ROOT_DEVICE: [{BP_ATTR: "root_device", NEEDS: "bp"}],
            FMT_ROOT_OPTS: [{BE_ATTR: "root_opts", NEEDS: "bp"}],
            FMT_KERNEL: [{BE_ATTR: "linux", NEEDS: "bp"}],
            FMT_INITRAMFS: [{BE_ATTR: "initrd", NEEDS: "bp"}],
            FMT_OS_NAME: [{OSP_ATTR: "os_name"}],
            FMT_OS_SHORT_NAME: [{OSP_ATTR: "os_short_name"}],
            FMT_OS_VERSION: [{OSP_ATTR: "os_version"}],
            FMT_OS_VERSION_ID: [{OSP_ATTR: "os_version_id"}],
        }

        for key_name in format_key_specs.keys():
            key = key_format % key_name
            if key not in fmt:
                continue
            for key_spec in format_key_specs[key_name]:
                # Check NEEDS
                for k in key_spec.keys():
                    if k == NEEDS:
                        if key_spec[k] == "bp" and not bp:
                            continue
                        if key_spec[k] == "osp" and not self._osp:
                            continue
                if not test_predicates(key_spec):
                    continue
                # A key value of None means the key should not be substituted:
                # this occurs when accessing a templated attribute of an entry
                # that has no attached OsProfile (in which case the format key
                # is retained in the formatted text).
                #
                # If the value is not None, but contains the empty string, the
                # value is substituted as normal.
                value = get_key_attr(key_spec)
                if value is None:
                    continue
                fmt = fmt.replace(key, value)

        return fmt

    def __generate_boot_id(self):
        """Generate a new boot_id value.

        Generate a new sha1 profile identifier for this entry,
        using the title, version, root_device and any defined
        LVM2 or BTRFS snapshot parameters.

        :returns: A ``boot_id`` string
        :rtype: str
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
        boot_id = sha1(
            self.__str(no_boot_id=True).encode("utf-8"), usedforsecurity=False
        ).hexdigest()
        return boot_id

    def _entry_data_property(self, name):
        """Return property value from entry data.

        :param name: The boom key name of the property to return
        :returns: The property value from the entry data dictionary
        """
        if self._entry_data and name in self._entry_data:
            return self._entry_data[name]
        return None

    def _have_optional_key(self, key):
        """Return ``True`` if optional BLS key ``key`` is permitted by
        the attached ``OsProfile``, or ``False`` otherwise.
        """
        if not self._osp or not self._osp.optional_keys:
            return False
        if key not in self._osp.optional_keys:
            return False
        return True

    def expanded(self):
        """Return a string representation of this ``BootEntry``, with
        any bootloader environment variables expanded to their
        current values.

        :returns: A string representation of this ``BootEntry``.
        :rtype: string
        """
        return self.__str(expand=True)

    @property
    def bp(self):
        """The ``BootParams`` object associated with this ``BootEntry``."""
        return self._bp

    @bp.setter
    def bp(self, value):
        """Set the ``BootParams`` object associated with this
        ``BootEntry``.
        """
        self._dirty()
        self._bp = value
        self._bp_generation = self._bp.generation if self._bp else 0

    @property
    def disp_boot_id(self):
        """The display boot_id of this entry.

        Return the shortest prefix of this BootEntry's boot_id that
        is unique within the current set of loaded entries.

        :getter: return this BootEntry's boot_id.
        :type: str
        """
        return self.boot_id[: min_boot_id_width()]

    @property
    def boot_id(self):
        """A SHA1 digest that uniquely identifies this ``BootEntry``.

        :getter: return this ``BootEntry``'s ``boot_id``.
        :type: string
        """
        # Mark ourself dirty if boot parameters have changed.
        if self.bp and self.bp.generation != self._bp_generation:
            self._bp_generation = self.bp.generation
            self._dirty()
        if not self.__boot_id or self._unwritten:
            self.__boot_id = self.__generate_boot_id()
            _log_debug_entry("Generated new boot_id='%s'", self.__boot_id)
        return self.__boot_id

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
        root_opts = []

        if bp.lvm_root_lv:
            lvm_opts = self._apply_format(osp.root_opts_lvm2)
            root_opts.append(lvm_opts)

        if bp.btrfs_subvol_id or bp.btrfs_subvol_path:
            btrfs_opts = self._apply_format(osp.root_opts_btrfs)
            root_opts.append(btrfs_opts)

        if is_stratis_device_path(self.bp.root_device):
            stratis_opts = self._apply_format(ROOT_OPTS_STRATIS)
            root_opts.append(stratis_opts)

        return " ".join(root_opts)

    @property
    def title(self):
        """The title of this ``BootEntry``.

        :getter: returns the ``BootEntry`` title.
        :setter: sets this ``BootEntry`` object's title.
        :type: string
        """
        if BOOM_ENTRY_TITLE in self._entry_data:
            return self._entry_data_property(BOOM_ENTRY_TITLE)

        if not self._osp or not self.bp:
            return ""

        osp = self._osp
        return self._apply_format(osp.title)

    @title.setter
    def title(self, title):
        if not title:
            # It is valid to set an empty title in a HostProfile as long
            # as the OsProfile defines one.
            if not self._osp or not self._osp.title:
                raise ValueError("Entry title cannot be empty")
        self._entry_data[BOOM_ENTRY_TITLE] = title
        self._dirty()

    @property
    def machine_id(self):
        """The machine_id of this ``BootEntry``.

        :getter: returns this ``BootEntry`` object's ``machine_id``.
        :setter: sets this ``BootEntry`` object's ``machine_id``.
        :type: string
        """
        return self._entry_data_property(BOOM_ENTRY_MACHINE_ID)

    @machine_id.setter
    def machine_id(self, machine_id):
        self._entry_data[BOOM_ENTRY_MACHINE_ID] = machine_id
        self._dirty()

    @property
    def version(self):
        """The version string associated with this ``BootEntry``.

        :getter: returns this ``BootEntry`` object's ``version``.
        :setter: sets this ``BootEntry`` object's ``version``.
        :type: string
        """
        if self.bp and BOOM_ENTRY_VERSION not in self._entry_data:
            return self.bp.version
        return self._entry_data_property(BOOM_ENTRY_VERSION)

    @version.setter
    def version(self, version):
        self._entry_data[BOOM_ENTRY_VERSION] = version
        self._dirty()

    def _options(self, expand=False):
        """The command line options for this ``BootEntry``, optionally
        expanding any bootloader environment variables to their
        current values.

        :param expand: Whether or not to expand bootloader
                       environment variable references.
        :rtype: string
        """

        def add_opts(opts, append):
            """Append additional kernel options to this options string.

            Format the elements of list ``append`` as a space separated
            string, and return them appended to the existing options
            string ``opts``.

            :param opts: A kernel command line options string.
            :param append: A list of additional options to append.
            :returns: A string with additional options appended.
            :rtype: string
            """
            extra = " ".join(append)
            return "%s %s" % (opts, extra) if append else opts

        def del_opt(opt, drop):
            """Return ``True`` if option ``opt`` should be dropped or
            ``False`` otherwise.

            Test the option ``opt`` against the drop specification ``drop``
            and return ``True`` if the option should be dropped according
            to the spec, or ``False`` otherwise.

            :param opt: A kernel command line option with or without value.
            :param drop: A drop specification in Boom del_opts notation
                         (see ``del_opts`` for further details of syntax).
            :returns: ``True`` if the option should be dropped or ``False``
                      otherwise.
            :rtype: bool
            """
            # "name" or "name=value"
            if opt in drop:
                return True

            # "name=" wildcard
            if ("%s=" % opt.split("=")[0]) in drop:
                return True
            return False

        def del_opts(opts, drop):
            """Remove template-supplied kernel options matching ``drop`` from
            options string ``opts``.

            A drop specification matches either a simple name, a name and
            its full value (in which case both must match), or a name,
            followed by '=', indicating that an option with value should
            be dropped regardless of the actual value:

            <name>         drop name
            <name>=        drop name and any value
            <name>=<value> drop name only if its value == value

            :param opts: A kernel command line options string.
            :param drop: A drop specification to apply to ``opts``.
            :returns: A kernel command line options string with options
                      matching ``drop`` removed.
            :rtype: string
            """
            return " ".join([o for o in opts.split() if not del_opt(o, drop)])

        def do_null(opts):
            """Dummy expansion function."""
            return opts

        # Optionally expand environment variable references.
        do_exp = _expand_vars if expand else do_null

        if BOOM_ENTRY_OPTIONS in self._entry_data:
            opts = self._entry_data_property(BOOM_ENTRY_OPTIONS)
            if self.bp and not self.read_only:
                opts = add_opts(opts, self.bp.add_opts)
                return do_exp(del_opts(opts, self.bp.del_opts))
            return do_exp(opts)

        if self._osp and self.bp:
            opts = self._apply_format(self._osp.options)
            opts = add_opts(opts, self.bp.add_opts)
            return do_exp(del_opts(opts, self.bp.del_opts))

        return ""

    @property
    def expand_options(self):
        """The command line options for this ``BootEntry``, with any
        bootloader environment variables expanded to their current
        values.

        Return the command line options for this ``BootEntry``,
        expanding any Boom or Grub2 substitution notation found.

        :getter: returns the command line for this ``BootEntry``.
        :setter: sets the command line for this ``BootEntry``.
        :type: string
        """
        return self._options(expand=True)

    @property
    def options(self):
        """The command line options for this ``BootEntry``, including
        any bootloader environment variable references as they
        appear.

        :getter: returns the command line for this ``BootEntry``.
        :setter: sets the command line for this ``BootEntry``.
        :type: string
        """
        return self._options()

    @options.setter
    def options(self, options):
        self._entry_data[BOOM_ENTRY_OPTIONS] = options
        self._dirty()

    @property
    def linux(self):
        """The bootable Linux image for this ``BootEntry``.

        :getter: returns the configured ``linux`` image.
        :setter: sets the configured ``linux`` image.
        :type: string
        """
        if not self._osp or BOOM_ENTRY_LINUX in self._entry_data:
            return self._entry_data_property(BOOM_ENTRY_LINUX)

        kernel_path = self._apply_format(self._osp.kernel_pattern)
        return kernel_path

    @linux.setter
    def linux(self, linux):
        self._entry_data[BOOM_ENTRY_LINUX] = linux
        self._dirty()

    def _initrd(self, expand=False):
        """Return the initrd string with or without variable expansion.

        Since some distributions use bootloader environment
        variables to define auxiliary initramfs images, the initrd
        property is optionally subject to the same variable
        expansion as the options property.

        :param expand: ``True`` if variables should be expanded or
                       ``False`` otherwise.
        :returns: An initrd string
        :rtype: string
        """
        if not self._osp or BOOM_ENTRY_INITRD in self._entry_data:
            initrd_string = self._entry_data_property(BOOM_ENTRY_INITRD)
            if expand:
                return _expand_vars(initrd_string)
            return initrd_string

        initramfs_path = self._apply_format(self._osp.initramfs_pattern)
        if expand:
            return _expand_vars(initrd_string)
        return initramfs_path

    @property
    def initrd(self):
        """The loadable initramfs image for this ``BootEntry``.

        :getter: returns the configured ``initrd`` image.
        :getter: sets the configured ``initrd`` image.
        :type: string
        """
        return self._initrd()

    @property
    def expand_initrd(self):
        """The loadable initramfs image for this ``BootEntry`` with any
        embedded bootloader variable references expanded.

        :getter: returns the configured ``initrd`` image.
        :getter: sets the configured ``initrd`` image.
        :type: string
        """
        return self._initrd(expand=True)

    @initrd.setter
    def initrd(self, initrd):
        self._entry_data[BOOM_ENTRY_INITRD] = initrd
        self._dirty()

    @property
    def efi(self):
        """The loadable EFI image for this ``BootEntry``.

        :getter: returns the configured EFI application image.
        :getter: sets the configured EFI application image.
        :type: string
        """
        return self._entry_data_property(BOOM_ENTRY_EFI)

    @efi.setter
    def efi(self, efi):
        self._entry_data[BOOM_ENTRY_EFI] = efi
        self._dirty()

    @property
    def devicetree(self):
        """The devicetree archive for this ``BootEntry``.

        :getter: returns the configured device tree archive.
        :getter: sets the configured device tree archive.
        :type: string
        """
        return self._entry_data_property(BOOM_ENTRY_DEVICETREE)

    @devicetree.setter
    def devicetree(self, devicetree):
        self._entry_data[BOOM_ENTRY_DEVICETREE] = devicetree
        self._dirty()

    @property
    def architecture(self):
        """The EFI machine type string for this ``BootEntry``.

        :getter: returns the configured architecture.
        :setter: sets the architecture for this entry.
        :type: string
        """
        return self._entry_data_property(BOOM_ENTRY_ARCHITECTURE)

    @architecture.setter
    def architecture(self, architecture):
        # The empty string means no architecture key
        machine_types = ["ia32", "x64", "ia64", "arm", "aa64", ""]
        if architecture and not architecture.lower() in machine_types:
            raise ValueError("Unknown architecture: '%s'" % architecture)
        self._entry_data[BOOM_ENTRY_ARCHITECTURE] = architecture
        self._dirty()

    @property
    def grub_users(self):
        """The current ``grub_users`` key for this entry.

        :getter: Return the current ``grub_users`` value.
        :setter: Store a new ``grub_users`` value.
        :type: string
        """
        bls_key = KEY_MAP[BOOM_ENTRY_GRUB_USERS]
        if not self._have_optional_key(bls_key):
            return ""
        return self._entry_data_property(BOOM_ENTRY_GRUB_USERS)

    @grub_users.setter
    def grub_users(self, grub_users):
        bls_key = KEY_MAP[BOOM_ENTRY_GRUB_USERS]
        if not self._have_optional_key(bls_key):
            raise ValueError(
                "OsProfile os_id=%s does not allow '%s'"
                % (self._osp.disp_os_id, bls_key)
            )
        self._entry_data[BOOM_ENTRY_GRUB_USERS] = grub_users

    @property
    def grub_arg(self):
        """The current ``grub_arg`` key for this entry.

        :getter: Return the current ``grub_arg`` value.
        :setter: Store a new ``grub_arg`` value.
        :type: string
        """
        bls_key = KEY_MAP[BOOM_ENTRY_GRUB_ARG]
        if not self._have_optional_key(bls_key):
            return ""
        return self._entry_data_property(BOOM_ENTRY_GRUB_ARG)

    @grub_arg.setter
    def grub_arg(self, grub_arg):
        bls_key = KEY_MAP[BOOM_ENTRY_GRUB_ARG]
        if not self._have_optional_key(bls_key):
            raise ValueError(
                "OsProfile os_id=%s does not allow '%s'"
                % (self._osp.disp_os_id, bls_key)
            )
        self._entry_data[BOOM_ENTRY_GRUB_ARG] = grub_arg

    @property
    def grub_class(self):
        """The current ``grub_class`` key for this entry.

        :getter: Return the current ``grub_class`` value.
        :setter: Store a new ``grub_class`` value.
        :type: string
        """
        bls_key = KEY_MAP[BOOM_ENTRY_GRUB_CLASS]
        if not self._have_optional_key(bls_key):
            return ""
        return self._entry_data_property(BOOM_ENTRY_GRUB_CLASS)

    @grub_class.setter
    def grub_class(self, grub_class):
        bls_key = KEY_MAP[BOOM_ENTRY_GRUB_CLASS]
        if not self._have_optional_key(bls_key):
            raise ValueError(
                "OsProfile os_id=%s does not allow '%s'"
                % (self._osp.disp_os_id, bls_key)
            )
        self._entry_data[BOOM_ENTRY_GRUB_CLASS] = grub_class

    @property
    def id(self):
        """The value of the ``id`` key for this entry.

        :getter: Return the current ``id`` value.
        :setter: Store a new ``id`` value.
        :type: string
        """
        bls_key = KEY_MAP[BOOM_ENTRY_GRUB_ID]
        if not self._have_optional_key(bls_key):
            return ""
        return self._entry_data_property(BOOM_ENTRY_GRUB_ID)

    @id.setter
    def id(self, ident):
        bls_key = KEY_MAP[BOOM_ENTRY_GRUB_ID]
        if not self._have_optional_key(bls_key):
            raise ValueError(
                "OsProfile os_id=%s does not allow '%s'"
                % (self._osp.disp_os_id, bls_key)
            )
        self._entry_data[BOOM_ENTRY_GRUB_ID] = ident

    @property
    def _entry_path(self):
        id_tuple = (self.machine_id, self.boot_id[0:7], self.version)
        file_name = BOOT_ENTRIES_FORMAT % id_tuple
        return path_join(boom_entries_path(), file_name)

    @property
    def entry_path(self):
        """The path to the on-disk file containing this ``BootEntry``."""
        if self.read_only:
            return self._last_path
        return self._entry_path

    def write_entry(self, force=False, expand=False):
        """Write out entry to disk.

        Write out this ``BootEntry``'s data to a file in BLS
        format to the path specified by ``boom_entries_path()``.

        The file will be named according to the entry's key values,
        and the value of the ``BOOT_ENTRIES_FORMAT`` constant.
        Currently the ``machine_id`` and ``version`` keys are used
        to construct the file name.

        If the value of ``force`` is ``False`` and the ``OsProfile``
        is not currently marked as dirty (either new, or modified
        since the last load operation) the write will be skipped.

        :param force: Force this entry to be written to disk even
                      if the entry is unmodified.
        :param expand: Expand bootloader environment variables in
                       on-disk entry.
        :raises: ``OSError`` if the temporary entry file cannot be
                 renamed, or if setting file permissions on the
                 new entry file fails.
        :rtype: None
        """
        if not self._unwritten and not force:
            return
        entry_path = self._entry_path
        (tmp_fd, tmp_path) = mkstemp(prefix="boom", dir=boom_entries_path())
        with fdopen(tmp_fd, "w") as f:
            # Our original file descriptor will be closed on exit from the
            # fdopen with statement: save a copy so that we can call fdatasync
            # once at the end of writing rather than on each loop iteration.
            tmp_fd = dup(tmp_fd)
            if self._osp:
                # Insert OsIdentifier comment at top-of-file
                f.write("#OsIdentifier: %s\n" % self._osp.os_id)
            if expand:
                f.write(self.expanded() + "\n")
            else:
                f.write(str(self) + "\n")
        try:
            fdatasync(tmp_fd)
            rename(tmp_path, entry_path)
            chmod(entry_path, BOOT_ENTRY_MODE)
        except Exception as e:
            _log_error("Error writing entry file %s: %s", entry_path, e)
            try:
                unlink(tmp_path)
            except Exception:
                _log_error("Error unlinking temporary path %s", tmp_path)
            raise e

        self._last_path = entry_path
        self._unwritten = False

        # Add this entry to the list of known on-disk entries
        _add_entry(self)

    def update_entry(self, force=False, expand=False):
        """Update on-disk entry.

        Update this ``BootEntry``'s on-disk data.

        The file will be named according to the entry's key values,
        and the value of the ``BOOT_ENTRIES_FORMAT`` constant.
        Currently the ``machine_id`` and ``version`` keys are used
        to construct the file name.

        If this ``BootEntry`` previously existed on-disk, and the
        ``boot_id`` has changed due to a change in entry key
        values, the old ``BootEntry`` file will be unlinked once
        the new data has been successfully written. If the entry
        does not already exist then calling this method is the
        equivalent of calling ``BootEntry.write_entry()``.

        If the value of ``force`` is ``False`` and the ``BootEntry``
        is not currently marked as dirty (either new, or modified
        since the last load operation) the write will be skipped.

        :param force: Force this entry to be written to disk even
                      if the entry is unmodified.
        :param expand: Expand bootloader environment variables in
                       on-disk entry.
        :raises: ``OSError`` if the temporary entry file cannot be
                 renamed, or if setting file permissions on the
                 new entry file fails.
        :rtype: None
        """
        # Cache old entry path
        to_unlink = self._last_path
        self.write_entry(force=force, expand=expand)
        _log_info("Rewrote entry %s as %s", self.disp_boot_id, self._entry_path)
        if self._entry_path != to_unlink:
            try:
                unlink(to_unlink)
            except Exception as e:
                _log_error("Error unlinking entry file %s: %s", to_unlink, e)

    def delete_entry(self):
        """Remove on-disk BootEntry file.

        Remove the on-disk entry corresponding to this ``BootEntry``
        object. This will permanently erase the current file
        (although the current data may be re-written at any time by
        calling ``write_entry()``).

        :rtype: ``NoneType``
        :raises: ``OsError`` if an error occurs removing the file or
                 ``ValueError`` if the entry does not exist.
        """
        if self.read_only:
            raise ValueError(
                "Cannot delete read-only boot " "entry: %s" % self._last_path
            )

        if not path_exists(self._entry_path):
            raise ValueError("Entry does not exist: %s" % self._entry_path)
        try:
            unlink(self._entry_path)
        except Exception as e:
            _log_error("Error removing entry file %s: %s", self._entry_path, e)
            raise

        if not self._unwritten:
            _del_entry(self)


__all__ = [
    # Module constants
    "BOOT_ENTRIES_FORMAT",
    "BOOT_ENTRY_MODE",
    # BootEntry keys
    "BOOM_ENTRY_TITLE",
    "BOOM_ENTRY_VERSION",
    "BOOM_ENTRY_MACHINE_ID",
    "BOOM_ENTRY_LINUX",
    "BOOM_ENTRY_INITRD",
    "BOOM_ENTRY_EFI",
    "BOOM_ENTRY_OPTIONS",
    "BOOM_ENTRY_DEVICETREE",
    "BOOM_ENTRY_GRUB_USERS",
    "BOOM_ENTRY_GRUB_ARG",
    "BOOM_ENTRY_GRUB_CLASS",
    "BOOM_ENTRY_GRUB_ID",
    # Lists of valid BootEntry keys
    "ENTRY_KEYS",
    "OPTIONAL_KEYS",
    # Root device pattern
    "DEV_PATTERN",
    # Boom root device error class
    "BoomRootDeviceError",
    # BootParams and BootEntry objects
    "BootParams",
    "BootEntry",
    # BLS Key lookup
    "key_to_bls_name",
    # Default values for optional BootEntry keys
    "optional_key_default",
    # Path configuration
    "boom_entries_path",
    # Entry lookup, load, and write functions
    "drop_entries",
    "load_entries",
    "write_entries",
    "find_entries",
    # Formatting
    "min_boot_id_width",
]

# vim: set et ts=4 sw=4 :
