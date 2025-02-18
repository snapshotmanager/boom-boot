# Copyright Red Hat
#
# boom/osprofile.py - Boom OS profiles
#
# This file is part of the boom project.
#
# SPDX-License-Identifier: GPL-2.0-only
"""The ``boom.osprofile``  module defines the `OsProfile` class that
represents an operating system profile. An `OsProfile` defines the
identity of a profile and includes template values used to generate boot
loader entries.

Functions are provided to read and write operating system profiles from
an on-disk store, and to retrieve ``OsProfile`` instances using various
selection criteria.

The ``OsProfile`` class includes named properties for each profile
attribute ("profile key"). In addition, the class serves as a container
type, allowing attributes to be accessed via dictionary-style indexing.
This simplifies iteration over a profile's key / value pairs and allows
straightforward access to all members in scripts and the Python shell.

All profile key names are made available as named members of the module:
``BOOM_OS_*``, and the ``OS_PROFILE_KEYS`` list. Human-readable names for
all the profile keys are stored in the ``OS_KEY_NAMES`` dictionary: these
are suitable for display use and are used by default by the
``OsProfile`` string formatting routines.
"""
from __future__ import print_function

from hashlib import sha1
from tempfile import mkstemp
from os.path import basename, join as path_join, exists as path_exists
from os import fdopen, rename, chmod, unlink, fdatasync
import logging
import re

from boom import *

#: Boom profiles directory name.
BOOM_PROFILES = "profiles"

#: File name format for Boom profiles.
BOOM_OS_PROFILE_FORMAT = "%s-%s%s.profile"

#: The file mode with which to create Boom profiles.
BOOM_PROFILE_MODE = 0o644

# Constants for Boom profile keys

#: Constant for the Boom OS identifier profile key.
BOOM_OS_ID = "BOOM_OS_ID"
#: Constant for the Boom OS name profile key.
BOOM_OS_NAME = "BOOM_OS_NAME"
#: Constant for the Boom OS short name profile key.
BOOM_OS_SHORT_NAME = "BOOM_OS_SHORT_NAME"
#: Constant for the Boom OS version string profile key.
BOOM_OS_VERSION = "BOOM_OS_VERSION"
#: Constant for the Boom OS version ID string profile key.
BOOM_OS_VERSION_ID = "BOOM_OS_VERSION_ID"
#: Constant for the Boom OS uname pattern profile key.
BOOM_OS_UNAME_PATTERN = "BOOM_OS_UNAME_PATTERN"
#: Constant for the Boom OS kernel pattern profile key.
BOOM_OS_KERNEL_PATTERN = "BOOM_OS_KERNEL_PATTERN"
#: Constant for the Boom OS initramfs pattern profile key.
BOOM_OS_INITRAMFS_PATTERN = "BOOM_OS_INITRAMFS_PATTERN"
#: Constant for the Boom OS LVM2 root options key.
BOOM_OS_ROOT_OPTS_LVM2 = "BOOM_OS_ROOT_OPTS_LVM2"
#: Constant for the Boom OS BTRFS root options key.
BOOM_OS_ROOT_OPTS_BTRFS = "BOOM_OS_ROOT_OPTS_BTRFS"
#: Constant for the Boom OS command line options key.
BOOM_OS_OPTIONS = "BOOM_OS_OPTIONS"
#: Constant for the Boom OS title template key.
BOOM_OS_TITLE = "BOOM_OS_TITLE"
#: Constant for the Boom OS optional keys key.
BOOM_OS_OPTIONAL_KEYS = "BOOM_OS_OPTIONAL_KEYS"

#: Ordered list of possible profile keys, partitioned into mandatory
#: keys, root option keys, and optional keys (currently the Linux
#: kernel command line).
OS_PROFILE_KEYS = [
    # Keys 0-6 (ID to INITRAMFS_PATTERN) are mandatory.
    BOOM_OS_ID,
    BOOM_OS_NAME,
    BOOM_OS_SHORT_NAME,
    BOOM_OS_VERSION,
    BOOM_OS_VERSION_ID,
    BOOM_OS_KERNEL_PATTERN,
    BOOM_OS_INITRAMFS_PATTERN,
    # At least one of keys 7-8 (ROOT_OPTS) is required.
    BOOM_OS_ROOT_OPTS_LVM2,
    BOOM_OS_ROOT_OPTS_BTRFS,
    # The OPTIONS, TITLE and UNAME_PATTERN keys are optional.
    BOOM_OS_OPTIONS,
    BOOM_OS_TITLE,
    BOOM_OS_OPTIONAL_KEYS,
    BOOM_OS_UNAME_PATTERN,
]

#: A map of Boom profile keys to human readable key names suitable
#: for use in formatted output. These key names are used to format
#: a ``OsProfile`` object as a human readable string.
OS_KEY_NAMES = {
    BOOM_OS_ID: "OS ID",
    BOOM_OS_NAME: "Name",
    BOOM_OS_SHORT_NAME: "Short name",
    BOOM_OS_VERSION: "Version",
    BOOM_OS_VERSION_ID: "Version ID",
    BOOM_OS_UNAME_PATTERN: "UTS release pattern",
    BOOM_OS_KERNEL_PATTERN: "Kernel pattern",
    BOOM_OS_INITRAMFS_PATTERN: "Initramfs pattern",
    BOOM_OS_ROOT_OPTS_LVM2: "Root options (LVM2)",
    BOOM_OS_ROOT_OPTS_BTRFS: "Root options (BTRFS)",
    BOOM_OS_OPTIONS: "Options",
    BOOM_OS_TITLE: "Title",
    BOOM_OS_OPTIONAL_KEYS: "Optional keys",
}

#: Boom profile keys that must exist in a valid profile.
OS_REQUIRED_KEYS = OS_PROFILE_KEYS[0:7]

#: Boom profile keys for different forms of root device specification.
OS_ROOT_KEYS = OS_PROFILE_KEYS[8:9]

#: Keys with default values
_DEFAULT_KEYS = {
    BOOM_OS_UNAME_PATTERN: "",
    BOOM_OS_KERNEL_PATTERN: "/vmlinuz-%{version}",
    BOOM_OS_INITRAMFS_PATTERN: "/initramfs-%{version}.img",
    BOOM_OS_ROOT_OPTS_LVM2: "rd.lvm.lv=%{lvm_root_lv}",
    BOOM_OS_ROOT_OPTS_BTRFS: "rootflags=%{btrfs_subvolume}",
    BOOM_OS_OPTIONS: "root=%{root_device} ro %{root_opts}",
    BOOM_OS_TITLE: "%{os_name} %{os_version_id} (%{version})",
}

# Module logging configuration
_log = logging.getLogger(__name__)
_log.set_debug_mask(BOOM_DEBUG_PROFILE)

_log_debug = _log.debug
_log_debug_profile = _log.debug_masked
_log_info = _log.info
_log_warn = _log.warning
_log_error = _log.error

#: Global profile list
_profiles = []
_profiles_by_id = {}

#: Whether profiles have been read from disk
_profiles_loaded = False


def _profile_exists(os_id):
    """Test whether the specified ``os_id`` already exists.

    Used during ``OsProfile`` initialisation to test if the new
    ``os_id`` is already known (and to avoid passing through
    find_profiles(), which may trigger recursive profile loading).

    :param os_id: the OS identifier to check for

    :returns: ``True`` if the identifier is known or ``False``
              otherwise.
    :rtype: bool
    """
    global _profiles_by_id
    if not _profiles_by_id:
        return False
    if os_id in _profiles_by_id:
        return True
    return False


def boom_profiles_path():
    """Return the path to the boom profiles directory.

    :returns: The boom profiles path.
    :rtype: str
    """
    return path_join(get_boom_path(), BOOM_PROFILES)


def _is_null_profile(osp):
    """Test for the Null Profile.

    Test ``osp`` and return ``True`` if it is the Null Profile.
    The Null Profile has an empty identity and defines no profile
    keys: it is used in the case that no valid match is found for
    an entry loaded from disk (for e.g. an entry that has been
    hand-edited and matches no known version or options string,
    or an entry for which the original profile has been deleted).

    :param osp: The OsProfile to test
    :returns: ``True`` if ``osp`` is the Null Profile or ``False``
              otherwise
    :rtype: bool
    """
    global _profiles
    if osp.os_id == _profiles[0].os_id:
        return True
    return False


def profiles_loaded():
    """Test whether profiles have been loaded from disk.

    :rtype: bool
    :returns: ``True`` if profiles are loaded in memory or ``False``
              otherwise
    """
    return _profiles_loaded


def drop_profiles():
    """Drop all in-memory profiles.

    Clear the list of in-memory profiles and reset the OsProfile
    list to the default state.

    :returns: None
    """
    global _profiles, _profiles_by_id, _profiles_loaded
    nr_profiles = len(_profiles) - 1 if _profiles else 0

    _profiles = []
    _profiles_by_id = {}

    optional_keys = "id grub_users grub_arg grub_class"
    _null_profile = OsProfile(
        name="", short_name="", version="", version_id="", optional_keys=optional_keys
    )
    _profiles_by_id[_null_profile.os_id] = _null_profile
    if nr_profiles:
        _log_info("Dropped %d profiles", nr_profiles)
    _profiles_loaded = False


def load_profiles():
    """Load OsProfile data from disk.

    Load the set of profiles found at the path
    ``boom.osprofile.boom_profiles_path()`` into the global profile
    list.

    This function may be called to explicitly load, or reload the
    set of profiles on-disk. Profiles are also loaded implicitly
    if an API function or method that requires access to profiles
    is invoked (for example, ``boom.bootloader.load_entries()``.

    :returns: None
    """
    global _profiles_loaded
    drop_profiles()
    load_profiles_for_class(OsProfile, "Os", boom_profiles_path(), "profile")
    _log_debug("Loaded %d profiles", len(_profiles) - 1)
    _profiles_loaded = True


def write_profiles(force=False):
    """Write all OsProfile data to disk.

    Write the current list of profiles to the directory located at
    ``boom.osprofile.boom_profiles_path()``.

    :rtype: None
    """
    global _profiles
    _log_debug("Writing profiles to %s", boom_profiles_path())
    for osp in _profiles:
        if _is_null_profile(osp):
            continue
        try:
            osp.write_profile(force)
        except Exception as e:
            _log_warn("Failed to write OsProfile(os_id='%s'): %s", osp.disp_os_id, e)


def min_os_id_width():
    """Calculate the minimum unique width for os_id values.

    Calculate the minimum width to ensure uniqueness when displaying
    os_id values.

    :returns: the minimum os_id width.
    :rtype: int
    """
    return min_id_width(7, _profiles, "os_id")


def select_profile(s, osp):
    """Test the supplied profile against selection criteria.

    Test the supplied ``OsProfile`` against the selection criteria
    in ``s`` and return ``True`` if it passes, or ``False``
    otherwise.

    :param s: The selection criteria
    :param osp: The ``OsProfile`` to test
    :rtype: bool
    :returns: True if ``osp`` passes selection or ``False``
              otherwise.
    """
    if not s.allow_null_profile and _is_null_profile(osp):
        return False
    if s.os_id and not osp.os_id.startswith(s.os_id):
        return False
    if s.os_name and osp.os_name != s.os_name:
        return False
    if s.os_short_name and osp.os_short_name != s.os_short_name:
        return False
    if s.os_version and osp.os_version != s.os_version:
        return False
    if s.os_version_id and osp.os_version_id != s.os_version_id:
        return False
    if s.os_uname_pattern and osp.uname_pattern != s.os_uname_pattern:
        return False
    if s.os_kernel_pattern and osp.kernel_pattern != s.os_kernel_pattern:
        return False
    if s.os_initramfs_pattern and s.os_initramfs_pattern != osp.initramfs_pattern:
        return False
    if s.os_options and osp.options != s.os_options:
        return False
    return True


def find_profiles(selection=None, match_fn=select_profile):
    """Find profiles matching selection criteria.

    Return a list of ``OsProfile`` objects matching the specified
    criteria. Matching proceeds as the logical 'and' of all criteria.
    Criteria that are unset (``None``) are ignored.

    If the optional ``match_fn`` parameter is specified, the match
    criteria parameters are ignored and each ``OsProfile`` is tested
    in turn by calling ``match_fn``. If the matching function returns
    ``True`` the ``OsProfile`` will be included in the results.

    If no ``OsProfile`` matches the specified criteria the empty list
    is returned.

    OS profiles will be automatically loaded from disk if they are
    not already in memory.

    :param selection: A ``Selection`` object specifying the match
                      criteria for the operation.
    :param match_fn: An optional match function to test profiles.
    :returns: a list of ``OsProfile`` objects.
    :rtype: list
    """
    global _profiles

    # Use null search criteria if unspecified
    selection = selection if selection else Selection()

    selection.check_valid_selection(profile=True)

    if not profiles_loaded():
        load_profiles()

    matches = []

    _log_debug_profile("Finding profiles for %s", repr(selection))
    for osp in _profiles:
        if match_fn(selection, osp):
            matches.append(osp)
    _log_debug_profile("Found %d profiles", len(matches))
    matches.sort(key=lambda o: (o.os_name, o.os_version))

    return matches


def get_os_profile_by_id(os_id):
    """Find an OsProfile by its os_id.

    Return the OsProfile object corresponding to ``os_id``, or
    ``None`` if it is not found.

    :rtype: OsProfile
    :returns: An OsProfile matching os_id or None if no match was
              found
    """
    if not profiles_loaded():
        load_profiles()
    if os_id in _profiles_by_id:
        return _profiles_by_id[os_id]
    return None


def match_os_profile(entry):
    """Attempt to match a BootEntry to a corresponding OsProfile.

    Probe all loaded ``OsProfile`` objects with the supplied
    ``BootEntry`` in turn, until an ``OsProfile`` reports a match.
    Checking terminates on the first matching ``OsProfile``.

    :param entry: A ``BootEntry`` object with no attached
                  ``OsProfile``.
    :returns: The corresponding ``OsProfile`` for the supplied
              ``BootEntry`` or ``None`` if no match is found.
    :rtype: ``OsProfile``
    """
    global _profiles, _profiles_loaded

    if not _profiles_loaded:
        load_profiles()

    # Do not report a boot_id: it will change if an OsProfile is
    # matched to the entry.
    _log_debug(
        "Attempting to match profile for BootEntry(title='%s', "
        "version='%s') with unknown os_id",
        entry.title,
        entry.version,
    )

    # Attempt to match by uname pattern
    for osp in sorted(_profiles, key=lambda o: (o.os_name, o.os_version)):
        if _is_null_profile(osp):
            continue
        if osp.match_uname_version(entry.version):
            _log_debug(
                "Matched BootEntry(version='%s', boot_id='%s') "
                "to OsProfile(name='%s', os_id='%s')",
                entry.version,
                entry.disp_boot_id,
                osp.os_name,
                osp.disp_os_id,
            )
            return osp

    # No matching uname pattern: attempt to match options template
    for osp in _profiles:
        if _is_null_profile(osp):
            continue
        if osp.match_options(entry):
            _log_debug(
                "Matched BootEntry(version='%s', boot_id='%s') "
                "to OsProfile(name='%s', os_id='%s')",
                entry.version,
                entry.disp_boot_id,
                osp.os_name,
                osp.disp_os_id,
            )
            return osp

    _log_debug_profile("No matching profile found for boot_id=%s", entry.boot_id)

    # Assign the Null profile to this BootEntry: we cannot determine a
    # valid OsProfile to associate with it, so it cannot be modified or
    # displayed correctly by boom. Add it to the list of loaded entries,
    # but do not return it as a valid entry in entry selections.
    return _profiles[0]


def match_os_profile_by_version(version):
    """Attempt to match a version string to an OsProfile.

    Attempt to find a profile with a uname pattern that matches
    ``version``. The first OsProfile with a match is returned.

    :param version: A uname release version string to match.
    :rtype: OsProfile
    :returns: An OsProfile matching version or None if not match
              was found
    """
    global _profiles, _profiles_loaded

    if not _profiles_loaded:
        load_profiles()

    for osp in _profiles:
        if osp.match_uname_version(version):
            return osp
    return None


def key_from_key_name(key_name):
    key_format = "%%{%s}"
    return key_format % key_name


class BoomProfile(object):
    """Class ``BoomProfile`` is the abstract base class for Boom template
    profiles. The ``BoomProfile`` class cannot be instantiated by
    itself but serves as the base class for both ``OsProfile`` and
    ``HostProfile`` instances.
    """

    #: Profile data dictionary
    _profile_data = None
    #: Dirty flag
    _unwritten = False
    #: Comment descriptors read from on-disk store
    _comments = None

    #: Key set for this profile class
    _profile_keys = None
    #: Mandatory keys for this profile class
    _required_keys = None
    #: The identity key for this profile class
    _identity_key = None

    def __str__(self):
        """Format this profile as a human readable string.

        This method must be implemented by concrete profile classes.

        :returns: A human readable string representation of this
                  ``BoomProfile``.

        :rtype: string
        """
        raise NotImplementedError

    def __repr__(self):
        """Format this ``BoomProfile`` as a machine readable string.

        This method must be implemented by concrete profile classes.

        :returns: a string representation of this ``BoomProfile``.
        :rtype: ``string``
        """
        raise NotImplementedError

    def _from_data(self, profile_data, dirty=True):
        """
        This method must be implemented by concrete profile classes.
        """
        raise NotImplementedError

    def __len__(self):
        """Return the length (key count) of this profile.

        :returns: the profile length as an integer.
        :rtype: ``int``
        """
        return len(self._profile_data)

    def __getitem__(self, key):
        """Return an item from this profile.

        :returns: the item corresponding to the key requested.
        :rtype: the corresponding type of the requested key.
        :raises: TypeError if ``key`` is of an invalid type.
                 KeyError if ``key`` is valid but not present.
        """
        if not isinstance(key, str):
            raise TypeError("Profile key must be a string.")

        if key in self._profile_data:
            return self._profile_data[key]

        raise KeyError("Key %s not in profile." % key)

    def __setitem__(self, key, value):
        """Set the specified ``Profile`` key to the given value.

        :param key: the ``Profile`` key to be set.
        :param value: the value to set for the specified key.
        """
        # Name of the current profile class instance
        ptype = self.__class__.__name__

        # Map key names to a list of format keys which must not
        # appear in that key's value: e.g. %{kernel} in the kernel
        # pattern profile key.
        bad_key_map = {
            BOOM_OS_KERNEL_PATTERN: [FMT_KERNEL],
            BOOM_OS_INITRAMFS_PATTERN: [FMT_INITRAMFS],
            BOOM_OS_ROOT_OPTS_LVM2: [FMT_ROOT_OPTS],
            BOOM_OS_ROOT_OPTS_BTRFS: [FMT_ROOT_OPTS],
        }

        def _check_format_key_value(key, value, bad_keys):
            for bad_key in bad_keys:
                if bad_key in value:
                    bad_fmt = key_from_key_name(bad_key)
                    raise ValueError("%s.%s cannot contain %s" % (ptype, key, bad_fmt))

        if not isinstance(key, str):
            raise TypeError("%s key must be a string." % ptype)

        if key not in self._profile_keys:
            raise ValueError("Invalid %s key: %s" % (ptype, key))

        if key in bad_key_map:
            _check_format_key_value(key, value, bad_key_map[key])

        self._profile_data[key] = value

    def keys(self):
        """Return the list of keys for this ``BoomProfile``.

        :rtype: list
        :returns: A list of ``BoomProfile`` key names
        """
        return self._profile_data.keys()

    def values(self):
        """Return the list of key values for this ``BoomProfile``.

        :rtype: list
        :returns: A list of ``BoomProfile`` key values
        """
        return self._profile_data.values()

    def items(self):
        """Return the items list for this ``BoomProfile``.

        Return a list of ``(key, value)`` tuples representing the
        key items in this ``BoomProfile``.

        :rtype: list
        :returns: A list of ``BoomProfile`` key item tuples
        """
        return self._profile_data.items()

    def _dirty(self):
        """Mark this ``BoomProfile`` as needing to be written to disk.

        A newly created ``BoomProfile`` object is always dirty and
        a call to its ``write_profile()`` method will always write
        a new profile file. Writes may be avoided for profiles
        that are not marked as dirty.

        A clean ``BoomProfile`` is marked as dirty if a new value
        is written to any of its writable properties.

        :returns None:
        """
        if self._identity_key in self._profile_data:
            # The profile may not have been modified in a way that
            # causes the identifier to change: clear it anyway, and
            # it will be re-set to the previous value on next access.
            self._profile_data.pop(self._identity_key)
        self._unwritten = True

    def _generate_id(self):
        """Generate a new profile identifier.

        Generate a new sha1 profile identifier for this profile.

        Subclasses of ``BoomProfile`` must override this method to
        generate an appropriate hash value, using the corresponding
        identity keys for the profile type.

        :returns: None
        :raises: NotImplementedError
        """
        raise NotImplementedError

    def _append_profile(self):
        """Append a ``BoomProfile`` to the appropriate global profile list

        This method must be overridden by classes that extend
        ``BoomProfile``.

        :returns: None
        :raises: NotImplementedError
        """
        raise NotImplementedError

    def _from_file(self, profile_file):
        """Initialise a new profile from data stored in a file.

        Initialise a new profile object using the profile data
        in profile_file.

        This method should not be called directly: to build a new
        ``Boomprofile`` object from in-memory data, use the class
        initialiser with the ``profile_file`` argument.

        :returns: None
        """
        profile_data = {}
        comments = {}
        comment = ""
        ptype = self.__class__.__name__

        _log_debug("Loading %s from '%s'", ptype, basename(profile_file))
        with open(profile_file, "r") as pf:
            for line in pf:
                if blank_or_comment(line):
                    comment += line if line else ""
                else:
                    name, value = parse_name_value(line)
                    profile_data[name] = value
                    if comment:
                        comments[name] = comment
                        comment = ""
        self._comments = comments

        try:
            # Call subclass _from_data() hook for initialisation
            self._from_data(profile_data, dirty=False)
        except ValueError as e:
            raise ValueError(str(e) + "in %s" % profile_file)

    def __init__(self, profile_keys, required_keys, identity_key):
        """Initialise a new ``BoomProfile`` object.

        This method should be called by all subclasses of
        ``BoomProfile`` in order to initialise the base class state.

        Subclasses must provide the set of allowed keys for this
        profile type, a list of keys that are mandatory for profile
        creation, and the name of the identity key that will return
        this profile's unique identifier.

        :param profile_keys: The set of keys used by this profile.
        :param required_keys: Mandatory keys for this profile.
        :param identity_key: The key containing the profile id.
        :returns: A new ``BoomProfile`` object.
        :rtype: class ``BoomProfile``
        """
        self._profile_keys = profile_keys
        self._required_keys = required_keys
        self._identity_key = identity_key

    def match_uname_version(self, version):
        """Test ``BoomProfile`` for version string match.

        Test the supplied version string to determine whether it
        matches the uname_pattern of this ``BoomProfile``.

        :param version: A uname release version string to match.
        :returns: ``True`` if this version matches this profile, or
                  ``False`` otherwise.
        :rtype: bool
        """
        _log_debug_profile(
            "Matching uname pattern '%s' to '%s'", self.uname_pattern, version
        )
        if self.uname_pattern and version:
            if re.search(self.uname_pattern, version):
                return True
        return False

    def match_options(self, entry):
        """Test ``BoomProfile`` for options template match.

        Test the supplied ``BootEntry`` to determine whether it
        matches the options template defined by this
        ``BoomProfile``.

        Used as a match of last resort when no uname pattern match
        exists.

        :param entry: A ``BootEntry`` to match against this profile.
        :returns: ``True`` if this entry matches this profile, or
                  ``False`` otherwise.
        :rtype: bool
        """
        # Attempt to match a distribution-formatted options line

        if not self.options or not entry.options:
            return False

        opts_regex_words = self.make_format_regexes(self.options)
        _log_debug_profile(
            "Matching options regex list with %d entries", len(opts_regex_words)
        )

        format_opts = []
        fixed_opts = []

        for rgx_word in opts_regex_words:
            for word in entry.options.split():
                (name, exp) = rgx_word
                match = re.match(exp, word)
                if not match:
                    continue
                value = match.group(0)
                if name:
                    fixed_opts.append(value)
                else:
                    format_opts.append(value)

        fixed = [o[1] for o in opts_regex_words if not o[0]]
        have_fixed = [True if f in fixed_opts else False for f in fixed]

        form = [o[1] for o in opts_regex_words if o[0]]
        have_form = [True if f in format_opts else False for f in form]

        return all(have_fixed) and any(have_form)

    def make_format_regexes(self, fmt):
        """Generate regexes matching format string

        Generate a list of ``(key, expr)`` tuples containing key and
        regular expression pairs capturing the format key values
        contained in the format string. Any non-format key words
        contained in the string are returned as a ``('', expr)``
        tuple containing no capture groups.

        The resulting list may be matched against the words of a
        ``BootEntry`` object's value strings in order to extract
        the parameters used to create them.

        :param fmt: The format string to build a regex list from.
        :returns: A list of key and word regex tuples.
        :rtype: list of (str, str)
        """
        key_format = "%%{%s}"
        regex_all = r"\S+"
        regex_num = r"\d+"
        regex_words = []

        if not fmt:
            return regex_words

        _log_debug_profile("Making format regex list for '%s'", fmt)

        # Keys captured by single regex
        key_regex = {
            FMT_VERSION: regex_all,
            FMT_LVM_ROOT_LV: regex_all,
            FMT_BTRFS_SUBVOL_ID: regex_num,
            FMT_BTRFS_SUBVOL_PATH: regex_all,
            FMT_STRATIS_POOL_UUID: regex_all,
            FMT_ROOT_DEVICE: regex_all,
            FMT_KERNEL: regex_all,
            FMT_INITRAMFS: regex_all,
        }

        # Keys requiring expansion
        key_exp = {
            FMT_LVM_ROOT_OPTS: [self.root_opts_lvm2],
            FMT_BTRFS_ROOT_OPTS: [self.root_opts_btrfs],
            FMT_BTRFS_SUBVOLUME: [ROOT_OPTS_BTRFS_PATH, ROOT_OPTS_BTRFS_ID],
            FMT_STRATIS_ROOT_OPTS: ROOT_OPTS_STRATIS,
            FMT_ROOT_OPTS: [
                self.root_opts_lvm2,
                self.root_opts_btrfs,
                ROOT_OPTS_STRATIS,
            ],
        }

        def _substitute_keys(word):
            """Return a list of regular expressions matching the format keys
            found in ``word``, expanding and substituting format keys
            as necessary until all keys have been replaced with a
            regular expression.

            For keys that form part of a word that represents the
            canonical source of a BootParams attribute value (for e.g.
            'root=%{root_device}') the regular expression returned will
            include a capture group for the attribute value.
            """
            subst = []
            did_subst = False
            capture = (
                "root=%{root_device}",
                "rd.lvm.lv=%{lvm_root_lv}",
                ROOT_OPTS_BTRFS_ID,
                ROOT_OPTS_BTRFS_PATH,
                ROOT_OPTS_STRATIS,
            )

            replace = ("rootflags=%{btrfs_subvolume}",)

            for key in FORMAT_KEYS:
                k = key_format % key
                if k in word and key in key_regex:
                    regex_fmt = "%s"
                    keyname = ""
                    if word in capture:
                        regex_fmt = "(%s)"
                        keyname = key
                    word = word.replace(k, regex_fmt % key_regex[key])
                    subst.append((keyname, word))
                    did_subst = True
                elif k in word and key in key_exp:
                    # Recursive expansion and substitution
                    for e in key_exp[key]:
                        if word in replace:
                            exp = e
                        else:
                            exp = word.replace(key_format % key, e)
                        subst += _substitute_keys(exp)
                        did_subst = True

            if not did_subst:
                # Non-formatted word
                subst.append(("", word))

            return subst

        for word in fmt.split():
            regex_words += _substitute_keys(word)

        return regex_words

    # We use properties for the BoomProfile attributes: this is to
    # allow the values to be stored in a dictionary. Although
    # properties are quite verbose this reduces the code volume
    # and complexity needed to marshal and unmarshal the various
    # file formats used, as well as conversion to and from string
    # representations of different types of BoomProfile objects.

    # The set of keys defined as properties for the BoomProfile
    # class is the set of keys exposed by every profile type.

    @property
    def os_name(self):
        """The ``os_name`` of this profile.

        :getter: returns the ``os_name`` as a string.
        :type: string
        """
        return self._profile_data[BOOM_OS_NAME]

    @property
    def os_short_name(self):
        """The ``os_short_name`` of this profile.

        :getter: returns the ``os_short_name`` as a string.
        :type: string
        """
        return self._profile_data[BOOM_OS_SHORT_NAME]

    @property
    def os_version(self):
        """The ``os_version`` of this profile.

        :getter: returns the ``os_version`` as a string.
        :type: string
        """
        return self._profile_data[BOOM_OS_VERSION]

    @property
    def os_version_id(self):
        """The ``version_id`` of this profile.

        :getter: returns the ``os_version_id`` as a string.
        :type: string
        """
        return self._profile_data[BOOM_OS_VERSION_ID]

    # Configuration keys specify values that may be modified and
    # have a corresponding <key>.setter.

    @property
    def uname_pattern(self):
        """The current ``uname_pattern`` setting of this profile.

        :getter: returns the ``uname_pattern`` as a string.
        :setter: stores a new ``uname_pattern`` setting.
        :type: string
        """
        return self._profile_data[BOOM_OS_UNAME_PATTERN]

    @uname_pattern.setter
    def uname_pattern(self, value):
        self._profile_data[BOOM_OS_UNAME_PATTERN] = value
        self._dirty()

    @property
    def kernel_pattern(self):
        """The current ``kernel_pattern`` setting of this profile.

        :getter: returns the ``kernel_pattern`` as a string.
        :setter: stores a new ``kernel_pattern`` setting.
        :type: string
        """
        return self._profile_data[BOOM_OS_KERNEL_PATTERN]

    @kernel_pattern.setter
    def kernel_pattern(self, value):
        kernel_key = key_from_key_name(FMT_KERNEL)

        if kernel_key in value:
            ptype = self.__class__.__name__
            raise ValueError("%s.kernel cannot contain %s" % (ptype, kernel_key))

        self._profile_data[BOOM_OS_KERNEL_PATTERN] = value
        self._dirty()

    @property
    def initramfs_pattern(self):
        """The current ``initramfs_pattern`` setting of this profile.

        :getter: returns the ``initramfs_pattern`` as a string.
        :setter: store a new ``initramfs_pattern`` setting.
        :type: string
        """
        return self._profile_data[BOOM_OS_INITRAMFS_PATTERN]

    @initramfs_pattern.setter
    def initramfs_pattern(self, value):
        initramfs_key = key_from_key_name(FMT_INITRAMFS)
        if initramfs_key in value:
            ptype = self.__class__.__name__
            raise ValueError("%s.initramfs cannot contain %s" % (ptype, initramfs_key))
        self._profile_data[BOOM_OS_INITRAMFS_PATTERN] = value
        self._dirty()

    @property
    def root_opts_lvm2(self):
        """The current LVM2 root options setting of this profile.

        :getter: returns the ``root_opts_lvm2`` value as a string.
        :setter: store a new ``root_opts_lvm2`` value.
        :type: string
        """
        if BOOM_OS_ROOT_OPTS_LVM2 not in self._profile_data:
            return None
        return self._profile_data[BOOM_OS_ROOT_OPTS_LVM2]

    @root_opts_lvm2.setter
    def root_opts_lvm2(self, value):
        root_opts_key = key_from_key_name(FMT_ROOT_OPTS)
        if root_opts_key in value:
            ptype = self.__class__.__name__
            raise ValueError(
                "%s.root_opts_lvm2 cannot contain %s" % (ptype, root_opts_key)
            )
        self._profile_data[BOOM_OS_ROOT_OPTS_LVM2] = value
        self._dirty()

    @property
    def root_opts_btrfs(self):
        """The current BTRFS root options setting of this profile.

        :getter: returns the ``root_opts_btrfs`` value as a string.
        :setter: store a new ``root_opts_btrfs`` value.
        :type: string
        """
        if BOOM_OS_ROOT_OPTS_BTRFS not in self._profile_data:
            return None
        return self._profile_data[BOOM_OS_ROOT_OPTS_BTRFS]

    @root_opts_btrfs.setter
    def root_opts_btrfs(self, value):
        root_opts_key = key_from_key_name(FMT_ROOT_OPTS)
        if root_opts_key in value:
            ptype = self.__class__.__name__
            raise ValueError(
                "%s.root_opts_btrfs cannot contain %s" % (ptype, root_opts_key)
            )
        self._profile_data[BOOM_OS_ROOT_OPTS_BTRFS] = value
        self._dirty()

    @property
    def options(self):
        """The current kernel command line options setting for this
        profile.

        :getter: returns the ``options`` value as a string.
        :setter: store a new ``options`` value.
        :type: string
        """
        if BOOM_OS_OPTIONS not in self._profile_data:
            return None
        return self._profile_data[BOOM_OS_OPTIONS]

    @options.setter
    def options(self, value):
        if "root=" not in value:
            raise ValueError("OsProfile.options must include root= " "device option")
        self._profile_data[BOOM_OS_OPTIONS] = value
        self._dirty()

    @property
    def title(self):
        """The current title template for this profile.

        :getter: returns the ``title`` value as a string.
        :setter: store a new ``title`` value.
        :type: string
        """
        if BOOM_OS_TITLE not in self._profile_data:
            return None
        return self._profile_data[BOOM_OS_TITLE]

    @title.setter
    def title(self, value):
        self._profile_data[BOOM_OS_TITLE] = value
        self._dirty()

    def _check_optional_key(self, optional_key):
        """Check that they optional key ``key`` is a valid, known BLS
        optional key and raise ``ValueError`` if it is not.
        """
        _valid_optional_keys = ["grub_users", "grub_arg", "grub_class", "id"]
        if optional_key not in _valid_optional_keys:
            raise ValueError("Unknown optional key: '%s'" % optional_key)

    @property
    def optional_keys(self):
        """The set of optional BLS keys allowed by this profile.

        :getter: returns a string containing optional BLS key names.
        :setter: store a new set of optional BLS keys.
        :type: string
        """
        if BOOM_OS_OPTIONAL_KEYS not in self._profile_data:
            return ""
        return self._profile_data[BOOM_OS_OPTIONAL_KEYS]

    @optional_keys.setter
    def optional_keys(self, optional_keys):
        for opt_key in optional_keys.split():
            self._check_optional_key(opt_key)
        self._profile_data[BOOM_OS_OPTIONAL_KEYS] = optional_keys
        self._dirty()

    def add_optional_key(self, key):
        """Add the BLS key ``key`` to the allowed set of optional keys
        for this profile.
        """
        self._check_optional_key(key)
        self.optional_keys = self.optional_keys + " " + key

    def del_optional_key(self, key):
        """Remove the BLS key ``key`` from the allowed set of optional
        keys for this profile.
        """
        self._check_optional_key(key)
        spacer = " "
        key_list = [k for k in self.optional_keys.split() if k != key]
        self.optional_keys = spacer.join(key_list)

    def _profile_path(self):
        """Return the path to this profile's on-disk data.

        Return the full path to this Profile in the appropriate
        Boom profile directory. Subclasses of ``BoomProfile`` must
        override this method to return the correct path for the
        specific profile type.

        :rtype: str
        :returns: The absolute path for this ``BoomProfile`` file
        :raises: NotImplementedError
        """
        raise NotImplementedError

    def _write_profile(self, profile_id, profile_dir, mode, force=False):
        """Write helper for profile classes.

        Write out this profile's data to a file in Boom format to
        the paths specified by the current configuration.

        The pathname to write is obtained from self._profile_path().

        If the value of ``force`` is ``False`` and the profile
        is not currently marked as dirty (either new, or modified
        since the last load operation) the write will be skipped.

        :param profile_id: The os_id or host_id of this profile.
        :param profile_dir: The directory containing this type.
        :param mode: The mode with which files are created.
        :param force: Force this profile to be written to disk even
                      if the entry is unmodified.

        :raises: ``OsError`` if the temporary entry file cannot be
                 renamed, or if setting file permissions on the
                 new entry file fails.
        """
        ptype = self.__class__.__name__
        if not force and not self._unwritten:
            return

        profile_path = self._profile_path()

        _log_debug(
            "Writing %s(id='%s') to '%s'", ptype, profile_id, basename(profile_path)
        )

        # List of key names for this profile type
        profile_keys = self._profile_keys

        (tmp_fd, tmp_path) = mkstemp(prefix="boom", dir=profile_dir)
        with fdopen(tmp_fd, "w") as f:
            for key in [k for k in profile_keys if k in self._profile_data]:
                if self._comments and key in self._comments:
                    f.write(self._comments[key].rstrip() + "\n")
                f.write('%s="%s"\n' % (key, self._profile_data[key]))
                f.flush()
                fdatasync(f.fileno())
        try:
            rename(tmp_path, profile_path)
            chmod(profile_path, mode)
        except Exception as e:
            _log_error("Error writing profile file '%s': %s", profile_path, e)
            try:
                unlink(tmp_path)
            except Exception:
                _log_error("Error unlinking temporary path %s", tmp_path)
            raise e

        _log_debug("Wrote %s (id=%s)'", ptype, profile_id)

    def write_profile(self, force=False):
        """Write out profile data to disk.

        Write out this ``BoomProfile``'s data to a file in Boom
        format to the paths specified by the current configuration.

        This method must be overridden by `BoomProfile` subclasses.

        :raises: ``OsError`` if the temporary entry file cannot be
                 renamed, or if setting file permissions on the
                 new entry file fails. ``NotImplementedError`` if
                 the method is called on the ``BoomProfile`` base
                 class.
        """
        raise NotImplementedError

    def _delete_profile(self, profile_id):
        """Deletion helper for profile classes.

        Remove the on-disk profile corresponding to this
        ``BoomProfile`` object. This will permanently erase the
        current file (although the current data may be re-written at
        any time by calling ``write_profile()`` before the object is
        disposed of).

        The method will call the profile class's ``_profile_path()``
        method in order to determine the location of the on-disk
        profile store.

        :rtype: ``NoneType``
        :raises: ``OsError`` if an error occurs removing the file or
                 ``ValueError`` if the profile does not exist.
        """
        ptype = self.__class__.__name__
        profile_path = self._profile_path()

        _log_debug(
            "Deleting %s(id='%s') from '%s'", ptype, profile_id, basename(profile_path)
        )

        if not path_exists(profile_path):
            return
        try:
            unlink(profile_path)
            _log_debug("Deleted %s(id='%s')", ptype, profile_id)
        except Exception as e:
            _log_error("Error removing %s file '%s': %s", ptype, profile_path, e)

    def delete_profile(self):
        """Delete on-disk data for this profile.

        Remove the on-disk profile corresponding to this
        ``BoomProfile`` object. This will permanently erase the
        current file (although the current data may be re-written at
        any time by calling ``write_profile()`` before the object is
        disposed of).

        Subclasses of ``BoomProfile`` that implement an on-disk store
        must override this method to perform any unlinking of the
        profile from in-memory data structures, and to call the
        generic ``_delete_profile()`` method to remove the profile
        file.

        :rtype: ``NoneType``
        :raises: ``OsError`` if an error occurs removing the file or
                 ``ValueError`` if the profile does not exist.
        """
        raise NotImplementedError


class OsProfile(BoomProfile):
    """Class OsProfile implements Boom operating system profiles.
    Objects of type OsProfile define the paths, kernel command line
    options, root device flags and file name patterns needed to boot
    an instance of that operating system.
    """

    _profile_data = None
    _unwritten = False
    _comments = None

    _profile_keys = OS_PROFILE_KEYS
    _required_keys = OS_REQUIRED_KEYS
    _identity_key = BOOM_OS_ID

    def __str__(self):
        """Format this OsProfile as a human readable string.

        Profile attributes are printed as "Name: value, " pairs,
        with like attributes grouped together onto lines.

        :returns: A human readable string representation of this OsProfile.

        :rtype: string
        """
        breaks = [
            BOOM_OS_ID,
            BOOM_OS_SHORT_NAME,
            BOOM_OS_VERSION_ID,
            BOOM_OS_UNAME_PATTERN,
            BOOM_OS_INITRAMFS_PATTERN,
            BOOM_OS_ROOT_OPTS_LVM2,
            BOOM_OS_ROOT_OPTS_BTRFS,
            BOOM_OS_OPTIONS,
            BOOM_OS_TITLE,
        ]

        fields = [f for f in OS_PROFILE_KEYS if f in self._profile_data]
        osp_str = ""
        tail = ""
        for f in fields:
            osp_str += '%s: "%s"' % (OS_KEY_NAMES[f], self._profile_data[f])
            tail = ",\n" if f in breaks else ", "
            osp_str += tail
        osp_str = osp_str.rstrip(tail)
        return osp_str

    def __repr__(self):
        """Format this OsProfile as a machine readable string.

        Return a machine-readable representation of this ``OsProfile``
        object. The string is formatted as a call to the ``OsProfile``
        constructor, with values passed as a dictionary to the
        ``profile_data`` keyword argument.

        :returns: a string representation of this ``OsProfile``.
        :rtype: string
        """
        osp_str = "OsProfile(profile_data={"
        fields = [f for f in OS_PROFILE_KEYS if f in self._profile_data]
        for f in fields:
            osp_str += '%s:"%s", ' % (f, self._profile_data[f])
        osp_str = osp_str.rstrip(", ")
        return osp_str + "})"

    def _generate_id(self):
        """Generate a new OS identifier.

        Generate a new sha1 profile identifier for this profile,
        using the os_short_name, version, and version_id values and
        store it in _profile_data.

        :returns: None
        """
        hashdata = self.os_short_name + self.os_version + self.os_version_id

        digest = sha1(hashdata.encode("utf-8"), usedforsecurity=False).hexdigest()
        self._profile_data[BOOM_OS_ID] = digest

    def _append_profile(self):
        """Append an OsProfile to the global profile list

        Check whether this ``OsProfile`` already exists, and add it
        to the global profile list if not. If the profile is already
        present ``ValueError`` is raised.

        :raises: ValueError
        """
        if _profile_exists(self.os_id):
            raise ValueError("Profile already exists (os_id=%s)" % self.disp_os_id)

        _profiles.append(self)
        _profiles_by_id[self.os_id] = self

    def _from_data(self, profile_data, dirty=True):
        """Initialise an OsProfile from in-memory data.

        Initialise a new OsProfile object using the profile data
        in the `profile_data` dictionary.

        This method should not be called directly: to build a new
        ``Osprofile`` object from in-memory data, use the class
        initialiser with the ``profile_data`` argument.

        :returns: None
        """
        err_str = "Invalid profile data (missing %s)"

        _log_debug_profile("Initialising OsProfile from profile_data=%s", profile_data)

        # Set profile defaults
        for key in _DEFAULT_KEYS:
            if key not in profile_data:
                profile_data[key] = _DEFAULT_KEYS[key]

        for key in self._required_keys:
            if key == BOOM_OS_ID:
                continue
            if key not in profile_data:
                raise ValueError(err_str % key)

        if BOOM_OS_OPTIONS not in profile_data:
            raise ValueError(err_str % BOOM_OS_OPTIONS)
        elif "root=" not in profile_data[BOOM_OS_OPTIONS]:
            raise ValueError("OsProfile.options must include root= " "device option")

        root_opts = [key for key in OS_ROOT_KEYS if key in profile_data]
        if not any(root_opts):
            root_opts_err = err_str % "ROOT_OPTS"
            raise ValueError(root_opts_err)

        if BOOM_OS_OPTIONAL_KEYS in profile_data:
            for opt_key in profile_data[BOOM_OS_OPTIONAL_KEYS].split():
                self._check_optional_key(opt_key)

        # Empty OPTIONS is permitted: set the corresponding
        # value in the _profile_data dictionary to the empty string.
        if BOOM_OS_OPTIONS not in profile_data:
            profile_data[BOOM_OS_OPTIONS] = ""
        self._profile_data = dict(profile_data)

        if BOOM_OS_ID not in self._profile_data:
            self._generate_id()

        if dirty:
            self._dirty()

        self._append_profile()

    def _from_file(self, profile_file):
        """Initialise a new profile from data stored in a file.

        Initialise a new profil object using the profile data
        in profile_file.

        This method should not be called directly: to build a new
        ``Osprofile`` object from in-memory data, use the class
        initialiser with the ``profile_file`` argument.

        :returns: None
        """
        profile_data = {}
        comments = {}
        comment = ""
        ptype = self.__class__.__name__

        _log_debug("Loading %s from '%s'", ptype, basename(profile_file))
        with open(profile_file, "r") as pf:
            for line in pf:
                if blank_or_comment(line):
                    comment += line if line else ""
                else:
                    name, value = parse_name_value(line)
                    profile_data[name] = value
                    if comment:
                        comments[name] = comment
                        comment = ""
        self._comments = comments

        self._from_data(profile_data, dirty=False)

    def __init__(
        self,
        name=None,
        short_name=None,
        version=None,
        version_id=None,
        profile_file=None,
        profile_data=None,
        uname_pattern=None,
        kernel_pattern=None,
        initramfs_pattern=None,
        root_opts_lvm2=None,
        root_opts_btrfs=None,
        options=None,
        optional_keys=None,
    ):
        """Initialise a new ``OsProfile`` object.

        If neither ``profile_file`` nor ``profile_data`` is given,
        all of ``name``, ``short_name``, ``version``, and
        ``version_id`` must be given.

        These values form the profile identity and are used to
        generate the profile unique identifier.

        :param name: The name of the operating system.
        :param short_name: A short name for the operating system,
                           suitable for use in file names.
        :param version: A string describing the version of the
                        operating system.
        :param version_id: A short alphanumeric string representing
                           the operating system version and suitable
                           for use in generating file names.
        :param profile_data: An optional dictionary mapping from
                             ``BOOM_OS_*`` keys to profile values.
        :param profile_file: An optional path to a file from which
                             profile data should be loaded. The file
                             should be in Boom profile format, with
                             ``BOOM_OS_*`` key=value pairs.
        :param uname_pattern: Optional uname pattern.
        :param kernel_pattern: Optional kernel pattern.
        :param initramfs_pattern: Optional initramfs pattern.
        :param root_opts_lvm2: Optional LVM2 root options template.
        :param root_opts_btrfs: Optional BTRFS options template.
        :param options: Optional options template.

        :returns: A new ``OsProfile`` object.
        :rtype: class OsProfile
        """
        global _profiles
        self._profile_data = {}

        # Initialise BoomProfile base class
        super(OsProfile, self).__init__(OS_PROFILE_KEYS, OS_REQUIRED_KEYS, BOOM_OS_ID)

        if profile_data and profile_file:
            raise ValueError(
                "Only one of 'profile_data' or 'profile_file' " "may be specified."
            )

        if profile_data:
            self._from_data(profile_data)
            return
        if profile_file:
            self._from_file(profile_file)
            return

        self._dirty()

        self._profile_data[BOOM_OS_NAME] = name
        self._profile_data[BOOM_OS_SHORT_NAME] = short_name
        self._profile_data[BOOM_OS_VERSION] = version
        self._profile_data[BOOM_OS_VERSION_ID] = version_id

        # Optional arguments: unset values will be replaced by defaults.
        if uname_pattern:
            self._profile_data[BOOM_OS_UNAME_PATTERN] = uname_pattern
        self._profile_data[BOOM_OS_KERNEL_PATTERN] = kernel_pattern
        self._profile_data[BOOM_OS_INITRAMFS_PATTERN] = initramfs_pattern
        self._profile_data[BOOM_OS_ROOT_OPTS_LVM2] = root_opts_lvm2
        self._profile_data[BOOM_OS_ROOT_OPTS_BTRFS] = root_opts_btrfs
        self._profile_data[BOOM_OS_OPTIONS] = options

        if optional_keys:
            self.optional_keys = optional_keys

        required_args = [name, short_name, version, version_id]
        if all([not val for val in required_args]):
            # NULL profile
            for key in OS_PROFILE_KEYS:
                # Allow optional_keys for the NULL profile
                if key == BOOM_OS_OPTIONAL_KEYS:
                    continue
                self._profile_data[key] = ""
        elif any([not val for val in required_args]):
            raise ValueError(
                "Invalid profile arguments: name, "
                "short_name, version, and version_id are"
                "mandatory."
            )

        def default_if_unset(key):
            if key not in self._profile_data:
                return _DEFAULT_KEYS[key]
            return self._profile_data[key] or _DEFAULT_KEYS[key]

        # Apply global defaults for unset keys
        for key in _DEFAULT_KEYS:
            self._profile_data[key] = default_if_unset(key)

        self._generate_id()
        self._append_profile()

    # We use properties for the OsProfile attributes: this is to
    # allow the values to be stored in a dictionary. Although
    # properties are quite verbose this reduces the code volume
    # and complexity needed to marshal and unmarshal the various
    # file formats used, as well as conversion to and from string
    # representations of OsProfile objects.

    # Keys obtained from os-release data form the profile's identity:
    # the corresponding attributes are read-only.

    # OSProfile properties:
    #
    #   disp_os_id
    #   os_id

    # OSProfile properties inherited from BoomProfile
    #   os_name
    #   os_short_name
    #   os_version
    #   os_version_id
    #   uname_pattern
    #   kernel_pattern
    #   initramfs_pattern
    #   root_opts_lvm2
    #   root_opts_btrfs
    #   options

    @property
    def disp_os_id(self):
        """The display os_id of this profile.

        Return the shortest prefix of this OsProfile's os_id that
        is unique within the current set of loaded profiles.

        :getter: return this OsProfile's os_id.
        :type: str
        """
        return self.os_id[: min_os_id_width()]

    @property
    def os_id(self):
        """The ``os_id`` of this profile.

        :getter: returns the ``os_id`` as a string.
        :type: string
        """
        if BOOM_OS_ID not in self._profile_data:
            self._generate_id()
        return self._profile_data[BOOM_OS_ID]

    #
    # Class methods for building OsProfile instances from os-release
    #

    @classmethod
    def from_os_release(cls, os_release, profile_data=None):
        """Build an OsProfile from os-release file data.

        Construct a new OsProfile object using data obtained from
        a file in os-release(5) format.

        :param os_release: String data in os-release(5) format
        :param profile_data: an optional dictionary of profile data
                             overriding default values.
        :returns: A new OsProfile for the specified os-release data
        :rtype: OsProfile
        """
        release_data = {}
        profile_data = profile_data or {}
        for line in os_release:
            if blank_or_comment(line):
                continue
            name, value = parse_name_value(line)
            release_data[name] = value

        release_keys = {
            "NAME": BOOM_OS_NAME,
            "ID": BOOM_OS_SHORT_NAME,
            "VERSION": BOOM_OS_VERSION,
            "VERSION_ID": BOOM_OS_VERSION_ID,
        }

        for key in release_keys.keys():
            profile_data[release_keys[key]] = release_data[key]

        osp = OsProfile(profile_data=profile_data)

        return osp

    @classmethod
    def from_os_release_file(cls, path, profile_data={}):
        """Build an OsProfile from an on-disk os-release file.

        Construct a new OsProfile object using data obtained from
        the file specified by 'path'.

        :param path: Path to a file in os-release(5) format
        :param profile_data: an optional dictionary of profile data
                             overriding default values.
        :returns: A new OsProfile for the specified os-release file
        :rtype: OsProfile
        """
        with open(path, "r") as f:
            return cls.from_os_release(f, profile_data=profile_data)

    @classmethod
    def from_host_os_release(cls, profile_data={}):
        """Build an OsProfile from the current hosts's os-release.

        Construct a new OsProfile object using data obtained from
        the running hosts's /etc/os-release file.

        :param profile_data: an optional dictionary of profile data
                             overriding default values.
        :returns: A new OsProfile for the current host
        :rtype: OsProfile
        """
        return cls.from_os_release_file("/etc/os-release", profile_data=profile_data)

    def _profile_path(self):
        """Return the path to this profile's on-disk data.

        Return the full path to this OsProfile in the Boom profiles
        directory (or the location to which it will be written, if
        it has not yet been written).

        :rtype: str
        :returns: The absolute path for this OsProfile's file
        """
        profile_id = (self.os_id, self.os_short_name, self.os_version_id)
        profile_path_name = BOOM_OS_PROFILE_FORMAT % (profile_id)
        return path_join(boom_profiles_path(), profile_path_name)

    def write_profile(self, force=False):
        """Write out profile data to disk.

        Write out this ``OsProfile``'s data to a file in Boom
        format to the paths specified by the current configuration.

        Currently the ``os_id``, ``short_name`` and ``version_id``
        keys are used to construct the file name.

        If the value of ``force`` is ``False`` and the ``OsProfile``
        is not currently marked as dirty (either new, or modified
        since the last load operation) the write will be skipped.

        :param force: Force this profile to be written to disk even
                      if the entry is unmodified.
        :raises: ``OsError`` if the temporary entry file cannot be
                 renamed, or if setting file permissions on the
                 new entry file fails.
        """
        path = boom_profiles_path()
        mode = BOOM_PROFILE_MODE
        self._write_profile(self.os_id, path, mode, force=force)

    def delete_profile(self):
        """Delete on-disk data for this profile.

        Remove the on-disk profile corresponding to this
        ``OsProfile`` object. This will permanently erase the
        current file (although the current data may be re-written at
        any time by calling ``write_profile()`` before the object is
        disposed of).

        :rtype: ``NoneType``
        :raises: ``OsError`` if an error occurs removing the file or
                 ``ValueError`` if the profile does not exist.
        """
        global _profiles
        self._delete_profile(self.os_id)
        if _profiles and self in _profiles:
            _profiles.remove(self)
        if _profiles_by_id and self.os_id in _profiles_by_id:
            _profiles_by_id.pop(self.os_id)


__all__ = [
    "BoomProfile",
    "OsProfile",
    "profiles_loaded",
    "drop_profiles",
    "load_profiles",
    "write_profiles",
    "find_profiles",
    "get_os_profile_by_id",
    "select_profile",
    "match_os_profile",
    "match_os_profile_by_version",
    "key_from_key_name",
    # Module constants
    "BOOM_PROFILES",
    "BOOM_OS_PROFILE_FORMAT",
    "BOOM_PROFILE_MODE",
    # Exported key names
    "BOOM_OS_ID",
    "BOOM_OS_NAME",
    "BOOM_OS_SHORT_NAME",
    "BOOM_OS_VERSION",
    "BOOM_OS_VERSION_ID",
    "BOOM_OS_UNAME_PATTERN",
    "BOOM_OS_KERNEL_PATTERN",
    "BOOM_OS_INITRAMFS_PATTERN",
    "BOOM_OS_ROOT_OPTS_LVM2",
    "BOOM_OS_ROOT_OPTS_BTRFS",
    "BOOM_OS_OPTIONS",
    "BOOM_OS_TITLE",
    "BOOM_OS_OPTIONAL_KEYS",
    "OS_PROFILE_KEYS",
    "OS_KEY_NAMES",
    "OS_REQUIRED_KEYS",
    "OS_ROOT_KEYS",
    # Path configuration
    "boom_profiles_path",
]

# vim: set et ts=4 sw=4 :
