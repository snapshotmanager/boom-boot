# Copyright Red Hat
#
# boom/_boom.py - Boom package initialisation
#
# SPDX-License-Identifier: GPL-2.0-only
"""This module provides the declarations, classes, and functions exposed
in the main ``boom`` module. Users of boom should not import this module
directly: it will be imported automatically with the top level module.
"""
from __future__ import print_function

from os.path import exists as path_exists, isabs, isdir, join as path_join
from os import listdir
import logging
import string

#: The location of the system ``/boot`` directory.
DEFAULT_BOOT_PATH = "/boot"

#: The default path for Boom configuration files.
DEFAULT_BOOM_DIR = "boom"

#: The root directory for Boom configuration files.
DEFAULT_BOOM_PATH = path_join(DEFAULT_BOOT_PATH, DEFAULT_BOOM_DIR)

#: The default directory name for the Boom cache.
DEFAULT_CACHE_DIR = "cache"

#: The path to the root directory of the Boom cache.
DEFAULT_CACHE_PATH = path_join(DEFAULT_BOOM_PATH, DEFAULT_CACHE_DIR)

#: Configuration file mode
BOOT_CONFIG_MODE = 0o644

#: The default configuration file location
BOOM_CONFIG_FILE = "boom.conf"
DEFAULT_BOOM_CONFIG_PATH = path_join(DEFAULT_BOOM_PATH, BOOM_CONFIG_FILE)
__boom_config_path = DEFAULT_BOOM_CONFIG_PATH

#: Kernel version string, in ``uname -r`` format.
FMT_VERSION = "version"
#: LVM2 root logical volume in ``vg/lv`` format.
FMT_LVM_ROOT_LV = "lvm_root_lv"
#: LVM2 kernel command line options
FMT_LVM_ROOT_OPTS = "lvm_root_opts"
#: BTRFS subvolume specification.
FMT_BTRFS_SUBVOLUME = "btrfs_subvolume"
#: BTRFS subvolume ID specification.
FMT_BTRFS_SUBVOL_ID = "btrfs_subvol_id"
#: BTRFS subvolume path specification.
FMT_BTRFS_SUBVOL_PATH = "btrfs_subvol_path"
#: BTRFS kernel command line options
FMT_BTRFS_ROOT_OPTS = "btrfs_root_opts"
#: Stratis pool UUID.
FMT_STRATIS_POOL_UUID = "stratis_pool_uuid"
#: Stratis kernel command line options.
FMT_STRATIS_ROOT_OPTS = "stratis_root_opts"
#: Root device path.
FMT_ROOT_DEVICE = "root_device"
#: Root device options.
FMT_ROOT_OPTS = "root_opts"
#: Linux kernel image
FMT_KERNEL = "kernel"
#: Initramfs image
FMT_INITRAMFS = "initramfs"
#: OS Profile name
FMT_OS_NAME = "os_name"
#: OS Profile short name
FMT_OS_SHORT_NAME = "os_short_name"
#: OS Profile version
FMT_OS_VERSION = "os_version"
#: OS Profile version ID
FMT_OS_VERSION_ID = "os_version_id"

#: List of all possible format keys.
FORMAT_KEYS = [
    FMT_VERSION,
    FMT_LVM_ROOT_LV,
    FMT_LVM_ROOT_OPTS,
    FMT_BTRFS_SUBVOL_ID,
    FMT_BTRFS_SUBVOL_PATH,
    FMT_BTRFS_SUBVOLUME,
    FMT_BTRFS_ROOT_OPTS,
    FMT_STRATIS_POOL_UUID,
    FMT_ROOT_DEVICE,
    FMT_ROOT_OPTS,
    FMT_KERNEL,
    FMT_INITRAMFS,
    FMT_OS_NAME,
    FMT_OS_SHORT_NAME,
    FMT_OS_VERSION,
    FMT_OS_VERSION_ID,
]

#: Root options for Stratis root file systems
ROOT_OPTS_STRATIS = "stratis.rootfs.pool_uuid=%{stratis_pool_uuid}"

# Root options for btrfs volumes

#: Volume specified by subvol path
ROOT_OPTS_BTRFS_PATH = "subvol=%{btrfs_subvol_path}"

#: Volume specified by subvol ID
ROOT_OPTS_BTRFS_ID = "subvolid=%{btrfs_subvol_id}"

#
# Logging
#

BOOM_LOG_DEBUG = logging.DEBUG
BOOM_LOG_INFO = logging.INFO
BOOM_LOG_WARN = logging.WARNING
BOOM_LOG_ERROR = logging.ERROR

_log_levels = (BOOM_LOG_DEBUG, BOOM_LOG_INFO, BOOM_LOG_WARN, BOOM_LOG_ERROR)

_log = logging.getLogger(__name__)

_log_debug = _log.debug
_log_info = _log.info
_log_warn = _log.warning
_log_error = _log.error

# Boom debugging levels
BOOM_DEBUG_PROFILE = 1
BOOM_DEBUG_ENTRY = 2
BOOM_DEBUG_REPORT = 4
BOOM_DEBUG_COMMAND = 8
BOOM_DEBUG_CACHE = 16
BOOM_DEBUG_STRATIS = 32
BOOM_DEBUG_ALL = (
    BOOM_DEBUG_PROFILE
    | BOOM_DEBUG_ENTRY
    | BOOM_DEBUG_REPORT
    | BOOM_DEBUG_COMMAND
    | BOOM_DEBUG_CACHE
    | BOOM_DEBUG_STRATIS
)

__debug_mask = 0


class BoomError(Exception):
    """Base class of all Boom exceptions."""

    pass


class BoomLogger(logging.Logger):
    """BoomLogger()

    Boom logging wrapper class: wrap the Logger.debug() method
    to allow filtering of submodule debug messages by log mask.

    This allows us to selectively control which messages are
    logged in the library without having to tamper with the
    Handler, Filter or Formatter configurations (which belong
    to the client application using the library).
    """

    mask_bits = 0

    def set_debug_mask(self, mask_bits):
        """Set the debug mask for this ``BoomLogger``.

        This should normally be set to the ``BOOM_DEBUG_*`` value
        corresponding to the ``boom`` sub-module that this instance
        of ``BoomLogger`` belongs to.

        :param mask_bits: The bits to set in this logger's mask.
        :rtype: None
        """
        if mask_bits < 0 or mask_bits > BOOM_DEBUG_ALL:
            raise ValueError(
                "Invalid BoomLogger mask bits: 0x%x" % (mask_bits & ~BOOM_DEBUG_ALL)
            )

        self.mask_bits = mask_bits

    def debug_masked(self, msg, *args, **kwargs):
        """Log a debug message if it passes the current debug mask.

        Log the specified message if it passes the current logger
        debug mask.

        :param msg: the message to be logged
        :rtype: None
        """
        if self.mask_bits & get_debug_mask():
            self.debug(msg, *args, **kwargs)


logging.setLoggerClass(BoomLogger)


def get_debug_mask():
    """Return the current debug mask for the ``boom`` package.

    :returns: The current debug mask value
    :rtype: int
    """
    return __debug_mask


def set_debug_mask(mask):
    """Set the debug mask for the ``boom`` package.

    :param mask: the logical OR of the ``BOOM_DEBUG_*``
                 values to log.
    :rtype: None
    """
    global __debug_mask
    if mask < 0 or mask > BOOM_DEBUG_ALL:
        raise ValueError("Invalid boom debug mask: %d" % mask)
    __debug_mask = mask


class BoomConfig(object):
    """Class representing boom persistent configuration values."""

    # Initialise members from global defaults

    boot_path = DEFAULT_BOOT_PATH
    boom_path = DEFAULT_BOOM_PATH

    legacy_enable = False
    legacy_format = "grub1"
    legacy_sync = True

    cache_enable = True
    cache_auto_clean = True
    cache_path = DEFAULT_CACHE_PATH

    def __str__(self):
        """Return a string representation of this ``BoomConfig`` in
        boom.conf (INI) notation.
        """
        cstr = ""
        cstr += "[global]\n"
        cstr += "boot_root = %s\n" % self.boot_path
        cstr += "boom_root = %s\n\n" % self.boom_path

        cstr += "[legacy]\n"
        cstr += "enable = %s\n" % self.legacy_enable
        cstr += "format = %s\n" % self.legacy_format
        cstr += "sync = %s\n\n" % self.legacy_sync

        cstr += "[cache]\n"
        cstr += "enable = %s\n" % self.cache_enable
        cstr += "auto_clean = %s\n" % self.cache_auto_clean
        cstr += "cache_path = %s\n" % self.cache_path

        return cstr

    def __repr__(self):
        """Return a string representation of this ``BoomConfig`` in
        BoomConfig initialiser notation.
        """
        cstr = 'BoomConfig(boot_path="%s", boom_path="%s", ' % (
            self.boot_path,
            self.boom_path,
        )
        cstr += 'enable_legacy=%s, legacy_format="%s", ' % (
            self.legacy_enable,
            self.legacy_format,
        )
        cstr += "legacy_sync=%s, " % self.legacy_sync
        cstr += "cache_enable=%s, " % self.cache_enable
        cstr += "auto_clean=%s, " % self.cache_auto_clean
        cstr += 'cache_path="%s")' % self.cache_path

        return cstr

    def __init__(
        self,
        boot_path=None,
        boom_path=None,
        legacy_enable=None,
        legacy_format=None,
        legacy_sync=None,
        cache_enable=None,
        cache_auto_clean=None,
        cache_path=None,
    ):
        """Initialise a new ``BoomConfig`` object with the supplied
        configuration values, or defaults for any unset arguments.

        :param boot_path: the path to the system /boot volume
        :param boom_path: the path to the boom configuration dir
        :param legacy_enable: enable legacy bootloader support
        :param legacy_format: the legacy bootlodaer format to write
        :param legacy_sync: the legacy sync mode
        :param cache_enable: enable boot image cache
        :param cache_auto_clean: automatically clean up unused boot
                                 images
        :param cache_path: the path to the boot image cache
        """
        self.boot_path = boot_path or self.boot_path
        self.boom_path = boom_path or self.boom_path
        self.legacy_enable = legacy_enable or self.legacy_enable
        self.legacy_format = legacy_format or self.legacy_format
        self.legacy_sync = legacy_sync or self.legacy_sync
        self.cache_enable = cache_enable or self.cache_enable
        self.cache_auto_clean = cache_auto_clean or self.cache_auto_clean
        self.cache_path = cache_path or self.cache_path


__config = BoomConfig()


def set_boom_config(config):
    """Set the active configuration to the object ``config`` (which may
    be any class that includes the ``BoomConfig`` attributes).

    :param config: a configuration object
    :returns: None
    :raises: TypeError if ``config`` does not appear to have the
             correct attributes.
    """
    global __config

    def has_value(obj, attr):
        return hasattr(obj, attr) and getattr(obj, attr) is not None

    if not (has_value(config, "boot_path") and has_value(config, "boom_path")):
        raise TypeError("config does not appear to be a BoomConfig object.")

    __config = config


def get_boom_config():
    """Return the active ``BoomConfig`` object.

    :rtype: BoomConfig
    :returns: the active configuration object
    """
    return __config


def get_boot_path():
    """Return the currently configured boot file system path.

    :returns: the path to the /boot file system.
    :rtype: str
    """
    return __config.boot_path


def get_boom_path():
    """Return the currently configured boom configuration path.

    :returns: the path to the BOOT/boom directory.
    :rtype: str
    """
    return __config.boom_path


def get_cache_path():
    """Return the currently configured boot file system path.

    :returns: the path to the /boot file system.
    :rtype: str
    """
    return __config.cache_path


def set_boot_path(boot_path):
    """Sets the location of the boot file system to ``boot_path``.

    The path defaults to the '/boot/' mount directory in the root
    file system: this may be overridden by calling this function
    with a different path.

    Calling ``set_boom_root_path()`` will re-set the value returned
    by ``get_boom_path()`` to the default boom configuration sub-
    directory within the new boot file system. The location of the
    boom configuration path may be configured separately by calling
    ``set_boom_root_path()`` after setting the boot path.

    :param boot_path: the path to the 'boom/' directory containing
                      boom profiles and configuration.
    :returnsNone: ``None``
    :raises: ValueError if ``boot_path`` does not exist.
    """
    global __config
    if not isabs(boot_path):
        raise ValueError("boot_path must be an absolute path: %s" % boot_path)

    if not path_exists(boot_path):
        raise ValueError("Path '%s' does not exist" % boot_path)

    __config.boot_path = boot_path
    _log_debug("Set boot path to: %s", boot_path)
    __config.boom_path = path_join(boot_path, DEFAULT_BOOM_DIR)

    # If a boom/ directory exists at the boot path, automatically set
    # the boom path to it. Otherwise, we assume that the caller will
    # set the path explicitly to some non-default location.
    boom_path = path_join(boot_path, "boom")
    if path_exists(boom_path) and isdir(boom_path):
        set_boom_path(path_join(__config.boot_path, "boom"))


def set_boom_path(boom_path):
    """Set the location of the boom configuration directory.

    Set the location of the boom configuration path stored in
    the active configuration to ``boom_path``. This defaults to the
    'boom/' sub-directory in the boot file system specified by
    ``config.boot_path``: this may be overridden by calling this
    function with a different path.

    :param boom_path: the path to the 'boom/' directory containing
                      boom profiles and configuration.
    :returns: ``None``
    :raises: ValueError if ``boom_path`` does not exist.
    """
    global __config
    err_str = "Boom path %s does not exist" % boom_path
    if isabs(boom_path) and not path_exists(boom_path):
        raise ValueError(err_str)
    elif not path_exists(path_join(__config.boot_path, boom_path)):
        raise ValueError(err_str)

    if not isabs(boom_path):
        boom_path = path_join(__config.boot_path, boom_path)

    if not path_exists(path_join(boom_path, "profiles")):
        raise ValueError(
            "Path does not contain a valid boom configuration"
            ": %s" % path_join(boom_path, "profiles")
        )

    _log_debug("Set boom path to: %s", boom_path)
    __config.boom_path = boom_path
    set_boom_config_path(__config.boom_path)

    cache_path = path_join(boom_path, "cache")
    if path_exists(cache_path):
        set_cache_path(cache_path)


def set_cache_path(cache_path):
    """Set the location of the boom image cache directory.

    Set the location of the boom image cache path stored in
    the active configuration to ``cache_path``. This defaults to the
    'cache/' sub-directory in the boom configuration directory
    ``config.boom_path``: this may be overridden by calling this
    function with a different path.

    :param cache_path: the path to the 'cache/' directory containing
                      cached boot images.
    :returns: ``None``
    :raises: ValueError if ``cache_path`` does not exist.
    """
    global __config
    err_str = "Cache path %s does not exist" % cache_path
    if isabs(cache_path) and not path_exists(cache_path):
        raise ValueError(err_str)
    elif not path_exists(path_join(__config.cache_path, cache_path)):
        raise ValueError(err_str)

    if not isabs(cache_path):
        cache_path = path_join(__config.cache_path, cache_path)

    __config.cache_path = cache_path
    _log_debug("Set cache path to: %s", cache_path)


def get_boom_config_path():
    """Return the currently configured boom configuration file path.

    :rtype: str
    :returns: the current boom configuration file path
    """
    return __boom_config_path


def set_boom_config_path(path):
    """Set the boom configuration file path."""
    global __boom_config_path
    path = path or get_boom_config_path()
    if not isabs(path):
        path = path_join(get_boom_path())
    if isdir(path):
        path = path_join(path, BOOM_CONFIG_FILE)
    if not path_exists(path):
        raise IOError(ENOENT, "File not found: '%s'" % path)
    __boom_config_path = path
    _log_debug("set boom_config_path to '%s'", path)


def parse_btrfs_subvol(subvol):
    """Parse a BTRFS subvolume string.

    Parse a BTRFS subvolume specification into either a subvolume
    path string, or a string containing a subvolume identifier.

    :param subvol: The subvolume parameter to parse
    :returns: A string containing the subvolume path or ID
    :rtype: ``str``
    :raises: ValueError if no valid subvolume was found
    """
    if not subvol:
        return (None, None)

    subvol_path = None
    subvol_id = None
    if subvol.isnumeric():
        subvol_id = int(subvol)
        subvol_id = str(subvol_id)
    else:
        subvol_path = subvol

    return (subvol_path, subvol_id)


#
# Selection criteria class
#


class Selection(object):
    """Selection()
    Selection criteria for boom BootEntry, OsProfile HostProfile,
    and BootParams.

    Selection criteria specified as a simple boolean AND of all
    criteria with a non-None value.
    """

    # BootEntry fields
    boot_id = None
    title = None
    version = None
    machine_id = None
    linux = None
    initrd = None
    efi = None
    options = None
    devicetree = None

    # BootParams fields
    root_device = None
    lvm_root_lv = None
    btrfs_subvol_path = None
    btrfs_subvol_id = None

    # OsProfile fields
    os_id = None
    os_name = None
    os_short_name = None
    os_version = None
    os_version_id = None
    os_uname_pattern = None
    os_kernel_pattern = None
    os_initramfs_pattern = None
    os_root_opts_lvm2 = None
    os_root_opts_btrfs = None
    os_options = None

    # Should results include the null profile?
    allow_null_profile = False

    # HostProfile fields
    host_id = None
    host_name = None
    host_label = None
    host_short_name = None
    host_add_opts = None
    host_del_opts = None

    # Cache fields
    path = None
    orig_path = None
    img_id = None

    #: Selection criteria applying to BootEntry objects
    entry_attrs = [
        "boot_id",
        "title",
        "version",
        "machine_id",
        "linux",
        "initrd",
        "efi",
        "options",
        "devicetree",
        "path",
    ]

    #: Selection criteria applying to BootParams objects
    params_attrs = [
        "root_device",
        "lvm_root_lv",
        "btrfs_subvol_path",
        "btrfs_subvol_id",
    ]

    #: Selection criteria applying to OsProfile objects
    profile_attrs = [
        "os_id",
        "os_name",
        "os_short_name",
        "os_version",
        "os_version_id",
        "os_uname_pattern",
        "os_kernel_pattern",
        "os_initramfs_pattern",
        "os_root_opts_lvm2",
        "os_root_opts_btrfs",
        "os_options",
    ]

    #: Selection criteria applying to HostProfile objects
    host_attrs = [
        "host_id",
        "host_name",
        "host_label",
        "host_short_name",
        "host_add_opts",
        "host_del_opts",
        "machine_id",
    ]

    #: Cache selection supports a subset of entry_attrs
    cache_attrs = [
        "version",
        "linux",
        "initrd",
        "path",
        "orig_path",
        "timestamp",
        "img_id",
    ]

    all_attrs = entry_attrs + params_attrs + profile_attrs + host_attrs + cache_attrs

    def __str__(self):
        """Format this ``Selection`` object as a human readable string.

        :returns: A human readable string representation of this
                  Selection object
        :rtype: string
        """
        all_attrs = self.all_attrs
        attrs = [attr for attr in all_attrs if self.__attr_has_value(attr)]
        strval = ""
        tail = ", "
        for attr in set(attrs):
            strval += "%s='%s'%s" % (attr, getattr(self, attr), tail)
        return strval.rstrip(tail)

    def __repr__(self):
        """Format this ``Selection`` object as a machine readable string.

        The returned string may be passed to the Selection
        initialiser to duplicate the original Selection.

        :returns: A machine readable string representation of this
                  Selection object
        :rtype: string
        """
        return "Selection(" + str(self) + ")"

    def __init__(
        self,
        boot_id=None,
        title=title,
        version=version,
        machine_id=None,
        linux=None,
        initrd=None,
        efi=None,
        root_device=None,
        lvm_root_lv=None,
        btrfs_subvol_path=None,
        btrfs_subvol_id=None,
        os_id=None,
        os_name=None,
        os_short_name=None,
        os_version=None,
        os_version_id=None,
        os_options=None,
        os_uname_pattern=None,
        os_kernel_pattern=None,
        os_initramfs_pattern=None,
        allow_null=False,
        host_id=None,
        host_name=None,
        host_label=None,
        host_short_name=None,
        host_add_opts=None,
        host_del_opts=None,
        path=None,
        orig_path=None,
        timestamp=None,
        img_id=None,
    ):
        """Initialise a new Selection object.

        Initialise a new Selection object with the specified selection
        criteria.

        :param boot_id: The boot_id to match
        :param title: The title to match
        :param version: The version to match
        :param machine_id: The machine_id to match
        :param linux: The BootEntry kernel image to match
        :param initrd: The BootEntry initrd image to match
        :param efi: The BootEntry efi image to match
        :param root_device: The root_device to match
        :param lvm_root_lv: The lvm_root_lv to match
        :param btrfs_subvol_path: The btrfs_subvol_path to match
        :param btrfs_subvol_id: The btrfs_subvol_id to match
        :param os_id: The os_id to match
        :param os_name: The os_name to match
        :param os_short_name: The os_short_name to match
        :param os_version: The os_version to match
        :param os_version_id: The os_version_id to match
        :param os_options: The os_options to match
        :param os_uname_pattern: The os_uname_pattern to match
        :param os_kernel_pattern: The kernel_pattern to match
        :param os_initramfs_pattern: The initramfs_pattern to match
        :param allow_null: Allow selecting the null profile
        :param host_id: The host identifier to match
        :param host_name: The host name to match
        :param host_label: The host label to match
        :param host_short_name: The host short name to match
        :param host_add_opts: Host add options to match
        :param host_del_opts: Host del options to match
        :param path: An cache image path to match
        :param orig_path: A cache origin path to match
        :param timestamp: A cache entry timestamp to match
        :param img_id: A cache image identifier to match
        :returns: A new Selection instance
        :rtype: Selection
        """
        self.boot_id = boot_id
        self.title = title
        self.version = version
        self.machine_id = machine_id
        self.linux = linux
        self.initrd = initrd
        self.efi = efi
        self.root_device = root_device
        self.lvm_root_lv = lvm_root_lv
        self.btrfs_subvol_path = btrfs_subvol_path
        self.btrfs_subvol_id = btrfs_subvol_id
        self.os_id = os_id
        self.os_name = os_name
        self.os_short_name = os_short_name
        self.os_version = os_version
        self.os_version_id = os_version_id
        self.os_options = os_options
        self.os_uname_pattern = os_uname_pattern
        self.os_kernel_pattern = os_kernel_pattern
        self.os_initramfs_pattern = os_initramfs_pattern
        self.allow_null_profile = allow_null
        self.host_id = host_id
        self.host_name = host_name
        self.host_label = host_label
        self.host_short_name = host_short_name
        self.host_add_opts = host_add_opts
        self.host_del_opts = host_del_opts
        self.path = path
        self.orig_path = orig_path
        self.timestamp = timestamp
        self.img_id = img_id

    @classmethod
    def from_cmd_args(cls, args):
        """Initialise Selection from command line arguments.

        Construct a new ``Selection`` object from the command line
        arguments in ``cmd_args``. Each set selection attribute from
        ``cmd_args`` is copied into the Selection. The resulting
        object may be passed to either the ``BootEntry``,
        ``OsProfile``, or ``HostProfile`` search functions
        (``find_entries``, ``find_profiles``, and
        ``find_host_profiles``), as well as the ``boom.command``
        calls that accept a selection argument.

        :param args: The command line selection arguments.
        :returns: A new Selection instance
        :rtype: Selection
        """
        (subvol_path, subvol_id) = parse_btrfs_subvol(args.btrfs_subvolume)

        s = Selection(
            boot_id=args.boot_id,
            title=args.title,
            version=args.version,
            machine_id=args.machine_id,
            linux=args.linux,
            initrd=args.initrd,
            efi=args.efi,
            root_device=args.root_device,
            lvm_root_lv=args.root_lv,
            btrfs_subvol_path=subvol_path,
            btrfs_subvol_id=subvol_id,
            os_id=args.profile,
            os_name=args.name,
            os_short_name=args.short_name,
            os_version=args.os_version,
            os_version_id=args.os_version_id,
            os_options=args.os_options,
            os_uname_pattern=args.uname_pattern,
            host_id=args.host_id,
        )

        _log_debug("Initialised %s from arguments", repr(s))
        return s

    def __attr_has_value(self, attr):
        """Test whether an attribute is defined.

        Return ``True`` if the specified attribute name is currently
        defined, or ``False`` otherwise.

        :param attr: The name of the attribute to test
        :returns: ``True`` if ``attr`` is set or ``False`` otherwise
        :rtype: bool
        """
        return hasattr(self, attr) and getattr(self, attr) is not None

    def check_valid_selection(
        self, entry=False, params=False, profile=False, host=False, cache=False
    ):
        """Check a Selection for valid criteria.

        Check this ``Selection`` object to ensure it contains only
        criteria that are valid for the specified object type(s).

        Returns ``None`` if the object passes the check, or raise
        ``ValueError`` if invalid criteria exist.

        :param entry: ``Selection`` may include BootEntry data
        :param params: ``Selection`` may include BootParams data
        :param profile: ``Selection`` may include OsProfile data
        :param host: ``Selection`` may include Host data
        :param cache: ``Selection`` may include Cache data
        :returns: ``None`` on success
        :rtype: ``NoneType``
        :raises: ``ValueError`` if excluded criteria are present
        """
        valid_attrs = []
        invalid_attrs = []

        if entry:
            valid_attrs += self.entry_attrs
        if entry or params:
            valid_attrs += self.params_attrs
        if profile or host:
            valid_attrs += self.profile_attrs
        if host:
            valid_attrs += self.host_attrs
        if cache:
            valid_attrs += self.cache_attrs

        for attr in self.all_attrs:
            if self.__attr_has_value(attr) and attr not in valid_attrs:
                invalid_attrs.append(attr)

        if invalid_attrs:
            invalid = ", ".join(invalid_attrs)
            raise ValueError("Invalid criteria for selection type: %s" % invalid)

    def is_null(self):
        """Test this Selection object for null selection criteria.

        Return ``True`` if this ``Selection`` object matches all
        objects, or ``False`` otherwise.

        :returns: ``True`` if this Selection is null
        :rtype: bool
        """
        all_attrs = self.all_attrs
        attrs = [attr for attr in all_attrs if self.__attr_has_value(attr)]
        return not any(attrs)


#
# Generic routines for parsing name-value pairs.
#


def blank_or_comment(line):
    """Test whether line is empty of contains a comment.

    Test whether the ``line`` argument is either blank, or a
    whole-line comment.

    :param line: the line of text to be checked.
    :returns: ``True`` if the line is blank or a comment,
              and ``False`` otherwise.
    :rtype: bool
    """
    return not line.strip() or line.lstrip().startswith("#")


def parse_name_value(nvp, separator="=", allow_empty=False):
    """Parse a name value pair string.

    Parse a ``name='value'`` style string into its component parts,
    stripping quotes from the value if necessary, and return the
    result as a (name, value) tuple.

    :param nvp: A name value pair optionally with an in-line
                comment.
    :param separator: The separator character used in this name
                      value pair, or ``None`` to splir on white
                      space.
    :returns: A ``(name, value)`` tuple.
    :rtype: (string, string) tuple.
    """
    val_err = ValueError("Malformed name/value pair: %s" % nvp)
    try:
        # Only strip newlines: values may contain embedded
        # whitespace anywhere within the string.
        name, value = nvp.rstrip("\n").split(separator, 1)
    except ValueError:
        if not allow_empty or not nvp:
            raise val_err
        name = nvp.strip(separator)
        value = None

    # Value cannot start with '='
    if value and value.startswith("="):
        raise val_err

    name = name.strip()
    value = value.lstrip() if value else None

    if value and "#" in value:
        value, comment = value.split("#", 1)

    valid_name_chars = string.ascii_letters + string.digits + "_-,.'\""
    bad_chars = [c for c in name if c not in valid_name_chars]
    if any(bad_chars):
        raise ValueError("Invalid characters in name: %s (%s)" % (name, bad_chars))

    if value:
        if value.startswith('"') or value.startswith("'"):
            quotes = "\"'"
            value = value.rstrip(quotes)
            value = value.lstrip(quotes)

    return (name, value)


def find_minimum_sha_prefix(shas, min_prefix):
    """Find the minimum SHA prefix length guaranteeing uniqueness.

    Find the minimum unique prefix for the set of SHA IDs in the set
    ``shas``.

    :param shas: A set of SHA IDs
    :param min_prefix: Initial minimum prefix value
    :returns: The minimum unique prefix length for the set
    :rtype: int
    """
    shas = list(shas)
    shas.sort()
    for sha in shas:
        if shas.index(sha) == len(shas) - 1:
            continue

        def _next_sha(shas, sha):
            return shas[shas.index(sha) + 1]

        while sha[:min_prefix] == _next_sha(shas, sha)[:min_prefix]:
            min_prefix += 1
    return min_prefix


def min_id_width(min_prefix, objs, attr):
    """Calculate the minimum unique width for id values.

    Calculate the minimum width to ensure uniqueness when displaying
    id values.

    :param min_prefix: The minimum allowed unique prefix.
    :param objs: An interrable containing objects to check.
    :param attr: The attribute to compare.

    :returns: the minimum id width.
    :rtype: int
    """
    if not objs:
        return min_prefix

    ids = set()
    for obj in objs:
        ids.add(getattr(obj, attr))
    return find_minimum_sha_prefix(ids, min_prefix)


def load_profiles_for_class(profile_class, profile_type, profiles_path, profile_ext):
    """Load profiles from disk.

    Load the set of profiles found at the path ``profiles_path``
    into the list ``profiles``. The list should be cleared before
    calling this function if the prior contents are no longer
    required.

    The profile class to be instantiated is specified by the
    ``profile_class`` argument. An optional ``type`` may be
    specified to describe the profile type in error messages.
    If ``type`` is unset the class name is used instead.

    This function is intended for use by profile implementations
    that share common on-disk profile handling.

    :param profile_class: The profile class to instantiate.
    :param profile_type: A string description of the profile type.
    :param profiles_path: Path to the on-disk profile directory.
    :param profile_ext: Extension of profile files.

    :returns: None
    """
    profile_files = listdir(profiles_path)
    _log_debug("Loading %s profiles from %s", profile_type, profiles_path)
    for pf in profile_files:
        if not pf.endswith(".%s" % profile_ext):
            continue
        pf_path = path_join(profiles_path, pf)
        try:
            profile_class(profile_file=pf_path)
        except Exception as e:
            _log_warn(
                "Failed to load %s from '%s': %s", profile_class.__name__, pf_path, e
            )
            if get_debug_mask():
                raise e
            continue


__all__ = [
    # boom module constants
    "DEFAULT_BOOT_PATH",
    "DEFAULT_BOOM_PATH",
    "BOOT_CONFIG_MODE",
    "BOOM_CONFIG_FILE",
    # Profile format keys
    "FMT_VERSION",
    "FMT_LVM_ROOT_LV",
    "FMT_LVM_ROOT_OPTS",
    "FMT_BTRFS_SUBVOLUME",
    "FMT_BTRFS_SUBVOL_ID",
    "FMT_BTRFS_SUBVOL_PATH",
    "FMT_BTRFS_ROOT_OPTS",
    "FMT_STRATIS_ROOT_OPTS",
    "FMT_STRATIS_POOL_UUID",
    "FMT_ROOT_DEVICE",
    "FMT_ROOT_OPTS",
    "FMT_KERNEL",
    "FMT_INITRAMFS",
    "FMT_OS_NAME",
    "FMT_OS_SHORT_NAME",
    "FMT_OS_VERSION",
    "FMT_OS_VERSION_ID",
    "FORMAT_KEYS",
    # Root fs option templates
    "ROOT_OPTS_BTRFS_PATH",
    "ROOT_OPTS_BTRFS_ID",
    "ROOT_OPTS_STRATIS",
    # API Classes
    "BoomConfig",
    "Selection",
    # Path configuration
    "get_boot_path",
    "get_boom_path",
    "get_cache_path",
    "set_boot_path",
    "set_boom_path",
    "set_cache_path",
    "set_boom_config_path",
    "get_boom_config_path",
    # Persistent configuration
    "set_boom_config",
    "get_boom_config",
    # boom exception base class
    "BoomError",
    # Boom logger class (used by test suite)
    "BoomLogger",
    # Debug logging
    "get_debug_mask",
    "set_debug_mask",
    "BOOM_DEBUG_PROFILE",
    "BOOM_DEBUG_ENTRY",
    "BOOM_DEBUG_REPORT",
    "BOOM_DEBUG_COMMAND",
    "BOOM_DEBUG_CACHE",
    "BOOM_DEBUG_STRATIS",
    "BOOM_DEBUG_ALL",
    # Utility routines
    "blank_or_comment",
    "parse_name_value",
    "parse_btrfs_subvol",
    "find_minimum_sha_prefix",
    "min_id_width",
    "load_profiles_for_class",
]

# vim: set et ts=4 sw=4
