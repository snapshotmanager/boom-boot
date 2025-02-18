# Copyright Red Hat
#
# boom/hostprofile.py - Boom host profiles
#
# This file is part of the boom project.
#
# SPDX-License-Identifier: GPL-2.0-only
"""The ``boom.hostprofile``  module defines the `HostProfile` class that
represents a host system profile. A `HostProfile` defines the identity
of a host and includes template values that override the corresponding
``OsProfile`` defaults for the respective host.

Functions are provided to read and write host system profiles from
an on-disk store, and to retrieve ``HostProfile`` instances using
various selection criteria.

The ``HostProfile`` class includes named properties for each profile
attribute ("profile key"). In addition, the class serves as a container
type, allowing attributes to be accessed via dictionary-style indexing.
This simplifies iteration over a profile's key / value pairs and allows
straightforward access to all members in scripts and the Python shell.

The keys used to access ``HostProfile`` members (and their corresponding
property names) are identical to those used by the ``OsProfile`` class.
"""
from __future__ import print_function

from hashlib import sha1
from os.path import join as path_join
import logging
import string

from boom import *
from boom.osprofile import *

# Module logging configuration
_log = logging.getLogger(__name__)
_log.set_debug_mask(BOOM_DEBUG_PROFILE)

_log_debug = _log.debug
_log_debug_profile = _log.debug_masked
_log_info = _log.info
_log_warn = _log.warning
_log_error = _log.error

#: Global host profile list
_host_profiles = []
_host_profiles_by_id = {}
_host_profiles_by_host_id = {}

#: Whether profiles have been read from disk
_host_profiles_loaded = False

#: Boom profiles directory name.
BOOM_HOST_PROFILES = "hosts"

#: File name format for Boom profiles.
BOOM_HOST_PROFILE_FORMAT = "%s-%s.host"

#: The file mode with which to create Boom profiles.
BOOM_HOST_PROFILE_MODE = 0o644

# Constants for Boom profile keys
#: Constant for the Boom host identifier profile key.
BOOM_HOST_ID = "BOOM_HOST_ID"
#: Constant for the Boom host name profile key.
BOOM_HOST_NAME = "BOOM_HOST_NAME"
#: Constant for the Boom host add options key.
BOOM_HOST_ADD_OPTS = "BOOM_HOST_ADD_OPTS"
#: Constant for the Boom host del options key.
BOOM_HOST_DEL_OPTS = "BOOM_HOST_DEL_OPTS"
#: Constant for the Boom host label key.
BOOM_HOST_LABEL = "BOOM_HOST_LABEL"

#: Constant for shared machine_id key
BOOM_ENTRY_MACHINE_ID = "BOOM_ENTRY_MACHINE_ID"

#: Ordered list of possible host profile keys, partitioned into
#: mandatory keys, optional host profile keys, keys mapping to
#: embedded ``OsProfile`` identity data, and ``OsProfile`` pattern
#: keys that may be overridden in the ``HostProfile``.
HOST_PROFILE_KEYS = [
    # HostProfile identifier
    BOOM_HOST_ID,
    # Machine hostname
    BOOM_HOST_NAME,
    # Binding to label, machine_id and OsProfile
    BOOM_ENTRY_MACHINE_ID,
    BOOM_OS_ID,
    # Optional host profile keys
    BOOM_HOST_LABEL,
    BOOM_HOST_ADD_OPTS,
    BOOM_HOST_DEL_OPTS,
    # Keys 7-10 OS identity keys mapped to the embedded OsProfile.
    BOOM_OS_NAME,
    BOOM_OS_SHORT_NAME,
    BOOM_OS_VERSION,
    BOOM_OS_VERSION_ID,
    # Keys 11-15 (OsProfile patterns) may be overridden in the host profile.
    BOOM_OS_UNAME_PATTERN,
    BOOM_OS_KERNEL_PATTERN,
    BOOM_OS_INITRAMFS_PATTERN,
    BOOM_OS_ROOT_OPTS_LVM2,
    BOOM_OS_ROOT_OPTS_BTRFS,
    BOOM_OS_OPTIONS,
]

#: A map of Boom host profile keys to human readable key names suitable
#: for use in formatted output. These key names are used to format a
#: ``HostProfile`` object as a human readable string.
HOST_KEY_NAMES = {
    # Keys unique to HostProfile
    BOOM_HOST_ID: "Host ID",
    BOOM_HOST_NAME: "Host name",
    BOOM_HOST_LABEL: "Host label",
    BOOM_HOST_ADD_OPTS: "Add options",
    BOOM_HOST_DEL_OPTS: "Del options",
    # Keys shared with BootEntry
    BOOM_ENTRY_MACHINE_ID: "Machine ID",
    # Keys incorporated from OsProfile
    BOOM_OS_ID: OS_KEY_NAMES[BOOM_OS_ID],
    BOOM_OS_NAME: OS_KEY_NAMES[BOOM_OS_NAME],
    BOOM_OS_SHORT_NAME: OS_KEY_NAMES[BOOM_OS_SHORT_NAME],
    BOOM_OS_VERSION: OS_KEY_NAMES[BOOM_OS_VERSION],
    BOOM_OS_VERSION_ID: OS_KEY_NAMES[BOOM_OS_VERSION_ID],
    BOOM_OS_UNAME_PATTERN: OS_KEY_NAMES[BOOM_OS_UNAME_PATTERN],
    BOOM_OS_KERNEL_PATTERN: OS_KEY_NAMES[BOOM_OS_KERNEL_PATTERN],
    BOOM_OS_INITRAMFS_PATTERN: OS_KEY_NAMES[BOOM_OS_INITRAMFS_PATTERN],
    BOOM_OS_ROOT_OPTS_LVM2: OS_KEY_NAMES[BOOM_OS_ROOT_OPTS_LVM2],
    BOOM_OS_ROOT_OPTS_BTRFS: OS_KEY_NAMES[BOOM_OS_ROOT_OPTS_BTRFS],
    BOOM_OS_OPTIONS: OS_KEY_NAMES[BOOM_OS_OPTIONS],
}

#: Boom host profile keys that must exist in a valid profile.
HOST_REQUIRED_KEYS = HOST_PROFILE_KEYS[0:4]

#: Boom optional host profile configuration keys.
HOST_OPTIONAL_KEYS = HOST_PROFILE_KEYS[4:]


def _host_exists(host_id):
    """Test whether the specified ``host_id`` already exists.

    Used during ``HostProfile`` initialisation to test if the new
    ``host_id`` is already known (and to avoid passing through
    find_profiles(), which may trigger recursive profile loading).

    :param host_id: the host identifier to check for

    :returns: ``True`` if the identifier is known or ``False``
              otherwise.
    :rtype: bool
    """
    global _host_profiles_by_host_id
    if not _host_profiles_by_host_id:
        return False
    if host_id in _host_profiles_by_host_id:
        return True
    return False


def boom_host_profiles_path():
    """Return the path to the boom host profiles directory.

    :returns: The boom host profiles path.
    :rtype: str
    """
    return path_join(get_boom_path(), BOOM_HOST_PROFILES)


def host_profiles_loaded():
    """Test whether profiles have been loaded from disk.

    :rtype: bool
    :returns: ``True`` if profiles are loaded in memory or ``False``
              otherwise
    """
    return _host_profiles_loaded


def drop_host_profiles():
    """Drop all in-memory host profiles."""
    global _host_profiles, _host_profiles_by_id, _host_profiles_by_host_id
    global _host_profiles_loaded

    _host_profiles = []
    _host_profiles_by_id = {}
    _host_profiles_by_host_id = {}
    _host_profiles_loaded = False


def load_host_profiles():
    """Load HostProfile data from disk.

    Load the set of host profiles found at the path
    ``boom.hostprofile.boom_profiles_path()`` into the global host
    profile list.

    This function may be called to explicitly load, or reload the
    set of profiles on-disk. Profiles are also loaded implicitly
    if an API function or method that requires access to profiles
    is invoked (for example, ``boom.bootloader.load_entries()``.

    :returns: None
    """
    global _host_profiles_loaded
    drop_host_profiles()
    profiles_path = boom_host_profiles_path()
    load_profiles_for_class(HostProfile, "Host", profiles_path, "host")

    _host_profiles_loaded = True
    _log_debug("Loaded %d host profiles", len(_host_profiles))


def write_host_profiles(force=False):
    """Write all HostProfile data to disk.

    Write the current list of host profiles to the directory located
    at ``boom.osprofile.boom_profiles_path()``.

    :rtype: None
    """
    global _host_profiles
    _log_debug("Writing host profiles to %s", boom_host_profiles_path())
    for hp in _host_profiles:
        try:
            hp.write_profile(force)
        except Exception as e:
            _log_warn(
                "Failed to write HostProfile(machine_id='%s'): %s",
                hp.disp_machine_id,
                e,
            )


def min_host_id_width():
    """Calculate the minimum unique width for host_id values.

    Calculate the minimum width to ensure uniqueness when displaying
    host_id values.

    :returns: the minimum host_id width.
    :rtype: int
    """
    return min_id_width(7, _host_profiles, "host_id")


def min_machine_id_width():
    """Calculate the minimum unique width for host_id values.

    Calculate the minimum width to ensure uniqueness when displaying
    host_id values.

    :returns: the minimum host_id width.
    :rtype: int
    """
    return min_id_width(7, _host_profiles, "machine_id")


def select_host_profile(s, hp):
    """Test the supplied host profile against selection criteria.

    Test the supplied ``HostProfile`` against the selection criteria
    in ``s`` and return ``True`` if it passes, or ``False``
    otherwise.

    :param s: The selection criteria
    :param hp: The ``HostProfile`` to test
    :rtype: bool
    :returns: True if ``hp`` passes selection or ``False`` otherwise.
    """
    if s.host_id and not hp.host_id.startswith(s.host_id):
        return False
    if s.machine_id and hp.machine_id != s.machine_id:
        return False
    if s.host_name and hp.host_name != s.host_name:
        return False
    if s.host_label and hp.label != s.host_label:
        return False
    if s.host_short_name and hp.short_name != s.host_short_name:
        return False
    if s.host_add_opts and hp.add_opts != s.host_add_opts:
        return False
    if s.host_del_opts and hp.del_opts != s.host_del_opts:
        return False
    if s.os_id and not hp.os_id.startswith(s.os_id):
        return False
    if s.os_name and hp.os_name != s.os_name:
        return False
    if s.os_short_name and hp.os_short_name != s.os_short_name:
        return False
    if s.os_version and hp.os_version != s.os_version:
        return False
    if s.os_version_id and hp.os_version_id != s.os_version_id:
        return False
    if s.os_uname_pattern and hp.uname_pattern != s.os_uname_pattern:
        return False
    if s.os_kernel_pattern and hp.kernel_pattern != s.os_kernel_pattern:
        return False
    if s.os_initramfs_pattern and hp.initramfs_pattern != s.os_initramfs_pattern:
        return False
    if s.os_options and hp.options != s.os_options:
        return False
    return True


def find_host_profiles(selection=None, match_fn=select_host_profile):
    """Find host profiles matching selection criteria.

    Return a list of ``HostProfile`` objects matching the specified
    criteria. Matching proceeds as the logical 'and' of all criteria.
    Criteria that are unset (``None``) are ignored.

    If the optional ``match_fn`` parameter is specified, the match
    criteria parameters are ignored and each ``HostProfile`` is
    tested in turn by calling ``match_fn``. If the matching function
    returns ``True`` the ``HostProfile`` will be included in the
    results.

    If no ``HostProfile`` matches the specified criteria the empty
    list is returned.

    Host profiles will be automatically loaded from disk if they are
    not already in memory.

    :param selection: A ``Selection`` object specifying the match
                      criteria for the operation.
    :param match_fn: An optional match function to test profiles.
    :returns: a list of ``HostProfile`` objects.
    :rtype: list
    """
    # Use null search criteria if unspecified
    selection = selection if selection else Selection()

    selection.check_valid_selection(host=True)

    if not host_profiles_loaded():
        load_host_profiles()

    matches = []

    _log_debug_profile("Finding host profiles for %s", repr(selection))
    for hp in _host_profiles:
        if match_fn(selection, hp):
            matches.append(hp)
    _log_debug_profile("Found %d host profiles", len(matches))
    matches.sort(key=lambda h: h.host_name)

    return matches


def get_host_profile_by_id(machine_id, label=""):
    """Find a HostProfile by its machine_id.

    Return the HostProfile object corresponding to ``machine_id``,
    or ``None`` if it is not found.

    :rtype: HostProfile
    :returns: An HostProfile matching machine_id or None if no match
              was found.
    """
    global _host_profiles, _host_profiles_by_id, _host_profiles_by_host_id
    if not host_profiles_loaded():
        load_host_profiles()
    if machine_id in _host_profiles_by_id:
        if label in _host_profiles_by_id[machine_id]:
            return _host_profiles_by_id[machine_id][label]
    return None


def match_host_profile(entry):
    """Attempt to match a BootEntry to a corresponding HostProfile.

    Attempt to find a loaded ``HostProfile`` object with the a
    ``machine_id`` that matches the supplied ``BootEntry``.
    Checking terminates on the first matching ``HostProfile``.

    :param entry: A ``BootEntry`` object with no attached
                  ``HostProfile``.
    :returns: The corresponding ``HostProfile`` for the supplied
              ``BootEntry`` or ``None`` if no match is found.
    :rtype: ``BootEntry`` or ``NoneType``.
    """
    global _host_profiles, _host_profiles_loaded

    if not host_profiles_loaded():
        load_host_profiles()

    _log_debug(
        "Attempting to match profile for BootEntry(title='%s', "
        "version='%s') with machine_id='%s'",
        entry.title,
        entry.version,
        entry.machine_id,
    )

    # Attempt to match by uname pattern
    for hp in _host_profiles:
        if hp.machine_id == entry.machine_id:
            _log_debug(
                "Matched BootEntry(version='%s', boot_id='%s') "
                "to HostProfile(name='%s', machine_id='%s')",
                entry.version,
                entry.disp_boot_id,
                hp.host_name,
                hp.machine_id,
            )
            return hp

    return None


class HostProfile(BoomProfile):
    """Class HostProfile implements Boom host system profiles.

    Objects of type HostProfile define a host identiry, and optional
    fields or ``BootParams`` modifications to be applied to the
    specified host.

    Host profiles may modify any non-identity ``OsProfile`` key,
    either adding to or replacing the value defined by an embedded
    ``OsProfile`` instance.
    """

    _profile_data = None
    _unwritten = False
    _comments = None

    _profile_keys = HOST_PROFILE_KEYS
    _required_keys = HOST_REQUIRED_KEYS
    _identity_key = BOOM_HOST_ID

    _osp = None

    def _key_data(self, key):
        if key in self._profile_data:
            return self._profile_data[key]
        if key in self.osp._profile_data:
            return self.osp._profile_data[key]
        return None

    def _have_key(self, key):
        """Test for presence of a Host or Os profile key."""
        return key in self._profile_data or key in self.osp._profile_data

    def __str__(self):
        """Format this HostProfile as a human readable string.

        Profile attributes are printed as "Name: value, " pairs,
        with like attributes grouped together onto lines.

        :returns: A human readable string representation of this
                  HostProfile.

        :rtype: string
        """
        # FIXME HostProfile breaks
        breaks = [
            BOOM_HOST_ID,
            BOOM_HOST_NAME,
            BOOM_OS_ID,
            BOOM_ENTRY_MACHINE_ID,
            BOOM_HOST_LABEL,
            BOOM_OS_VERSION,
            BOOM_OS_UNAME_PATTERN,
            BOOM_HOST_ADD_OPTS,
            BOOM_HOST_DEL_OPTS,
            BOOM_OS_INITRAMFS_PATTERN,
            BOOM_OS_ROOT_OPTS_LVM2,
            BOOM_OS_ROOT_OPTS_BTRFS,
            BOOM_OS_OPTIONS,
        ]

        fields = [f for f in HOST_PROFILE_KEYS if self._have_key(f)]
        hp_str = ""
        tail = ""
        for f in fields:
            hp_str += '%s: "%s"' % (HOST_KEY_NAMES[f], self._key_data(f))
            tail = ",\n" if f in breaks else ", "
            hp_str += tail
        hp_str = hp_str.rstrip(tail)
        return hp_str

    def __repr__(self):
        """Format this HostProfile as a machine readable string.

        Return a machine-readable representation of this ``HostProfile``
        object. The string is formatted as a call to the ``HostProfile``
        constructor, with values passed as a dictionary to the
        ``profile_data`` keyword argument.

        :returns: a string representation of this ``HostProfile``.
        :rtype: string
        """
        hp_str = "HostProfile(profile_data={"
        fields = [f for f in HOST_PROFILE_KEYS if self._have_key(f)]
        for f in fields:
            hp_str += '%s:"%s", ' % (f, self._key_data(f))
        hp_str = hp_str.rstrip(", ")
        return hp_str + "})"

    def __setitem__(self, key, value):
        """Set the specified ``HostProfile`` key to the given value.

        :param key: the ``HostProfile`` key to be set.
        :param value: the value to set for the specified key.
        """

        # FIXME: duplicated from OsProfile.__setitem__ -> factor
        # osprofile.check_format_key_value(key, value)
        # and include isstr() key name validation etc.

        # Map hp key names to a list of format keys which must not
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
                    raise ValueError(
                        "HostProfile.%s cannot contain %s"
                        % (key, key_from_key_name(bad_key))
                    )

        if not isinstance(key, str):
            raise TypeError("HostProfile key must be a string.")

        if key not in HOST_PROFILE_KEYS:
            raise ValueError("Invalid HostProfile key: %s" % key)

        if key in bad_key_map:
            _check_format_key_value(key, value, bad_key_map[key])

        self._profile_data[key] = value

    def _generate_id(self):
        """Generate a new host identifier.

        Generate a new sha1 profile identifier for this profile,
        using the name, machine_id, and os_id and store it in
        _profile_data.

        :returns: None
        """
        hashdata = self.machine_id + self.label

        digest = sha1(hashdata.encode("utf-8"), usedforsecurity=False).hexdigest()
        self._profile_data[BOOM_HOST_ID] = digest

    def __set_os_profile(self):
        """Set this ``HostProfile``'s ``osp`` member to the
        corresponding profile for the set ``os_id``.
        """
        os_id = self._profile_data[BOOM_OS_ID]
        osps = find_profiles(Selection(os_id=os_id))
        if not osps:
            raise ValueError("OsProfile not found: %s" % os_id)
        if len(osps) > 1:
            raise ValueError("OsProfile identifier '%s' is ambiguous" % os_id)

        self.osp = osps[0]

    def _append_profile(self):
        """Append a HostProfile to the global profile list"""
        global _host_profiles, _host_profiles_by_id, _host_profiles_by_host_id
        if _host_exists(self.host_id):
            raise ValueError("Profile already exists (host_id=%s)" % self.disp_host_id)

        _host_profiles.append(self)
        machine_id = self.machine_id
        if machine_id not in _host_profiles_by_id:
            _host_profiles_by_id[machine_id] = {}
        _host_profiles_by_id[machine_id][self.label] = self
        _host_profiles_by_host_id[self.host_id] = self

    def _from_data(self, host_data, dirty=True):
        """Initialise a ``HostProfile`` from in-memory data.

        Initialise a new ``HostProfile`` object using the profile
        data in the `host_data` dictionary.

        This method should not be called directly: to build a new
        `Hostprofile`` object from in-memory data, use the class
        initialiser with the ``host_data`` argument.

        :returns: None
        """
        err_str = "Invalid profile data (missing %s)"

        for key in HOST_REQUIRED_KEYS:
            if key == BOOM_HOST_ID:
                continue
            if key not in host_data:
                raise ValueError(err_str % key)

        self._profile_data = dict(host_data)

        if BOOM_HOST_ID not in self._profile_data:
            self._generate_id()

        self.__set_os_profile()

        if dirty:
            self._dirty()

        self._append_profile()

    def __init__(
        self,
        machine_id=None,
        host_name=None,
        label=None,
        os_id=None,
        kernel_pattern=None,
        initramfs_pattern=None,
        root_opts_lvm2=None,
        root_opts_btrfs=None,
        add_opts="",
        del_opts="",
        options=None,
        profile_file=None,
        profile_data=None,
    ):
        """Initialise a new ``HostProfile`` object.

        If neither ``profile_file`` nor ``profile_data`` is given,
        all of ``machine_id``, ``name``, and ``os_id`` must be given.

        These values form the host profile identity and are used to
        generate the profile unique identifier.

        :param host_name: The hostname of this system
        :param os_id: An OS identifier specifying the ``OsProfile``
                      to use with this host profile.
        :param profile_data: An optional dictionary mapping from
                             ``BOOM_*`` keys to profile values.
        :param profile_file: An optional path to a file from which
                             profile data should be loaded. The file
                             should be in Boom host profile format,
                             with ``BOOM_*`` key=value pairs.
        :returns: A new ``HostProfile`` object.
        :rtype: class HostProfile
        """
        global _host_profiles
        self._profile_data = {}

        # Initialise BoomProfile base class
        super(HostProfile, self).__init__(
            HOST_PROFILE_KEYS, HOST_REQUIRED_KEYS, BOOM_HOST_ID
        )

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

        required_args = [machine_id, host_name, os_id]
        if any([not val for val in required_args]):
            raise ValueError(
                "Invalid host profile arguments: machine_id, "
                "host_name, and os_id are mandatory."
            )

        osps = find_profiles(Selection(os_id=os_id))
        if not osps:
            raise ValueError("No matching profile found for os_id=%s" % os_id)
        if len(osps) > 1:
            raise ValueError("OsProfile ID is ambiguous: %s" % os_id)
        os_id = osps[0].os_id

        self._profile_data[BOOM_ENTRY_MACHINE_ID] = machine_id
        self._profile_data[BOOM_HOST_NAME] = host_name
        self._profile_data[BOOM_OS_ID] = os_id
        self._profile_data[BOOM_HOST_LABEL] = label

        # Only set keys that have a value in the host profile data dict
        if kernel_pattern:
            self._profile_data[BOOM_OS_KERNEL_PATTERN] = kernel_pattern
        if initramfs_pattern:
            self._profile_data[BOOM_OS_INITRAMFS_PATTERN] = initramfs_pattern
        if root_opts_lvm2:
            self._profile_data[BOOM_OS_ROOT_OPTS_LVM2] = root_opts_lvm2
        if root_opts_btrfs:
            self._profile_data[BOOM_OS_ROOT_OPTS_BTRFS] = root_opts_btrfs
        if add_opts:
            self._profile_data[BOOM_HOST_ADD_OPTS] = add_opts
        if del_opts:
            self._profile_data[BOOM_HOST_DEL_OPTS] = del_opts
        if options:
            self._profile_data[BOOM_OS_OPTIONS] = options

        self.__set_os_profile()

        self._generate_id()
        _host_profiles.append(self)

    # We use properties for the HostProfile attributes: this is to
    # allow the values to be stored in a dictionary. Although
    # properties are quite verbose this reduces the code volume
    # and complexity needed to marshal and unmarshal the various
    # file formats used, as well as conversion to and from string
    # representations of HostProfile objects.

    # Keys obtained from os-release data form the profile's identity:
    # the corresponding attributes are read-only.

    # HostProfile properties:
    #
    #  Profile identity properties (ro):
    #   host_id
    #   disp_os_id
    #
    #  Profile identity properties (rw):
    #   host_name
    #   machine_id
    #   os_id
    #
    #  Properties mapped to OsProfile (ro)
    #   os_name
    #   os_short_name
    #   os_version
    #   os_version_id
    #   uname_pattern
    #
    # Properties overridden or mapped to OsProfile (rw)
    #   kernel_pattern
    #   initramfs_pattern
    #   root_opts_lvm2
    #   root_opts_btrfs
    #   options
    #
    # HostProfile specific properties (rw)
    #   label
    #   add_opts
    #   del_opts

    @property
    def disp_os_id(self):
        """The display os_id of this profile.

        Return the shortest prefix of this OsProfile's os_id that
        is unique within the current set of loaded profiles.

        :getter: return this OsProfile's os_id.
        :type: str
        """
        return self.osp.disp_os_id

    @property
    def host_id(self):
        if BOOM_HOST_ID not in self._profile_data:
            self._generate_id()
        return self._profile_data[BOOM_HOST_ID]

    @property
    def disp_host_id(self):
        """The display host_id of this profile

        Return the shortest prefix of this HostProfile's os_id that
        is unique within the current set of loaded profiles.

        :getter: return this HostProfile's display host_id.
        :type: str
        """
        return self.host_id[: min_host_id_width()]

    @property
    def disp_machine_id(self):
        """The machine_id of this host profile.
        Return the shortest prefix of this HostProfile's os_id that
        is unique within the current set of loaded profiles.

        :getter: return this HostProfile's display host_id.
        :type: str
        """
        return self.machine_id[: min_machine_id_width()]

    @property
    def machine_id(self):
        """The machine_id of this host profile.
        Return the shortest prefix of this HostProfile's os_id that
        is unique within the current set of loaded profiles.

        :getter: return this ``HostProfile``'s display host_id.
        :setter: change this ``HostProfile``'s ``machine_id``. This
                 will change the ``host_id``.
        :type: str
        """
        return self._profile_data[BOOM_ENTRY_MACHINE_ID]

    @machine_id.setter
    def machine_id(self, value):
        if value == self._profile_data[BOOM_ENTRY_MACHINE_ID]:
            return
        self._profile_data[BOOM_ENTRY_MACHINE_ID] = value
        self._dirty()
        self._generate_id()

    @property
    def os_id(self):
        """The ``os_id`` of this profile.

        :getter: returns the ``os_id`` as a string.
        :type: string
        """
        return self.osp.os_id

    @os_id.setter
    def os_id(self, value):
        if value == self._profile_data[BOOM_OS_ID]:
            return
        self._profile_data[BOOM_OS_ID] = value
        self.__set_os_profile()
        self._dirty()
        self._generate_id()

    @property
    def osp(self):
        """The ``OsProfile`` used by this ``HostProfile``.

        :getter: returns the ``OsProfile`` object used by this
                 ``HostProfile``.
        :setter: stores a new ``OsProfile`` for use by this
                 ``HostProfile`` and updates the stored ``os_id``
                 value in the host profile.
        """
        return self._osp

    @osp.setter
    def osp(self, osp):
        if self._osp and osp.os_id == self._osp.os_id:
            return
        self._osp = osp
        self._profile_data[BOOM_OS_ID] = osp.os_id
        self._dirty()
        self._generate_id()

    @property
    def host_name(self):
        """The ``host_name`` of this profile.

        Normally set to the hostname of the system corresponding to
        this ``HostProfile``.

        :getter: returns the ``host_name`` as a string.
        :type: string
        """
        return self._profile_data[BOOM_HOST_NAME]

    @host_name.setter
    def host_name(self, value):
        if value == self._profile_data[BOOM_HOST_NAME]:
            return
        self._profile_data[BOOM_HOST_NAME] = value
        self._dirty()
        self._generate_id()

    @property
    def short_name(self):
        """The ``short_name`` of this profile.

        If ``HostProfile.host_name`` appears to contain a DNS-style name,
        return only the host portion.

        :getter: returns the ``short_name`` as a string.
        :type: string
        """
        host_name = self._profile_data[BOOM_HOST_NAME]
        return host_name.split(".")[0] if "." in host_name else host_name

    #
    #  Properties mapped to OsProfile
    #

    @property
    def os_name(self):
        """The ``os_name`` of this profile.

        :getter: returns the ``os_name`` as a string.
        :type: string
        """
        return self.osp.os_name

    @property
    def os_short_name(self):
        """The ``os_short_name`` of this profile.

        :getter: returns the ``os_short_name`` as a string.
        :type: string
        """
        return self.osp.os_short_name

    @property
    def os_version(self):
        """The ``os_version`` of this profile.

        :getter: returns the ``os_version`` as a string.
        :type: string
        """
        return self.osp.os_version

    @property
    def os_version_id(self):
        """The ``os_version_id`` of this profile.

        :getter: returns the ``os_version_id`` as a string.
        :type: string
        """
        return self.osp.os_version_id

    @property
    def uname_pattern(self):
        """The current ``uname_pattern`` setting of this profile.

        :getter: returns the ``uname_pattern`` as a string.
        :setter: stores a new ``uname_pattern`` setting.
        :type: string
        """
        if BOOM_OS_UNAME_PATTERN in self._profile_data:
            return self._profile_data[BOOM_OS_UNAME_PATTERN]
        return self.osp.uname_pattern

    #
    # Properties overridden or mapped to OsProfile
    #

    @property
    def kernel_pattern(self):
        """The current ``kernel_pattern`` setting of this profile.

        :getter: returns the ``kernel_pattern`` as a string.
        :setter: stores a new ``kernel_pattern`` setting.
        :type: string
        """
        if BOOM_OS_KERNEL_PATTERN in self._profile_data:
            return self._profile_data[BOOM_OS_KERNEL_PATTERN]
        return self.osp.kernel_pattern

    @kernel_pattern.setter
    def kernel_pattern(self, value):
        kernel_key = key_from_key_name(FMT_KERNEL)
        if kernel_key in value:
            raise ValueError("HostProfile.kernel cannot contain %s" % kernel_key)
        self._profile_data[BOOM_OS_KERNEL_PATTERN] = value
        self._dirty()

    @property
    def initramfs_pattern(self):
        """The current ``initramfs_pattern`` setting of this profile.

        :getter: returns the ``initramfs_pattern`` as a string.
        :setter: store a new ``initramfs_pattern`` setting.
        :type: string
        """
        if BOOM_OS_INITRAMFS_PATTERN in self._profile_data:
            return self._profile_data[BOOM_OS_INITRAMFS_PATTERN]
        return self.osp.initramfs_pattern

    @initramfs_pattern.setter
    def initramfs_pattern(self, value):
        initramfs_key = key_from_key_name(FMT_INITRAMFS)
        if initramfs_key in value:
            raise ValueError("HostProfile.initramfs cannot contain %s" % initramfs_key)
        self._profile_data[BOOM_OS_INITRAMFS_PATTERN] = value
        self._dirty()

    @property
    def root_opts_lvm2(self):
        """The current LVM2 root options setting of this profile.

        :getter: returns the ``root_opts_lvm2`` value as a string.
        :setter: store a new ``root_opts_lvm2`` value.
        :type: string
        """
        if BOOM_OS_ROOT_OPTS_LVM2 in self._profile_data:
            return self._profile_data[BOOM_OS_ROOT_OPTS_LVM2]

        return self.osp.root_opts_lvm2

    @root_opts_lvm2.setter
    def root_opts_lvm2(self, value):
        root_opts_key = key_from_key_name(FMT_ROOT_OPTS)
        if root_opts_key in value:
            raise ValueError(
                "HostProfile.root_opts_lvm2 cannot contain " "%s" % root_opts_key
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
        if BOOM_OS_ROOT_OPTS_BTRFS in self._profile_data:
            return self._profile_data[BOOM_OS_ROOT_OPTS_BTRFS]
        return self.osp.root_opts_btrfs

    @root_opts_btrfs.setter
    def root_opts_btrfs(self, value):
        root_opts_key = key_from_key_name(FMT_ROOT_OPTS)
        if root_opts_key in value:
            raise ValueError(
                "HostProfile.root_opts_btrfs cannot contain %s" % root_opts_key
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
        if BOOM_OS_OPTIONS in self._profile_data:
            return self._profile_data[BOOM_OS_OPTIONS]
        return self.osp.options

    @options.setter
    def options(self, value):
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
        if not value:
            # It is valid to set an empty title in a HostProfile as long
            # as the OsProfile defines one.
            if not self.osp or not self.osp.title:
                raise ValueError("Entry title cannot be empty")
        self._profile_data[BOOM_OS_TITLE] = value
        self._dirty()

    @property
    def optional_keys(self):
        if not self.osp or not self.osp.optional_keys:
            return ""
        return self.osp.optional_keys

    #
    # HostProfile specific properties
    #

    @property
    def add_opts(self):
        if BOOM_HOST_ADD_OPTS in self._profile_data:
            return self._profile_data[BOOM_HOST_ADD_OPTS]
        return ""

    @add_opts.setter
    def add_opts(self, opts):
        self._profile_data[BOOM_HOST_ADD_OPTS] = opts
        self._dirty()

    @property
    def del_opts(self):
        if BOOM_HOST_DEL_OPTS in self._profile_data:
            return self._profile_data[BOOM_HOST_DEL_OPTS]
        return ""

    @del_opts.setter
    def del_opts(self, opts):
        self._profile_data[BOOM_HOST_DEL_OPTS] = opts
        self._dirty()

    @property
    def label(self):
        if BOOM_HOST_LABEL in self._profile_data:
            return self._profile_data[BOOM_HOST_LABEL]
        return ""

    @label.setter
    def label(self, value):
        valid_chars = string.ascii_letters + string.digits + "_- "

        if BOOM_HOST_LABEL in self._profile_data:
            if self._profile_data[BOOM_HOST_LABEL] == value:
                return

        for c in value:
            if c not in valid_chars:
                raise ValueError("Invalid host label character: '%s'" % c)

        self._profile_data[BOOM_HOST_LABEL] = value
        self._dirty()
        self._generate_id()

    def _profile_path(self):
        """Return the path to this profile's on-disk data.

        Return the full path to this HostProfile in the Boom profiles
        directory (or the location to which it will be written, if
        it has not yet been written).

        :rtype: str
        :returns: The absolute path for this HostProfile's file
        """
        if self.label:
            label = self.label
            if " " in label:
                label = label.replace(" ", "_")
            names = (self.short_name, label)
            name_fmt = "%s-%s"
        else:
            names = self.short_name
            name_fmt = "%s"
        profile_name = name_fmt % names
        profile_id = (self.host_id, profile_name)
        profile_path_name = BOOM_HOST_PROFILE_FORMAT % profile_id
        return path_join(boom_host_profiles_path(), profile_path_name)

    def write_profile(self, force=False):
        """Write out profile data to disk.

        Write out this ``HostProfile``'s data to a file in Boom
        format to the paths specified by the current configuration.

        Currently the ``machine_id`` and ``name`` keys are used to
        construct the file name.

        If the value of ``force`` is ``False`` and the ``HostProfile``
        is not currently marked as dirty (either new, or modified
        since the last load operation) the write will be skipped.

        :param force: Force this profile to be written to disk even
                      if the entry is unmodified.
        :raises: ``OsError`` if the temporary entry file cannot be
                 renamed, or if setting file permissions on the
                 new entry file fails.
        """
        path = boom_host_profiles_path()
        mode = BOOM_HOST_PROFILE_MODE
        self._write_profile(self.host_id, path, mode, force=force)

    def delete_profile(self):
        """Delete on-disk data for this profile.

        Remove the on-disk profile corresponding to this
        ``HostProfile`` object. This will permanently erase the
        current file (although the current data may be re-written at
        any time by calling ``write_profile()`` before the object is
        disposed of).

        :rtype: ``NoneType``
        :raises: ``OsError`` if an error occurs removing the file or
                 ``ValueError`` if the profile does not exist.
        """
        global _host_profiles, _host_profiles_by_id, _host_profiles_by_host_id
        self._delete_profile(self.host_id)

        machine_id = self.machine_id
        host_id = self.host_id
        if _host_profiles and self in _host_profiles:
            _host_profiles.remove(self)
        if _host_profiles_by_id and machine_id in _host_profiles_by_id:
            _host_profiles_by_id.pop(machine_id)
        if _host_profiles_by_host_id and host_id in _host_profiles_by_host_id:
            _host_profiles_by_host_id.pop(host_id)


__all__ = [
    # Host profiles
    "HostProfile",
    "drop_host_profiles",
    "load_host_profiles",
    "write_host_profiles",
    "host_profiles_loaded",
    "find_host_profiles",
    "select_host_profile",
    "get_host_profile_by_id",
    "match_host_profile",
    "select_host_profile",
    # Host profile keys
    "BOOM_HOST_ID",
    "BOOM_HOST_NAME",
    "BOOM_HOST_ADD_OPTS",
    "BOOM_HOST_DEL_OPTS",
    "BOOM_HOST_LABEL",
    "HOST_PROFILE_KEYS",
    "HOST_REQUIRED_KEYS",
    "HOST_OPTIONAL_KEYS",
    # Path configuration
    "boom_host_profiles_path",
]

# vim: set et ts=4 sw=4 :
